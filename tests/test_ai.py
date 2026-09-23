"""Offline guarantees and SDK fallback; never makes an actual API call."""

import unittest
from unittest.mock import patch

from openai import OpenAIError

from citysim.ai import explain_result
from citysim.data import load_dataset
from citysim.engine import baseline


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        self.result = baseline(load_dataset())

    @patch("openai.OpenAI", side_effect=AssertionError("Network is forbidden in demo"))
    def test_demo_even_with_credentials(self, client):
        result = explain_result(self.result, demo_mode=True, api_key="test-only", model="test-model")
        self.assertEqual(result.mode, "demo")
        self.assertIn("52.5577", result.text)
        self.assertIn("Нура", result.text)
        client.assert_not_called()

    @patch("openai.OpenAI", side_effect=AssertionError("Missing configuration must use demo"))
    def test_missing_live_configuration(self, client):
        for key, model in [(None, "test-model"), ("test-only", None)]:
            with self.subTest(key_present=bool(key)):
                result = explain_result(self.result, demo_mode=False, api_key=key, model=model)
                self.assertEqual(result.mode, "demo")
                self.assertTrue(result.warning)
        client.assert_not_called()

    @patch("openai.OpenAI", side_effect=OpenAIError("private provider details"))
    def test_provider_error_is_safe_fallback(self, client):
        result = explain_result(self.result, demo_mode=False, api_key="test-only", model="test-model")
        self.assertEqual(result.mode, "demo")
        self.assertTrue(result.warning)
        self.assertNotIn("private provider details", result.warning)

    @patch("openai.OpenAI")
    def test_empty_response_falls_back(self, client):
        client.return_value.responses.create.return_value.output_text = "   "
        result = explain_result(self.result, demo_mode=False, api_key="test-only", model="test-model")
        self.assertEqual(result.mode, "demo")
        self.assertTrue(result.warning)


if __name__ == "__main__":
    unittest.main()
