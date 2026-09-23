"""Offline guarantees and SDK fallback; never makes an actual API call."""

import unittest
from dataclasses import asdict, replace
from unittest.mock import patch

from openai import OpenAIError

from citysim.ai import _explanation_payload, explain_result
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
        client.return_value.responses.create.return_value.status = "completed"
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
        self.assertIn("Число показателей ниже 40 (Ncrit): 2 → 0", explanation.text)
        self.assertIn("Нура — школы и детсады", explanation.text)
        self.assertIn("Нура — поликлиники и первичная медпомощь", explanation.text)
        self.assertIn("+10.0000", explanation.text)
        self.assertIn("Сарыарка", explanation.text)
        self.assertIn("Изменения показывают фактическое значение после мер", explanation.text)
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
        self.assertIn("разгрузка дорог", explanation.text)
        self.assertIn("-1.7500", explanation.text)
        self.assertIn("Среди учтённых эффектов есть отрицательные", explanation.text)

    @patch("openai.OpenAI")
    def test_live_request_uses_exact_result_json_and_existing_client_configuration(self, client):
        from dataclasses import asdict
        import json

        result = simulate((
            Decision("M7", "nura"), Decision("M8", "nura"),
            Decision("M10", "nura"), Decision("M12"),
            Decision("M5", "saryarka"),
        ), load_dataset())
        original = json.loads(json.dumps(asdict(result), ensure_ascii=False))
        client.return_value.responses.create.return_value.status = "completed"
        client.return_value.responses.create.return_value.output_text = "Факты по сценарию."

        explanation = explain_result(result, demo_mode=False, api_key="test-only", model="test-model")

        self.assertEqual(explanation.mode, "openai")
        client.assert_called_once_with(api_key="test-only", timeout=15, max_retries=0)
        kwargs = client.return_value.responses.create.call_args.kwargs
        payload = json.loads(kwargs["input"])
        for field, value in original.items():
            self.assertEqual(payload[field], value)
        self.assertEqual(payload["districts_before"][4]["indicators"]["S1"], 38)
        self.assertEqual(payload["districts_before"][4]["indicators"]["S2"], 35)
        self.assertEqual(len(payload["critical_indicators_before"]), 2)
        self.assertEqual(payload["critical_indicators_after"], [])
        self.assertEqual(
            {(row["district_id"], row["indicator"], row["value"])
             for row in payload["critical_indicators_before"]},
            {("nura", "S1", 38), ("nura", "S2", 35)},
        )
        self.assertEqual(payload["indicator_names"]["S1"], "школы и детсады")
        self.assertEqual(payload["measure_names"]["M7"], "школа + детсад")
        self.assertEqual(kwargs["store"], False)
        self.assertEqual(kwargs["max_output_tokens"], 700)
        self.assertNotIn("reasoning", kwargs)
        self.assertEqual(json.loads(json.dumps(asdict(result), ensure_ascii=False)), original)

    def test_live_explanation_context_preserves_baseline_values(self):
        import json

        payload = json.loads(json.dumps(_explanation_payload(self.result), ensure_ascii=False))
        raw_result = json.loads(json.dumps(asdict(self.result), ensure_ascii=False))
        for field, value in raw_result.items():
            self.assertEqual(payload[field], value)
        self.assertEqual(payload["districts_before"], [
            {"id": district.id, "name": district.name,
             "indicators": district.indicators}
            for district in self.result.districts_after
        ])
        self.assertEqual(len(payload["critical_indicators_before"]), 2)
        self.assertEqual(payload["critical_indicators_before"], payload["critical_indicators_after"])
        self.assertEqual(json.loads(json.dumps(payload, ensure_ascii=False)), payload)

    def test_live_explanation_context_reconstructs_a_clipped_indicator(self):
        dataset = load_dataset()
        districts = tuple(
            replace(district, indicators={**district.indicators, "T1": 98})
            if district.id == "esil" else district
            for district in dataset.districts
        )
        dataset = replace(dataset, districts=districts)
        result = simulate((
            Decision("M2"), Decision("M4", "saryarka"),
            Decision("M7", "nura"), Decision("M10", "almaty"),
            Decision("M12"),
        ), dataset)

        payload = _explanation_payload(result)

        self.assertEqual(payload["districts_before"][0]["indicators"]["T1"], 98)
        self.assertEqual(result.districts_after[0].indicators["T1"], 100)

    def test_luna_request_uses_no_reasoning_and_larger_explanation_budget(self):
        for model in ("gpt-6-luna", "test-model", "gpt-4.1", "gpt-6-astra"):
            with self.subTest(model=model), patch("openai.OpenAI") as client:
                client.return_value.responses.create.return_value.status = "completed"
                client.return_value.responses.create.return_value.output_text = "Факты по сценарию."
                result = explain_result(
                    self.result, demo_mode=False, api_key="test-only", model=model,
                )
                self.assertEqual(result.mode, "openai")
                kwargs = client.return_value.responses.create.call_args.kwargs
                self.assertEqual(kwargs["max_output_tokens"], 1600 if model == "gpt-6-luna" else 700)
                if model == "gpt-6-luna":
                    self.assertEqual(kwargs["reasoning"], {"effort": "none"})
                else:
                    self.assertNotIn("reasoning", kwargs)

    @patch("openai.OpenAI")
    def test_incomplete_partial_response_falls_back_to_demo(self, client):
        client.return_value.responses.create.return_value.status = "incomplete"
        client.return_value.responses.create.return_value.output_text = "Частичный ответ"

        result = explain_result(
            self.result, demo_mode=False, api_key="test-only", model="gpt-6-luna",
        )

        self.assertEqual(result.mode, "demo")
        self.assertTrue(result.warning)
        self.assertIn("52.5577", result.text)


if __name__ == "__main__":
    unittest.main()
