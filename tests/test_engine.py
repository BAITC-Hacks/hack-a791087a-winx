"""Acceptance tests for the official dataset, scenario rules and numerical core."""

import unittest
from copy import deepcopy
from dataclasses import replace
from itertools import permutations
from unittest.mock import patch

from citysim.data import load_dataset
from citysim.engine import (
    InvalidScenarioError, baseline, compute_score, simulate, validate_scenario,
)
from citysim.models import Decision


REFERENCE = (
    Decision("M7", "nura"), Decision("M8", "nura"), Decision("M10", "nura"),
    Decision("M12"), Decision("M5", "saryarka"),
)
CHEAPEST = (
    Decision("M9", "nura"), Decision("M11", "nura"), Decision("M10", "nura"),
    Decision("M12"), Decision("M4", "saryarka"),
)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()

    def assert_codes(self, decisions, codes, cost):
        validation = validate_scenario(decisions, self.dataset)
        self.assertEqual({issue.code for issue in validation.errors}, set(codes))
        self.assertEqual(validation.valid, not codes)
        self.assertEqual(validation.cost, cost)
        for issue in validation.errors:
            self.assertTrue(any("а" <= char.lower() <= "я" for char in issue.message))
        return validation

    def test_reference_and_cheapest_are_valid_without_all_five_directions(self):
        self.assert_codes(REFERENCE, (), 95)
        self.assert_codes(CHEAPEST, (), 61)

    def test_requires_exactly_five_decisions_including_empty_baseline(self):
        for decisions, cost in (((), 0), (REFERENCE[:4], 70),
                                ((*CHEAPEST, Decision("M2")), 83)):
            with self.subTest(count=len(decisions)):
                self.assert_codes(decisions, ("decision_count",), cost)

    def test_unknown_measure_has_partial_cost(self):
        self.assert_codes((Decision("M99", "nura"), *REFERENCE[1:]),
                          ("unknown_measure",), 71)

    def test_duplicate_measure_counts_each_row_even_in_different_districts(self):
        self.assert_codes((REFERENCE[0], Decision("M7", "esil"), *REFERENCE[2:]),
                          ("duplicate_measure",), 99)

    def test_district_is_required_for_district_measure(self):
        self.assert_codes((Decision("M7"), *REFERENCE[1:]), ("district_required",), 95)

    def test_unknown_district_including_empty_string(self):
        for district_id in ("missing", "", "Нура"):
            with self.subTest(district_id=district_id):
                self.assert_codes((Decision("M7", district_id), *REFERENCE[1:]),
                                  ("unknown_district",), 95)

    def test_city_accepts_only_none_for_district(self):
        for district_id in ("nura", "missing", "", "город"):
            with self.subTest(district_id=district_id):
                decisions = (*REFERENCE[:3], Decision("M12", district_id), REFERENCE[4])
                self.assert_codes(decisions, ("district_forbidden",), 95)

    def test_over_budget(self):
        decisions = (Decision("M3", "esil"), Decision("M5", "saryarka"),
                     Decision("M2"), Decision("M12"), Decision("M11", "almaty"))
        self.assert_codes(decisions, ("budget_exceeded",), 101)

    def test_three_measures_in_one_direction(self):
        decisions = (Decision("M7", "nura"), Decision("M8", "nura"),
                     Decision("M9", "nura"), Decision("M10", "nura"), Decision("M12"))
        self.assert_codes(decisions, ("direction_limit",), 80)

    def test_incompatible_pairs_and_geographic_scope(self):
        cases = (("M1", "M3", 84, True), ("M4", "M7", 75, False),
                 ("M5", "M13", 89, False))
        for first, second, cost, global_conflict in cases:
            for target in ("nura", "esil"):
                with self.subTest(pair=(first, second), target=target):
                    decisions = (Decision(first, "nura"), Decision(second, target),
                                 Decision("M9", "nura"), Decision("M10", "nura"),
                                 Decision("M12"))
                    # M4+M7 costs 39; these three neutral fillers cost 36.
                    codes = ("incompatible_measures",) if global_conflict or target == "nura" else ()
                    self.assert_codes(decisions, codes, cost)

    def test_collects_all_independently_applicable_errors(self):
        decisions = (Decision("M1"), Decision("M3", "esil"), Decision("M3", "missing"),
                     Decision("M12", "nura"), Decision("M99"), Decision("M7", "nura"))
        self.assert_codes(decisions, (
            "decision_count", "unknown_measure", "duplicate_measure", "district_required",
            "unknown_district", "district_forbidden", "budget_exceeded",
            "direction_limit", "incompatible_measures",
        ), 116)

    def test_unknown_measure_does_not_guess_scope_or_direction(self):
        self.assert_codes((Decision("M99", "missing"), *REFERENCE[1:]),
                          ("unknown_measure",), 71)

    def test_duplicate_unknown_measure_is_also_reported(self):
        self.assert_codes((Decision("M99"), Decision("M99"), *REFERENCE[2:]),
                          ("unknown_measure", "duplicate_measure"), 51)

    def test_invalid_scenario_never_computes_a_score(self):
        validation = validate_scenario(REFERENCE[:4], self.dataset)
        with patch("citysim.engine.compute_score") as score:
            with self.assertRaises(InvalidScenarioError) as raised:
                simulate(REFERENCE[:4], self.dataset)
        score.assert_not_called()
        self.assertEqual(raised.exception.validation, validation)
        self.assertIn(validation.errors[0].message, str(raised.exception))


class ScenarioTests(unittest.TestCase):
    def test_official_reference(self):
        result = simulate(REFERENCE, load_dataset())
        self.assertEqual((result.cost, result.remaining_budget, result.after.n_crit), (95, 5, 0))
        self.assertAlmostEqual(result.before.score, 52.55768, places=7)
        self.assertAlmostEqual(result.after.score, 56.54307, places=7)
        self.assertAlmostEqual(result.score_delta, 3.98539, places=7)
        self.assertFalse(result.is_baseline)

    def test_cheapest_scenario(self):
        result = simulate(CHEAPEST, load_dataset())
        self.assertEqual((result.cost, result.remaining_budget), (61, 39))
        self.assertGreater(result.after.score, result.before.score)

    def test_every_permutation_has_identical_full_result(self):
        dataset = load_dataset()
        expected = simulate(REFERENCE, dataset)
        self.assertEqual(tuple(d.measure_id for d in expected.decisions),
                         ("M5", "M7", "M8", "M10", "M12"))
        for decisions in permutations(REFERENCE):
            with self.subTest(order=decisions):
                self.assertEqual(simulate(decisions, dataset), expected)

    def test_input_is_not_changed(self):
        dataset = load_dataset()
        decisions = list(REFERENCE)
        original = deepcopy((dataset, decisions))
        validate_scenario(decisions, dataset)
        simulate(decisions, dataset)
        self.assertEqual((dataset, decisions), original)


class BaselineTests(unittest.TestCase):
    def test_organizer_baseline(self):
        dataset = load_dataset()
        result = baseline(dataset)
        self.assertAlmostEqual(result.after.score, 52.55768, places=7)
        self.assertAlmostEqual(result.after.d_avg, 56.8624, places=7)
        self.assertEqual(result.after.n_crit, 2)
        self.assertEqual(result.after.d_min, 49.18)
        self.assertTrue(result.is_baseline)
        self.assertEqual(result.remaining_budget, 100)

    def test_exactly_40_is_not_critical(self):
        dataset = load_dataset()
        nura = dataset.districts[-1]
        revised = replace(nura, indicators={**nura.indicators, "S1": 40, "S2": 40})
        score = compute_score((*dataset.districts[:-1], revised), dataset.weights)
        self.assertEqual(score.n_crit, 0)
        revised = replace(revised, indicators={**revised.indicators, "S1": 39.999})
        score = compute_score((*dataset.districts[:-1], revised), dataset.weights)
        self.assertEqual(score.n_crit, 1)

    def test_calculation_does_not_mutate_or_share_input(self):
        dataset = load_dataset()
        original = deepcopy(dataset)
        result = baseline(dataset)
        self.assertEqual(dataset, original)
        result.districts_after[0].indicators["T1"] = 0
        self.assertEqual(dataset, original)
        self.assertEqual(load_dataset(), original)


if __name__ == "__main__":
    unittest.main()
