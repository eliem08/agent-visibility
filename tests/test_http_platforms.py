"""OpenAI, Perplexity and Gemini adapters: request shape, answer parsing, citations and errors (no network)."""

import io
import os
import unittest
import urllib.error
from unittest import mock

from agent_visibility.core import parse_answer
from agent_visibility.live import (
    GeminiPlatform,
    LiveError,
    OpenAIPlatform,
    PerplexityPlatform,
    _post_json,
    platform_for,
)


class Recorder:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def __call__(self, url, headers, body, provider):
        self.calls.append((url, headers, body, provider))
        return self.answer


class AdapterTests(unittest.TestCase):
    def test_openai(self):
        rec = Recorder({"choices": [{"message": {"role": "assistant", "content": "1. Pipely\n2. Acme CRM"}}]})
        answer = OpenAIPlatform(model="m1", key="k", post=rec).ask("best CRM?")
        self.assertEqual(answer, "1. Pipely\n2. Acme CRM")
        url, headers, body, _ = rec.calls[0]
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(headers, {"Authorization": "Bearer k"})
        self.assertEqual(body, {"model": "m1", "messages": [{"role": "user", "content": "best CRM?"}]})

    def test_perplexity_citations_become_citations(self):
        rec = Recorder(
            {
                "choices": [{"message": {"content": "Pipely is popular [1]."}}],
                "citations": ["https://www.g2.com/pipely", "https://pipely.com"],
                "search_results": [{"title": "x", "url": "https://pipely.com"}, {"url": "https://reddit.com/r/crm"}],
            }
        )
        answer = PerplexityPlatform(key="k", post=rec).ask("best CRM?")
        self.assertEqual(rec.calls[0][2]["model"], "sonar")
        parsed = parse_answer(answer, {"Pipely": ["Pipely"]})
        self.assertEqual(parsed["citations"], ["g2.com", "pipely.com", "reddit.com"])
        self.assertTrue(parsed["entities"]["Pipely"]["mentioned"])

    def test_gemini_key_in_header_and_empty_candidates(self):
        rec = Recorder({"candidates": [{"content": {"parts": [{"text": "Try Pipely."}, {"text": "Or Acme."}]}}]})
        g = GeminiPlatform(model="gem-x", key="secret", post=rec)
        self.assertEqual(g.ask("q"), "Try Pipely.\nOr Acme.")
        url, headers, body, _ = rec.calls[0]
        self.assertTrue(url.endswith("/models/gem-x:generateContent"))
        self.assertNotIn("secret", url)
        self.assertEqual(headers, {"x-goog-api-key": "secret"})
        self.assertEqual(body["contents"][0]["parts"][0]["text"], "q")
        self.assertEqual(
            GeminiPlatform(key="k", post=Recorder({"promptFeedback": {"blockReason": "SAFETY"}})).ask("q"), ""
        )

    def test_keys_and_models_from_the_environment(self):
        env = {"OPENAI_API_KEY": "", "PERPLEXITY_API_KEY": "pk", "AGENT_VISIBILITY_PERPLEXITY_MODEL": "sonar-pro"}
        with mock.patch.dict(os.environ, env):
            with self.assertRaisesRegex(LiveError, "OPENAI_API_KEY"):
                platform_for("chatgpt", [])
            p = platform_for("perplexity", [])
            self.assertEqual((p.key, p.model), ("pk", "sonar-pro"))

    def test_http_errors_become_plain_messages(self):
        def raiser(code):
            def urlopen(req, timeout):
                raise urllib.error.HTTPError(req.full_url, code, "x", {}, io.BytesIO(b'{"error": "nope"}'))

            return urlopen

        for code, msg in ((401, "credentials"), (429, "rate limit"), (500, "error 500")):
            with mock.patch("urllib.request.urlopen", raiser(code)), self.assertRaisesRegex(LiveError, msg):
                _post_json("https://api.example.com", {}, {}, "Example")
        bad = OpenAIPlatform(key="k", post=Recorder({"error": "x"}))
        with self.assertRaisesRegex(LiveError, "unexpected OpenAI"):
            bad.ask("q")


if __name__ == "__main__":
    unittest.main()
