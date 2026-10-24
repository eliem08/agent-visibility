# agent-visibility

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
