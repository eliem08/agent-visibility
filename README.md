# agent-visibility

[![CI](https://github.com/eliem08/agent-visibility/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/agent-visibility/actions/workflows/ci.yml)

> **SEMrush for personal agent platforms** — track how agents recommend your brand.

SEO tracked your rank on Google. Now customers ask ChatGPT, Claude,
Perplexity, Gemini and personal agent platforms "what's the best CRM for a
5-person agency?". If you're not in the answer, you don't exist.
`agent-visibility` runs your buyer prompts across platforms on a schedule
and tracks share of voice, rank, sentiment and cited sources over time.

## What the MVP does

- **Project config**: brand + aliases, competitors, prompt set (with intent tags), platforms
- **Platform adapters** behind one interface; ships with a deterministic `MockPlatform`
  (plug in real APIs by implementing `Platform.ask(prompt) -> str`)
- **Answer parsing**:
  - brand / competitor **mentions** (alias-aware, word-boundary matching)
  - **rank** in numbered / bulleted recommendation lists (or order of first mention)
  - **sentiment** around the mention (lexicon window)
  - **citations**: domains of URLs in the answer
- **Metrics** per platform and overall: mention rate, share of voice, average rank,
  top-3 rate, sentiment, top cited domains
- **History** (JSONL) + **alerts** when the brand drops out of the top 3 or loses
  share of voice vs. the previous run

## Quickstart

```bash
pip install -e .
agent-visibility run examples/project.json --history history.jsonl
agent-visibility report history.jsonl
```

## Roadmap

- Real adapters (OpenAI, Anthropic, Perplexity, Gemini APIs; browser capture for consumer apps)
- Prompt discovery: generate the buyer questions people actually ask, by persona
- "Why not us?" analysis: which sources the agents cite, and content gaps to fill

## Development

Zero runtime dependencies; Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m unittest discover -s tests -t .           # unit + CLI smoke tests
ruff check . && ruff format --check .               # lint + format
```

```
agent_visibility/core.py       domain logic (pure, importable, fully tested)
agent_visibility/__main__.py   CLI (`agent-visibility ...` / `python -m agent_visibility ...`)
tests/                unit tests + generated CLI smoke tests
examples/             sample inputs used by the docs and smoke tests
```

CI runs lint and tests on Ubuntu and Windows across Python 3.10, 3.12 and 3.13.
Design, data model, trade-offs and production path: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

Part of the [agent-economy](https://github.com/eliem08/agent-economy) portfolio (idea #38).
