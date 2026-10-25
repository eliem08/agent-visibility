<!-- sell-kit:start -->
# Agent Visibility

[![CI](https://github.com/eliem08/agent-visibility/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/agent-visibility/actions/workflows/ci.yml)

> **Track how AI assistants recommend your brand.**

**Who it's for:** Marketing and SEO teams as search moves to AI assistants.

**The problem:** Buyers now ask assistants what to buy, and brands have no idea whether they are mentioned, ranked or dismissed.

**What you get:** Measure share of voice, rank, sentiment and citations for your brand across assistants and prompts, tracked over time.

## Quickstart

Customers receive a release archive with the wheel and the examples. Python 3.10+ and no other dependencies.

```bash
pip install agent_visibility-0.1.0-py3-none-any.whl
agent-visibility run examples/project.json --history h.jsonl
agent-visibility run examples/project.json --history h.jsonl
agent-visibility report h.jsonl
```

## Web app and API

Every command is also a JSON API endpoint and a browser form, served by the built-in web app.

```bash
agent-visibility-web --port 8000          # then open http://127.0.0.1:8000
agent-visibility-web keys create --label "first customer"   # prints an API key (stored hashed)
docker build -t agent-visibility . && docker run -p 8000:8000 -e API_KEYS=sk_... -v agent-visibility-data:/data agent-visibility
```

Every API call needs `Authorization: Bearer <key>` once any key exists; a server on a public address refuses to start without one. Calls are rate-limited per key (60/min, `--rate`) and metered: `agent-visibility-web usage` prints calls per key for billing.

Endpoints: `POST /api/run`, `POST /api/report`, plus `GET /healthz` and `GET /api/spec` (machine-readable field list).
Files are sent as `{"name": ..., "content": ...}`, folders as `{"files": [...]}` or a base64 zip.

## Pricing

Every plan starts with a 14-day free trial. Prices in USD, billed monthly unless noted.

| Plan | Price | Includes |
|---|---|---|
| **Starter** | $49 per month | 1 brand; 50 prompts; Weekly runs |
| **Growth** | $249 per month | 5 brands; 500 prompts; Competitor tracking |
| **Agency** | $799 per month | Unlimited brands; White-label reports; Priority support |

To start a trial or buy a plan, email **sales@YOUR-DOMAIN.com**.

## Licence

Proprietary. Copyright (c) 2026 eliem08. All rights reserved. Use requires a paid plan or an active trial; see [LICENSE](LICENSE).
<!-- sell-kit:end -->

## What it does

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
