import contextlib
import io
import json
import os
import tempfile
import types
import unittest

from agent_visibility.__main__ import main
from agent_visibility.core import Project
from agent_visibility.live import ClaudePlatform, LiveError, import_answers, platform_for

ROOT = os.path.join(os.path.dirname(__file__), "..", "examples")


class FakeMessages:
    def __init__(self, stop_reason="end_turn"):
        self.calls, self.stop_reason = [], stop_reason

    def create(self, **kwargs):
        self.calls.append(kwargs)
        blocks = [
            types.SimpleNamespace(type="thinking", thinking=""),
            types.SimpleNamespace(type="text", text="1. **Pipely** is affordable."),
        ]
        return types.SimpleNamespace(stop_reason=self.stop_reason, content=blocks)


def fake_client(messages):
    return types.SimpleNamespace(beta=types.SimpleNamespace(messages=messages))


class LiveTests(unittest.TestCase):
    def test_claude_platform_sends_the_bare_question_and_reads_only_text_blocks(self):
        messages = FakeMessages()
        answer = ClaudePlatform(client=fake_client(messages)).ask("best CRM?")
        self.assertEqual(answer, "1. **Pipely** is affordable.")
        call = messages.calls[0]
        self.assertEqual(call["messages"], [{"role": "user", "content": "best CRM?"}])
        self.assertEqual((call["model"], call["fallbacks"]), ("claude-opus-5-5", "default"))
        self.assertNotIn("system", call)  # no steering: the answer is what a buyer would see

    def test_a_refusal_counts_as_not_mentioned(self):
        self.assertEqual(ClaudePlatform(client=fake_client(FakeMessages("refusal"))).ask("x"), "")

    def test_unknown_platforms_are_refused_with_a_way_forward(self):
        self.assertEqual(platform_for("mock-gpt", ["A"]).name, "mock-gpt")
        with self.assertRaises(LiveError) as ctx:
            platform_for("chatgpt", ["A"])
        self.assertIn("import-answers", str(ctx.exception))

    def test_imported_answers_are_scored_like_live_ones(self):
        proj = Project.load(os.path.join(ROOT, "project.json"))
        rows = import_answers(proj, os.path.join(ROOT, "captured-answers.json"))
        chatgpt = rows[0]
        self.assertEqual((chatgpt["platform"], chatgpt["intent"]), ("chatgpt", "category"))
        self.assertEqual(chatgpt["entities"]["Pipely"]["rank"], 2)
        self.assertFalse(rows[1]["entities"]["Pipely"]["mentioned"])
        self.assertIn("g2.com", chatgpt["citations"])

    def test_bad_answer_files_are_rejected(self):
        proj = Project.load(os.path.join(ROOT, "project.json"))
        with tempfile.TemporaryDirectory() as t:
            for i, doc in enumerate(
                (
                    [],
                    {"platform": "x"},
                    [{"platform": "x", "prompt": "p"}],
                    [{"platform": "", "prompt": "p", "answer": "a"}],
                )
            ):
                path = os.path.join(t, f"{i}.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(doc, fh)
                with self.subTest(doc=doc), self.assertRaises(LiveError):
                    import_answers(proj, path)

    def test_cli_import_writes_history_and_reports(self):
        with tempfile.TemporaryDirectory() as t:
            hist = os.path.join(t, "h.jsonl")
            out = io.StringIO()
            argv = ["import-answers", os.path.join(ROOT, "project.json"), os.path.join(ROOT, "captured-answers.json")]
            with contextlib.redirect_stdout(out):
                self.assertEqual(main([*argv, "--history", hist]), 0)
            self.assertIn("chatgpt", out.getvalue())
            with open(hist, encoding="utf-8") as fh:
                self.assertEqual(len(fh.readlines()), 2)


if __name__ == "__main__":
    unittest.main()
