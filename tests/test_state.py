"""Immutable scenario-state transitions around engine snapshots."""

import unittest
from dataclasses import FrozenInstanceError

from citysim.data import load_dataset
from citysim.engine import baseline, simulate
from citysim.models import Decision
from ui.state import ScenarioState, draft_matches_saved, save_a, set_draft


REFERENCE = (
    Decision("M7", "nura"), Decision("M8", "nura"), Decision("M10", "nura"),
    Decision("M12"), Decision("M5", "saryarka"),
)
CHEAPEST = (
    Decision("M9", "nura"), Decision("M11", "nura"), Decision("M10", "nura"),
    Decision("M12"), Decision("M4", "saryarka"),
)


class ScenarioStateTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.result = simulate(REFERENCE, self.dataset)

    def test_save_a_keeps_real_budget_and_isolates_result_from_input(self):
        state = save_a(ScenarioState(), self.result)

        self.assertEqual((state.plan_a.cost, state.plan_a.remaining_budget), (95, 5))
        self.assertAlmostEqual(state.plan_a.after.score, 56.54307, places=7)
        state.plan_a.after.district_scores["nura"] = -1
        state.plan_a.indicator_deltas["nura"]["B1"] = -1
        self.assertAlmostEqual(self.result.after.score, 56.54307, places=7)
        self.assertGreater(self.result.after.district_scores["nura"], 0)
        self.assertGreater(self.result.indicator_deltas["nura"]["B1"], -1)

    def test_draft_change_keeps_a_snapshot_isolated_from_previous_state(self):
        previous = save_a(ScenarioState(), self.result)
        updated = set_draft(previous, [Decision("M1", "esil")])

        self.assertEqual(updated.draft, (Decision("M1", "esil"),))
        self.assertEqual(updated.plan_a.cost, 95)
        previous.plan_a.after.district_scores["nura"] = -1
        self.assertGreater(updated.plan_a.after.district_scores["nura"], 0)
        updated.plan_a.indicator_deltas["nura"]["B1"] = -1
        self.assertGreater(previous.plan_a.indicator_deltas["nura"]["B1"], -1)

    def test_saving_a_replaces_a_clears_b_and_keeps_draft(self):
        alternate = simulate(CHEAPEST, self.dataset)
        old_a = simulate(CHEAPEST, self.dataset)
        state = ScenarioState(draft=REFERENCE, plan_a=old_a, plan_b=alternate)
        result = save_a(state, self.result)

        self.assertEqual(result.draft, REFERENCE)
        self.assertEqual(result.plan_a.cost, 95)
        self.assertEqual(result.plan_a.decisions, self.result.decisions)
        self.assertIsNone(result.plan_b)

    def test_draft_match_ignores_order_but_counts_every_decision(self):
        saved = save_a(ScenarioState(), self.result)
        self.assertTrue(draft_matches_saved(set_draft(saved, reversed(REFERENCE))))
        self.assertFalse(draft_matches_saved(set_draft(saved, REFERENCE[:-1])))
        self.assertFalse(draft_matches_saved(set_draft(saved, (*REFERENCE[:-1], REFERENCE[0]))))

    def test_baseline_cannot_be_saved_as_a_five_decision_plan(self):
        with self.assertRaises(ValueError):
            save_a(ScenarioState(), baseline(self.dataset))

    def test_state_fields_cannot_be_reassigned(self):
        with self.assertRaises(FrozenInstanceError):
            ScenarioState().draft = REFERENCE


if __name__ == "__main__":
    unittest.main()
