import pathlib
import unittest
from datetime import datetime, timezone

from agent_visibility import MockPlatform, Project, alerts, metrics, parse_answer, run

EX = pathlib.Path(__file__).resolve().parent.parent / "examples" / "project.json"
ENTS = {"Pipely": ["Pipely", "Pipely CRM"], "HubSpot": ["HubSpot"], "Attio": ["Attio"]}

ANSWER = """For a small agency I'd look at:
1. **HubSpot** - powerful but expensive once you scale.
2. **Pipely CRM** - great, intuitive and affordable.
3. Folk
Source: https://www.g2.com/crm and https://pipely.com/pricing"""


class Tests(unittest.TestCase):
    def test_parse(self):
        p = parse_answer(ANSWER, ENTS)
        self.assertEqual(p["entities"]["Pipely"], {"mentioned": True, "rank": 2, "sentiment": 1})
        self.assertEqual(p["entities"]["HubSpot"]["rank"], 1)
        self.assertFalse(p["entities"]["Attio"]["mentioned"])
        self.assertEqual(p["citations"], ["g2.com", "pipely.com"])

    def test_prose_fallback_rank_and_word_boundary(self):
        p = parse_answer("Attio is nice. HubSpot is fine. Pipelyx is not a brand.", ENTS)
        self.assertEqual(p["entities"]["Attio"]["rank"], 1)
        self.assertFalse(p["entities"]["Pipely"]["mentioned"])

    def test_run_and_metrics_deterministic(self):
        proj = Project.load(str(EX))
        plats = [MockPlatform(p, [proj.brand, *proj.competitors]) for p in proj.platforms]
        now = datetime(2026, 10, 24, tzinfo=timezone.utc)
        rows = run(proj, plats, now)
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows, run(proj, plats, now))
        m = metrics(rows, "Pipely")
        self.assertEqual(set(m["by_platform"]), {"mock-gpt", "mock-claude"})
        self.assertTrue(0 <= m["overall"]["share_of_voice"] <= 1)

    def test_alerts(self):
        prev = {"by_platform": {"x": {"top3_rate": 0.5, "share_of_voice": 0.3, "mention_rate": 0.6}}}
        cur = {"by_platform": {"x": {"top3_rate": 0.0, "share_of_voice": 0.0, "mention_rate": 0.0}}}
        self.assertEqual(len(alerts(prev, cur)), 3)


if __name__ == "__main__":
    unittest.main()
