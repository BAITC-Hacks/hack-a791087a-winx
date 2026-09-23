"""Offline guarantees and SDK fallback; never makes an actual API call."""

import unittest
from unittest.mock import patch

from openai import OpenAIError

from citysim.ai import explain_result
from citysim.data import load_dataset
from citysim.engine import baseline, simulate
from citysim.models import Decision


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

    def test_demo_explains_reference_scenario_from_engine_values(self):
        result = simulate((
            Decision("M7", "nura"), Decision("M8", "nura"),
            Decision("M10", "nura"), Decision("M12"),
            Decision("M5", "saryarka"),
        ), load_dataset())

        explanation = explain_result(result)

        self.assertEqual(explanation.mode, "demo")
        self.assertIn("Стоимость 95", explanation.text)
        self.assertIn("остаток бюджета 5", explanation.text)
        self.assertIn("52.5577", explanation.text)
        self.assertIn("56.5431", explanation.text)
        self.assertIn("Ncrit: 2 → 0", explanation.text)
        self.assertIn("Нура — S1", explanation.text)
        self.assertIn("Нура — S2", explanation.text)
        self.assertIn("+10.0000", explanation.text)
        self.assertIn("Сарыарка", explanation.text)
        self.assertIn("указаны до ограничения", explanation.text)
        self.assertNotIn("линейный вклад", explanation.text)
        self.assertNotIn("оптимальн", explanation.text.lower())

    def test_demo_reports_negative_indicator_change_candidly(self):
        result = simulate((
            Decision("M9", "nura"), Decision("M11", "nura"),
            Decision("M10", "nura"), Decision("M12"),
            Decision("M4", "saryarka"),
        ), load_dataset())

        explanation = explain_result(result)

        self.assertIn("M11", explanation.text)
        self.assertIn("T1", explanation.text)
        self.assertIn("-1.7500", explanation.text)
        self.assertIn("указаны до ограничения", explanation.text)

    @patch("openai.OpenAI")
    def test_live_request_uses_exact_result_json_and_existing_client_configuration(self, client):
        from dataclasses import asdict
        import json

        result = simulate((
            Decision("M9", "nura"), Decision("M11", "nura"),
            Decision("M10", "nura"), Decision("M12"),
            Decision("M4", "saryarka"),
        ), load_dataset())
        original = json.dumps(asdict(result), ensure_ascii=False)
        client.return_value.responses.create.return_value.output_text = "Факты по сценарию."

        explanation = explain_result(result, demo_mode=False, api_key="test-only", model="test-model")

        self.assertEqual(explanation.mode, "openai")
        client.assert_called_once_with(api_key="test-only", timeout=15, max_retries=0)
        kwargs = client.return_value.responses.create.call_args.kwargs
        self.assertEqual(kwargs["input"], original)
        self.assertEqual(json.dumps(json.loads(kwargs["input"]), ensure_ascii=False), original)
        self.assertEqual(kwargs["store"], False)
        self.assertEqual(json.dumps(asdict(result), ensure_ascii=False), original)


if __name__ == "__main__":
    unittest.main()
