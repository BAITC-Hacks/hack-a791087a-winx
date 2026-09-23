"""Executable C0 rules shared by the future numerical and AI reviewers."""

import json
import unittest
from copy import deepcopy
from dataclasses import asdict, replace

from citysim.data import load_dataset
from citysim.engine import baseline, simulate
from citysim.models import Decision, ValidationIssue
from citysim.review_models import (
    EPS, CandidateCheck, ReviewConstraints, ReviewResult,
    check_candidate_constraints, classify_outcome, validate_review_input,
)


REFERENCE = (
    Decision("M7", "nura"), Decision("M8", "nura"), Decision("M10", "nura"),
    Decision("M12"), Decision("M5", "saryarka"),
)


class ReviewInputTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.source = simulate(REFERENCE, self.dataset)

    def test_accepts_computed_source_and_exact_locks(self):
        constraints = ReviewConstraints(locked=(Decision("M7", "nura"), Decision("M12")))
        original = deepcopy((self.source, self.dataset, constraints))
        validate_review_input(self.source, self.dataset, constraints)
        self.assertEqual((self.source, self.dataset, constraints), original)

    def test_baseline_cannot_be_reviewed_as_a_five_decision_plan(self):
        with self.assertRaisesRegex(ValueError, "baseline"):
            validate_review_input(baseline(self.dataset), self.dataset, ReviewConstraints())

    def test_invalid_source_decisions_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_review_input(replace(self.source, decisions=REFERENCE[:4]),
                                  self.dataset, ReviewConstraints())

    def test_rejects_stale_or_edited_calculation_even_with_valid_decisions(self):
        for edited in (
            replace(self.source, cost=1),
            replace(self.source, after=replace(self.source.after, score=100.0)),
            replace(self.source, effects=()),
        ):
            with self.subTest(edited=edited):
                with self.assertRaises(ValueError):
                    validate_review_input(edited, self.dataset, ReviewConstraints())

    def test_locks_include_the_district_and_must_belong_to_source(self):
        for lock in (Decision("M7", "esil"), Decision("M4", "esil"), Decision("M12", "nura")):
            with self.subTest(lock=lock):
                with self.assertRaises(ValueError):
                    validate_review_input(self.source, self.dataset, ReviewConstraints(locked=(lock,)))

    def test_duplicate_locks_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_review_input(self.source, self.dataset,
                                  ReviewConstraints(locked=(Decision("M12"), Decision("M12"))))

    def test_wrong_source_or_constraints_type_has_a_value_error(self):
        with self.assertRaises(ValueError):
            validate_review_input(None, self.dataset, ReviewConstraints())
        for constraints in (None, {}, "locked"):
            with self.subTest(constraints=constraints):
                with self.assertRaises(ValueError):
                    validate_review_input(self.source, self.dataset, constraints)

    def test_locks_must_be_a_tuple_of_decisions(self):
        for locked in ([Decision("M12")], ("M12",), None):
            with self.subTest(locked=locked):
                with self.assertRaises(ValueError):
                    validate_review_input(self.source, self.dataset, ReviewConstraints(locked=locked))

    def test_current_contract_supports_zero_or_one_change_only(self):
        for limit in (0, 1):
            validate_review_input(self.source, self.dataset, ReviewConstraints(max_changes=limit))
        for limit in (-1, 2, 5, True, 1.0, "1"):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    validate_review_input(self.source, self.dataset, ReviewConstraints(max_changes=limit))


class CandidateConstraintsTests(unittest.TestCase):
    def setUp(self):
        self.source = simulate(REFERENCE, load_dataset())

    def codes(self, candidate, constraints=ReviewConstraints()):
        return {issue.code for issue in check_candidate_constraints(self.source, candidate, constraints)}

    def test_permutation_is_zero_changes(self):
        self.assertEqual(self.codes(tuple(reversed(REFERENCE)), ReviewConstraints(max_changes=0)), set())

    def test_replacing_measure_or_district_is_one_change(self):
        for replacement in (Decision("M9", "nura"), Decision("M7", "esil")):
            with self.subTest(replacement=replacement):
                candidate = (replacement, *REFERENCE[1:])
                self.assertEqual(self.codes(candidate), set())
                self.assertEqual(self.codes(candidate, ReviewConstraints(max_changes=0)), {"change_limit"})

    def test_second_round_cannot_chain_two_changes_from_original_source(self):
        first = (Decision("M7", "esil"), *REFERENCE[1:])
        second = (first[0], Decision("M8", "esil"), *REFERENCE[2:])
        self.assertEqual(self.codes(first), set())
        self.assertEqual(self.codes(second), {"change_limit"})

    def test_moving_locked_measure_returns_lock_error(self):
        candidate = (Decision("M7", "esil"), *REFERENCE[1:])
        self.assertEqual(self.codes(candidate, ReviewConstraints(locked=(REFERENCE[0],))), {"locked_changed"})

    def test_all_constraint_errors_are_preserved_together(self):
        candidate = (Decision("M7", "esil"), Decision("M8", "esil"), *REFERENCE[2:])
        constraints = ReviewConstraints(locked=(REFERENCE[0],))
        self.assertEqual(self.codes(candidate, constraints), {"locked_changed", "change_limit"})

    def test_constraint_check_does_not_mutate_source_or_candidate(self):
        candidate = list(REFERENCE)
        original = deepcopy((self.source, candidate))
        check_candidate_constraints(self.source, candidate, ReviewConstraints())
        self.assertEqual((self.source, candidate), original)


class ReviewOutcomeTests(unittest.TestCase):
    def setUp(self):
        source = simulate(REFERENCE, load_dataset())
        # Synthetic scores isolate EPS policy from the official scoring formula.
        self.source = replace(source, after=replace(source.after, score=0.0))

    def candidate(self, score, cost=95):
        return replace(self.source, after=replace(self.source.after, score=score), cost=cost)

    def test_improvement_requires_more_than_eps(self):
        self.assertEqual(classify_outcome(self.source, self.candidate(EPS)), "unchanged")
        self.assertEqual(classify_outcome(self.source, self.candidate(2 * EPS)), "improved")

    def test_cheaper_equal_accepts_both_inclusive_eps_boundaries(self):
        for score in (-EPS, 0.0, EPS):
            with self.subTest(score=score):
                self.assertEqual(classify_outcome(self.source, self.candidate(score, 94)), "cheaper_equal")

    def test_equal_or_worse_candidate_does_not_displace_source(self):
        for score, cost in ((0.0, 95), (0.0, 96), (-2 * EPS, 61)):
            with self.subTest(score=score, cost=cost):
                self.assertEqual(classify_outcome(self.source, self.candidate(score, cost)), "unchanged")

    def test_no_cumulative_epsilon_drift_when_each_round_uses_original_a(self):
        cheaper = self.candidate(-0.75 * EPS, 90)
        too_low = self.candidate(-1.5 * EPS, 80)
        self.assertEqual(classify_outcome(self.source, cheaper), "cheaper_equal")
        self.assertEqual(classify_outcome(self.source, too_low), "unchanged")

    def test_status_and_outcome_survive_json_without_losing_candidate_errors(self):
        source = simulate(REFERENCE, load_dataset())
        error = ValidationIssue("decision_count", "Нужно выбрать ровно 5 мер.")
        check = CandidateCheck(REFERENCE[:4], (error,), None)
        result = ReviewResult(source, source, (check,), "incomplete", "unchanged", ReviewConstraints())
        payload = json.loads(json.dumps(asdict(result), ensure_ascii=False))
        self.assertEqual(payload["status"], "incomplete")
        self.assertEqual(payload["outcome"], "unchanged")
        self.assertIsNone(payload["checks"][0]["result"])
        self.assertEqual(payload["checks"][0]["errors"][0]["message"], error.message)
        self.assertEqual(payload["source"]["after"]["score"], source.after.score)


if __name__ == "__main__":
    unittest.main()
