"""Track brand visibility in AI agent answers: parsing, metrics, history and alerts."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

__all__ = ["Platform", "MockPlatform", "Project", "parse_answer", "run", "metrics", "alerts", "load_history"]

POSITIVE = {
    "best",
    "great",
    "excellent",
    "recommend",
    "love",
    "easy",
    "affordable",
    "powerful",
    "intuitive",
    "top",
    "solid",
    "fast",
}
NEGATIVE = {
    "expensive",
    "clunky",
    "slow",
    "limited",
    "buggy",
    "avoid",
    "poor",
    "complicated",
    "outdated",
    "lacks",
    "worse",
}
URL_RE = re.compile(r"https?://([^/\s)\]]+)")


class Platform:
    name = "base"

    def ask(self, prompt: str) -> str:
        raise NotImplementedError


class MockPlatform(Platform):
    """Deterministic fake answers so the pipeline can be exercised without API keys."""

    def __init__(self, name: str, brands: list[str]):
        self.name, self.brands = name, brands

    def ask(self, prompt: str) -> str:
        seed = int(hashlib.sha256(f"{self.name}|{prompt}".encode()).hexdigest(), 16)
        order = sorted(self.brands, key=lambda b: hashlib.sha256(f"{seed}{b}".encode()).hexdigest())
        k = 3 + seed % 2
        lines = [f"Here are good options for: {prompt}"]
        for i, b in enumerate(order[:k], 1):
            adj = [
                "is a great, intuitive pick",
                "is powerful but can be expensive",
                "is affordable and easy to set up",
                "is solid for small teams",
            ][(seed >> i) % 4]
            lines.append(f"{i}. **{b}** {adj}. See https://{b.lower().replace(' ', '')}.com/pricing")
        lines.append("Sources: https://www.g2.com/categories/crm https://www.reddit.com/r/smallbusiness")
        return "\n".join(lines)


@dataclass
class Project:
    brand: str
    aliases: list = field(default_factory=list)
    competitors: list = field(default_factory=list)
    prompts: list = field(default_factory=list)
    platforms: list = field(default_factory=list)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as fh:
            return cls(**json.load(fh))

    def names(self) -> dict[str, list[str]]:
        return {self.brand: [self.brand, *self.aliases], **{c: [c] for c in self.competitors}}


def _find(text: str, names: list[str]) -> int:
    best = -1
    for n in names:
        m = re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text, re.I)
        if m and (best < 0 or m.start() < best):
            best = m.start()
    return best


def parse_answer(answer: str, entities: dict[str, list[str]]) -> dict:
    list_items = [l for l in answer.splitlines() if re.match(r"^\s*(\d+[.)]|[-*•])\s+", l)]
    out = {}
    first_pos = {}
    for ent, names in entities.items():
        pos = _find(answer, names)
        if pos < 0:
            out[ent] = {"mentioned": False, "rank": None, "sentiment": 0}
            continue
        first_pos[ent] = pos
        rank = next((i for i, l in enumerate(list_items, 1) if _find(l, names) >= 0), None)
        window = answer[max(0, pos - 80) : pos + 160].lower()
        words = re.findall(r"[a-z]+", window)
        sentiment = sum(w in POSITIVE for w in words) - sum(w in NEGATIVE for w in words)
        out[ent] = {"mentioned": True, "rank": rank, "sentiment": max(-1, min(1, sentiment))}
    if not list_items:  # fall back to order of first mention
        for i, ent in enumerate(sorted(first_pos, key=first_pos.get), 1):
            out[ent]["rank"] = i
    citations = sorted({d.lower().removeprefix("www.") for d in URL_RE.findall(answer)})
    return {"entities": out, "citations": citations}


def run(project: Project, platforms: list[Platform], now: datetime | None = None) -> list[dict]:
    ts = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    ents = project.names()
    rows = []
    for p in platforms:
        for pr in project.prompts:
            ans = p.ask(pr["text"])
            parsed = parse_answer(ans, ents)
            rows.append({"ts": ts, "platform": p.name, "prompt": pr["text"], "intent": pr.get("intent", ""), **parsed})
    return rows


def metrics(rows: list[dict], brand: str) -> dict:
    def calc(rs):
        n = len(rs)
        if not n:
            return {}
        b = [r["entities"][brand] for r in rs]
        mentioned = [x for x in b if x["mentioned"]]
        ranks = [x["rank"] for x in mentioned if x["rank"]]
        total_mentions = sum(1 for r in rs for e in r["entities"].values() if e["mentioned"])
        cites = Counter(c for r in rs for c in r["citations"])
        return {
            "answers": n,
            "mention_rate": round(len(mentioned) / n, 3),
            "share_of_voice": round(len(mentioned) / total_mentions, 3) if total_mentions else 0.0,
            "avg_rank": round(sum(ranks) / len(ranks), 2) if ranks else None,
            "top3_rate": round(sum(1 for r in ranks if r <= 3) / n, 3),
            "sentiment": round(sum(x["sentiment"] for x in mentioned) / len(mentioned), 2) if mentioned else 0.0,
            "top_citations": cites.most_common(5),
        }

    by_platform = defaultdict(list)
    for r in rows:
        by_platform[r["platform"]].append(r)
    return {"overall": calc(rows), "by_platform": {k: calc(v) for k, v in sorted(by_platform.items())}}


def alerts(prev: dict, cur: dict, sov_drop: float = 0.05) -> list[str]:
    out = []
    for plat, m in cur["by_platform"].items():
        p = prev.get("by_platform", {}).get(plat)
        if not p:
            continue
        if p["top3_rate"] > 0 and m["top3_rate"] == 0:
            out.append(f"{plat}: dropped out of the top 3 on every prompt")
        if p["share_of_voice"] - m["share_of_voice"] >= sov_drop:
            out.append(f"{plat}: share of voice fell {p['share_of_voice']:.0%} -> {m['share_of_voice']:.0%}")
        if p["mention_rate"] > 0 and m["mention_rate"] == 0:
            out.append(f"{plat}: no longer mentioned at all")
    return out


def load_history(path: str) -> dict[str, list[dict]]:
    runs = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                runs[r["ts"]].append(r)
    return dict(sorted(runs.items()))
