"""Immutable scenario-state transitions around engine snapshots."""

import unittest
from dataclasses import FrozenInstanceError

from citysim.data import load_dataset
from citysim.engine import baseline, simulate
from citysim.models import Decision, Explanation
from citysim.review_models import CandidateCheck, ReviewConstraints, ReviewResult
from ui.state import (
    ScenarioState, accept_b, draft_matches_saved, keep_a, save_a, save_b,
    save_review, set_constraints, set_draft,
)


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


class ReviewStateTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.a = simulate(REFERENCE, self.dataset)
        self.b = simulate(CHEAPEST, self.dataset)
        self.explanation = Explanation("review notes", "demo")

    def review(self, source=None, best=None, constraints=None, status="incomplete"):
        source = self.a if source is None else source
        best = self.b if best is None else best
        constraints = ReviewConstraints() if constraints is None else constraints
        check = CandidateCheck(best.decisions, (), best)
        return ReviewResult(source, best, (check,), status, "improved", constraints)

    def test_save_b_copies_manual_result_and_clears_review(self):
        state = save_a(ScenarioState(), self.a)
        state = save_review(state, self.review(), self.explanation)
        updated = save_b(state, self.b)

        self.assertEqual(updated.plan_b.decisions, self.b.decisions)
        self.assertIsNone(updated.review)
        self.assertIsNone(updated.review_explanation)
        updated.plan_b.after.district_scores["nura"] = -1
        self.assertGreater(self.b.after.district_scores["nura"], 0)

    def test_save_b_requires_saved_a_and_nonbaseline(self):
        with self.assertRaises(ValueError):
            save_b(ScenarioState(), self.b)
        with self.assertRaises(ValueError):
            save_b(save_a(ScenarioState(), self.a), baseline(self.dataset))

    def test_save_review_rejects_stale_source_and_constraints(self):
        state = save_a(ScenarioState(), self.a)
        with self.assertRaises(ValueError):
            save_review(state, self.review(source=self.b), self.explanation)
        with self.assertRaises(ValueError):
            save_review(state, self.review(constraints=ReviewConstraints(max_changes=0)), self.explanation)

    def test_save_review_keeps_best_even_when_incomplete_and_isolates_copy(self):
        state = save_a(ScenarioState(), self.a)
        review = self.review()
        updated = save_review(state, review, self.explanation)

        self.assertEqual(updated.review.status, "incomplete")
        self.assertEqual(updated.plan_b.decisions, self.b.decisions)
        self.assertIsNot(updated.plan_b, state.plan_a)
        updated.plan_b.after.district_scores["nura"] = -1
        self.assertGreater(review.best.after.district_scores["nura"], 0)
        self.assertGreater(state.plan_a.after.district_scores["nura"], 0)

    def test_set_draft_preserves_and_deep_copies_review_state(self):
        state = save_a(ScenarioState(), self.a)
        state = save_review(state, self.review(), self.explanation)
        updated = set_draft(state, (Decision("M1", "esil"),))

        self.assertEqual(updated.review, state.review)
        self.assertEqual(updated.review_explanation, self.explanation)
        updated.review.best.after.district_scores["nura"] = -1
        self.assertGreater(state.review.best.after.district_scores["nura"], 0)

    def test_constraints_validate_and_equivalent_lock_order_preserves_content(self):
        state = save_a(ScenarioState(), self.a)
        locked = (REFERENCE[0], REFERENCE[1])
        state = set_constraints(state, ReviewConstraints(locked=locked))
        state = save_review(state, self.review(constraints=ReviewConstraints(locked=locked)), self.explanation)
        reordered = set_constraints(state, ReviewConstraints(locked=tuple(reversed(locked))))
        self.assertEqual(reordered.review, state.review)
        self.assertEqual(reordered.plan_b, state.plan_b)
        for invalid in (
            ReviewConstraints(max_changes=True),
            ReviewConstraints(max_changes=2),
            ReviewConstraints(locked=(REFERENCE[0], REFERENCE[0])),
            ReviewConstraints(locked=(Decision("M1", "esil"),)),
            object(),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                set_constraints(state, invalid)

    def test_changed_constraints_clear_review_explanation_and_b(self):
        state = save_a(ScenarioState(), self.a)
        state = save_review(state, self.review(), self.explanation)
        changed = set_constraints(state, ReviewConstraints(max_changes=0))
        self.assertIsNone(changed.review)
        self.assertIsNone(changed.review_explanation)
        self.assertIsNone(changed.plan_b)
        self.assertEqual(changed.plan_a.decisions, self.a.decisions)

    def test_accept_b_promotes_copy_to_a_and_resets_review_controls(self):
        state = save_a(ScenarioState(draft=REFERENCE), self.a)
        state = set_constraints(state, ReviewConstraints(max_changes=0))
        state = save_review(state, self.review(constraints=ReviewConstraints(max_changes=0)), self.explanation)
        accepted = accept_b(state)

        self.assertEqual(accepted.draft, self.b.decisions)
        self.assertEqual(accepted.plan_a.decisions, self.b.decisions)
        self.assertIsNone(accepted.plan_b)
        self.assertIsNone(accepted.review)
        self.assertIsNone(accepted.review_explanation)
        self.assertEqual(accepted.constraints, ReviewConstraints())
        accepted.plan_a.after.district_scores["nura"] = -1
        self.assertGreater(self.b.after.district_scores["nura"], 0)

    def test_keep_a_discards_b_and_review_but_keeps_draft_and_constraints(self):
        constraints = ReviewConstraints(locked=(REFERENCE[0],), max_changes=0)
        state = save_a(ScenarioState(draft=CHEAPEST), self.a)
        state = set_constraints(state, constraints)
        state = save_review(state, self.review(constraints=constraints), self.explanation)
        kept = keep_a(state)

        self.assertEqual(kept.plan_a.decisions, self.a.decisions)
        self.assertEqual(kept.draft, CHEAPEST)
        self.assertEqual(kept.constraints, constraints)
        self.assertIsNone(kept.plan_b)
        self.assertIsNone(kept.review)
        self.assertIsNone(kept.review_explanation)

    def test_accept_and_keep_require_b_and_a(self):
        with self.assertRaises(ValueError):
            accept_b(ScenarioState())
        with self.assertRaises(ValueError):
            keep_a(ScenarioState())


if __name__ == "__main__":
    unittest.main()
