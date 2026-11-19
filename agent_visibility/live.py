"""Live platforms: ask a real assistant, and bring in answers captured from any other one.

`claude` calls the Claude API through the official SDK, which is an optional install (`pip install
anthropic`) so the core stays dependency-free. Credentials come from the environment the usual way
(ANTHROPIC_API_KEY or an `ant auth login` profile). Every prompt is a billed API call.

`openai`, `perplexity` and `gemini` call those APIs directly with the standard library (keys from
OPENAI_API_KEY, PERPLEXITY_API_KEY and GEMINI_API_KEY; models from AGENT_VISIBILITY_<NAME>_MODEL). An API
answer is close to, but not the same as, what the consumer app shows: the apps add memory, location and their
own browsing. Perplexity's cited sources are appended so they count as citations.

For assistants without an adapter (Copilot, the consumer apps themselves), paste or export their answers into a
JSON file and use `import-answers`: the same parsing and metrics apply.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
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


def _post_json(url: str, headers: dict, body: dict, provider: str, timeout: float = 120) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        with e:
            detail = e.read()[:300].decode("utf-8", "replace")
        if e.code in (401, 403):
            raise LiveError(f"{provider} API credentials are missing or invalid") from None
        if e.code == 429:
            raise LiveError(f"{provider} API rate limit or quota reached; run again later") from None
        raise LiveError(f"{provider} API error {e.code}: {detail}") from None
    except (urllib.error.URLError, OSError) as e:
        raise LiveError(f"could not reach the {provider} API: {e}") from None
    except ValueError:
        raise LiveError(f"{provider} API answered with something that is not JSON") from None


class HTTPPlatform(Platform):
    """Shared plumbing: key from the environment, model overridable, a replaceable transport for tests."""

    provider = ""
    key_env = ""
    default_model = ""

    def __init__(self, model: str | None = None, key: str | None = None, post=None):
        self.model = model or os.environ.get(f"AGENT_VISIBILITY_{self.name.upper()}_MODEL", self.default_model)
        self.key = key if key is not None else os.environ.get(self.key_env, "")
        if not self.key:
            raise LiveError(f"the {self.name} platform needs an API key: set {self.key_env}")
        self.post = post or _post_json


class OpenAIPlatform(HTTPPlatform):
    name, provider, key_env, default_model = "openai", "OpenAI", "OPENAI_API_KEY", "gpt-4o"

    def ask(self, prompt: str) -> str:
        res = self.post(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": f"Bearer {self.key}"},
            {"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            self.provider,
        )
        try:
            return res["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError):
            raise LiveError(f"unexpected OpenAI answer: {str(res)[:200]}") from None


class PerplexityPlatform(HTTPPlatform):
    name, provider, key_env, default_model = "perplexity", "Perplexity", "PERPLEXITY_API_KEY", "sonar"

    def ask(self, prompt: str) -> str:
        res = self.post(
            "https://api.perplexity.ai/chat/completions",
            {"Authorization": f"Bearer {self.key}"},
            {"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            self.provider,
        )
        try:
            text = res["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError):
            raise LiveError(f"unexpected Perplexity answer: {str(res)[:200]}") from None
        sources = [c for c in res.get("citations") or [] if isinstance(c, str)]
        sources += [r["url"] for r in res.get("search_results") or [] if isinstance(r, dict) and r.get("url")]
        if sources:
            text += "\n\nSources:\n" + "\n".join(dict.fromkeys(sources))
        return text


class GeminiPlatform(HTTPPlatform):
    name, provider, key_env, default_model = "gemini", "Gemini", "GEMINI_API_KEY", "gemini-2.5-flash"

    def ask(self, prompt: str) -> str:
        res = self.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {"x-goog-api-key": self.key},  # in a header, so the key never lands in a URL or a log
            {"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
            self.provider,
        )
        candidates = res.get("candidates") or []
        if not candidates:
            return ""  # blocked or empty: the brand was not mentioned
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "\n".join(p.get("text", "") for p in parts if isinstance(p, dict))


LIVE = {"openai": OpenAIPlatform, "chatgpt": OpenAIPlatform, "perplexity": PerplexityPlatform, "gemini": GeminiPlatform}


def platform_for(name: str, brands: list[str]) -> Platform:
    if name == "claude":
        return ClaudePlatform()
    if name in LIVE:
        return LIVE[name]()
    if name.startswith("mock-"):
        return MockPlatform(name, brands)
    raise LiveError(
        f"no live adapter for platform {name!r}. Use claude, openai, perplexity, gemini, a 'mock-*' platform, "
        "or capture that "
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
