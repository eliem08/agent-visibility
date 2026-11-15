"""Live platforms: ask a real assistant, and bring in answers captured from any other one.

`claude` calls the Claude API through the official SDK, which is an optional install (`pip install
anthropic`) so the core stays dependency-free. Credentials come from the environment the usual way
(ANTHROPIC_API_KEY or an `ant auth login` profile). Every prompt is a billed API call.

For assistants without an adapter here (ChatGPT, Perplexity, Gemini, Copilot), paste or export their
answers into a JSON file and use `import-answers`: the same parsing and metrics apply.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .core import MockPlatform, Platform, Project, parse_answer

DEFAULT_MODEL = "claude-opus-5-5"
MAX_ANSWER_CHARS = 200_000


class LiveError(ValueError):
    pass


class ClaudePlatform(Platform):
    """One user-style question per call, no system prompt, so the answer is what a buyer would get."""

    name = "claude"

    def __init__(self, model: str | None = None, client=None):
        self.model = model or os.environ.get("AGENT_VISIBILITY_CLAUDE_MODEL", DEFAULT_MODEL)
        if client is None:
            try:
                import anthropic
            except ImportError:
                raise LiveError("the claude platform needs the Anthropic SDK: pip install anthropic") from None
            client = anthropic.Anthropic()
        self.client = client

    def ask(self, prompt: str) -> str:
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                # a safety decline on the main model is re-run on a fallback inside the same call
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise _translate(e) from None
        if response.stop_reason == "refusal":
            return ""  # a declined prompt is a real result: the brand was not mentioned
        return "\n".join(block.text for block in response.content if block.type == "text")


def _translate(e: Exception) -> Exception:
    """Turn the SDK's typed errors into one-line messages; anything else passes through unchanged."""
    try:
        import anthropic
    except ImportError:
        return e
    if isinstance(e, anthropic.AuthenticationError):
        return LiveError("Claude API credentials are missing or invalid (set ANTHROPIC_API_KEY)")
    if isinstance(e, anthropic.RateLimitError):
        return LiveError("Claude API rate limit reached; run again later")
    if isinstance(e, anthropic.APIStatusError):
        return LiveError(f"Claude API error {e.status_code}: {e.message}")
    if isinstance(e, anthropic.APIConnectionError):
        return LiveError(f"could not reach the Claude API: {e}")
    return e


def platform_for(name: str, brands: list[str]) -> Platform:
    if name == "claude":
        return ClaudePlatform()
    if name.startswith("mock-"):
        return MockPlatform(name, brands)
    raise LiveError(
        f"no live adapter for platform {name!r}. Use 'claude', a 'mock-*' platform, or capture that "
        "assistant's answers and load them with import-answers"
    )


def import_answers(project: Project, path: str, now: datetime | None = None) -> list[dict]:
    """[{"platform": "chatgpt", "prompt": "...", "answer": "..."}] -> history rows."""
    with open(path, encoding="utf-8-sig") as fh:
        items = json.load(fh)
    if not isinstance(items, list) or not items:
        raise LiveError(f"{path}: expected a non-empty JSON list of {{platform, prompt, answer}} objects")
    ts = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    intents = {p["text"]: p.get("intent", "") for p in project.prompts}
    ents, rows = project.names(), []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict) or not all(
            isinstance(item.get(k), str) for k in ("platform", "prompt", "answer")
        ):
            raise LiveError(f"{path}: item {i} needs string fields platform, prompt and answer")
        if not item["platform"].strip() or not item["prompt"].strip():
            raise LiveError(f"{path}: item {i} has an empty platform or prompt")
        parsed = parse_answer(item["answer"][:MAX_ANSWER_CHARS], ents)
        prompt = item["prompt"].strip()
        rows.append(
            {
                "ts": ts,
                "platform": item["platform"].strip(),
                "prompt": prompt,
                "intent": intents.get(prompt, ""),
                **parsed,
            }
        )
    return rows
