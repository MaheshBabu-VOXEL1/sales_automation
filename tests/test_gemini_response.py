"""No live provider calls: preserve complete answers and reject unsafe partial output."""
import io
import json
import os
import unittest
from unittest.mock import patch

import ai_draft
import draft_outputs
from provider_search import GeminiResponseError, ProviderError, gemini_failure, gemini_json


def envelope(parts, **kwargs):
    return {"candidates": [{"content": {"parts": parts}, **kwargs}]}


class GeminiResponseTest(unittest.TestCase):
    def test_thought_parts_are_not_mistaken_for_the_answer(self):
        result = envelope([{"text": "private reasoning", "thought": True},
                           {"text": '{"title":"Scan-to-BIM","body":"Hello"}'}], finishReason="STOP")
        self.assertEqual(gemini_json(result)["body"], "Hello")

    def test_answer_split_across_parts_is_combined(self):
        self.assertEqual(gemini_json(envelope([{"text": '{"title":"Example",'}, {"text": '"body":"Hello"}'}]))["body"], "Hello")

    def test_one_json_fence_is_accepted(self):
        self.assertEqual(gemini_json(envelope([{"text": '```json\n{"body":"Hello"}\n```'}]))["body"], "Hello")

    def test_non_completed_answers_are_rejected_even_if_the_json_looks_valid(self):
        for reason in ("MAX_TOKENS", "SAFETY", "RECITATION", "OTHER"):
            with self.subTest(reason=reason), self.assertRaises(GeminiResponseError):
                gemini_json(envelope([{"text": '{"body":"Hello"}'}], finishReason=reason))

    def test_empty_blocked_and_malformed_answers_have_safe_diagnostics(self):
        examples = [None, {}, {"promptFeedback": {"blockReason": "SAFETY"}},
                    envelope([]), envelope([{"thought": True, "text": "SECRET"}]),
                    envelope([{"text": '{"body":"SECRET'}]),
                    envelope([{"text": 'Before {"body":"SECRET"} after'}]),
                    envelope([{"text": '[{"body":"SECRET"}]'}])]
        for value in examples:
            with self.subTest(value=value), self.assertRaises(GeminiResponseError) as captured:
                gemini_json(value)
            self.assertNotIn("SECRET", gemini_failure(captured.exception))

    def test_output_limit_is_distinguished_from_json_failure(self):
        with self.assertRaises(GeminiResponseError) as captured:
            gemini_json(envelope([], finishReason="MAX_TOKENS"))
        self.assertIn("output-token limit", gemini_failure(captured.exception))

    def test_draft_generator_reads_final_answer_without_another_request(self):
        payload = envelope([{"thought": True, "text": "Thinking"},
                            {"text": '{"title":"Scan-to-BIM", "body":"Would a call about Scan-to-BIM help?"}'}])
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(payload).encode())) as opened:
            result = draft_outputs.generate("linkedin_message", "bim", {"campaign_service_focus": "Scan-to-BIM"}, "")
        self.assertIn("Scan-to-BIM", result["body"])
        self.assertEqual(opened.call_count, 1)

    def test_invalid_email_field_types_are_rejected(self):
        payload = envelope([{"text": '{"subject": null,"body": {"nested":"text"}}'}])
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(payload).encode())):
            with self.assertRaises(ProviderError):
                ai_draft.write_draft({"company": "Example"}, "bim", "First contact")

    def test_failed_response_is_not_retried(self):
        payload = envelope([{"text": '{"title":"Incomplete'}], finishReason="MAX_TOKENS")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}), patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(payload).encode())) as opened:
            with self.assertRaisesRegex(ProviderError, "output-token limit"):
                draft_outputs.generate("room", "bim", {}, "")
        self.assertEqual(opened.call_count, 1)
