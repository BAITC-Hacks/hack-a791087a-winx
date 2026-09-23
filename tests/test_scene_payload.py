"""Tests for the private Python-to-3D scene payload prototype."""

import json
import os
import unittest
from copy import deepcopy
from unittest.mock import patch

from citysim.data import load_dataset
from citysim.engine import baseline
from ui.scene import build_scene_payload, validate_district_selection


class ScenePayloadTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.result = baseline(self.dataset)

    def test_payload_preserves_result_values_and_is_json_serializable(self):
        payload = build_scene_payload(self.dataset, self.result)

        self.assertEqual(payload, {
            "schema_version": 1,
            "states": [{
                "id": "baseline",
                "label": "Исходное состояние",
                "is_baseline": True,
                "decisions": [],
                "cost": 0,
                "remaining_budget": 100,
                "score": 52.55768,
                "districts": [
                    {"id": "esil", "name": "Есиль", "indicators": {
                        "T1": 45, "T2": 62, "E1": 68, "E2": 72, "S1": 48,
                        "S2": 55, "B1": 78, "B2": 60, "C1": 75, "C2": 70,
                    }},
                    {"id": "almaty", "name": "Алматы", "indicators": {
                        "T1": 40, "T2": 75, "E1": 50, "E2": 55, "S1": 60,
                        "S2": 65, "B1": 62, "B2": 52, "C1": 50, "C2": 60,
                    }},
                    {"id": "saryarka", "name": "Сарыарка", "indicators": {
                        "T1": 50, "T2": 70, "E1": 42, "E2": 40, "S1": 62,
                        "S2": 68, "B1": 58, "B2": 55, "C1": 45, "C2": 55,
                    }},
                    {"id": "baikonur", "name": "Байконур", "indicators": {
                        "T1": 52, "T2": 68, "E1": 55, "E2": 50, "S1": 58,
                        "S2": 60, "B1": 52, "B2": 58, "C1": 55, "C2": 58,
                    }},
                    {"id": "nura", "name": "Нура", "indicators": {
                        "T1": 55, "T2": 40, "E1": 45, "E2": 65, "S1": 38,
                        "S2": 35, "B1": 55, "B2": 50, "C1": 60, "C2": 50,
                    }},
                ],
                "district_scores": self.result.after.district_scores,
            }],
            "selected_indicator": "S1",
            "selected_district": None,
            "diff_only": False,
        })
        self.assertEqual(json.loads(json.dumps(payload)), payload)

    def test_selectors_round_trip_and_reject_unknown_values(self):
        payload = build_scene_payload(
            self.dataset, self.result, selected_indicator="T2", selected_district="nura"
        )
        self.assertEqual(payload["selected_indicator"], "T2")
        self.assertEqual(payload["selected_district"], "nura")
        for kwargs in (
            {"selected_indicator": "bogus"}, {"selected_indicator": None},
            {"selected_district": "bogus"}, {"selected_district": ["nura"]},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                build_scene_payload(self.dataset, self.result, **kwargs)

    def test_nested_payload_mutations_do_not_change_inputs_or_later_payloads(self):
        original_dataset = deepcopy(self.dataset)
        payload = build_scene_payload(self.dataset, self.result)
        payload["states"][0]["districts"][0]["indicators"]["T1"] = -1
        payload["states"][0]["district_scores"]["esil"] = -1
        payload["states"][0]["decisions"].append({"measure_id": "M1"})

        self.assertEqual(self.dataset, original_dataset)
        second = build_scene_payload(self.dataset, self.result)
        self.assertEqual(second["states"][0]["districts"][0]["indicators"]["T1"], 45)
        self.assertEqual(second["states"][0]["district_scores"]["esil"],
                         self.result.after.district_scores["esil"])
        self.assertEqual(second["states"][0]["decisions"], [])

    def test_payload_contains_no_environment_values(self):
        with patch.dict(os.environ, {"CODEX_SCENE_SECRET": "must-not-leak"}):
            serialized = json.dumps(build_scene_payload(self.dataset, self.result))
        self.assertNotIn("CODEX_SCENE_SECRET", serialized)
        self.assertNotIn("must-not-leak", serialized)

    def test_district_event_returns_only_a_known_id(self):
        self.assertEqual(validate_district_selection({"district_id": "nura"}, self.dataset), "nura")
        for event in (
            None, "district_selected", [], 7, {}, {"district_id": None},
            {"district_id": "missing"}, {"district_id": ["nura"]},
        ):
            with self.subTest(event=event):
                self.assertIsNone(validate_district_selection(event, self.dataset))


if __name__ == "__main__":
    unittest.main()
