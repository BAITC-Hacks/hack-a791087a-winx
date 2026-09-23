"""S1 acceptance tests for deterministic candidate generation and review."""

import unittest
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from citysim.data import load_dataset
from citysim.engine import baseline, simulate, validate_scenario
from citysim.models import Decision
from citysim.review_models import ReviewConstraints
from citysim.search import generate_candidates, review_candidates


REFERENCE = (
    Decision("M5", "saryarka"), Decision("M7", "nura"), Decision("M8", "nura"),
    Decision("M10", "nura"), Decision("M12"),
)
IMPROVED = (
    Decision("M7", "nura"), Decision("M8", "nura"), Decision("M10", "nura"),
    Decision("M12"), Decision("M14"),
)
CHEAPEST = (
    Decision("M9", "nura"), Decision("M11", "esil"), Decision("M10", "baikonur"),
    Decision("M12"), Decision("M4", "saryarka"),
)


class SearchTestCase(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.source = simulate(REFERENCE, self.dataset)


class GenerateCandidatesTests(SearchTestCase):
    def test_generates_unique_valid_single_replacements_in_canonical_order(self):
        original = deepcopy((self.source, self.dataset))
        candidates = generate_candidates(self.source, self.dataset, ReviewConstraints())
        self.assertEqual((self.source, self.dataset), original)
        self.assertEqual(len(candidates), 20)
        self.assertLessEqual(len(candidates), 20)
        self.assertEqual(len(candidates), len(set(candidates)))
        source_set = set(self.source.decisions)
        measure_ids = {measure.id for measure in self.dataset.measures}
        district_ids = {district.id for district in self.dataset.districts}
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assertEqual(len(candidate), 5)
                self.assertEqual(len(set(candidate)), 5)
                self.assertEqual(len(source_set - set(candidate)), 1)
                self.assertEqual(len(set(candidate) - source_set), 1)
                self.assertTrue(validate_scenario(candidate, self.dataset).valid)
                key = tuple((int(d.measure_id[1:]), d.district_id or "") for d in candidate)
                self.assertEqual(key, tuple(sorted(key)))
                for decision in candidate:
                    self.assertIn(decision.measure_id, measure_ids)
                    measure = next(m for m in self.dataset.measures if m.id == decision.measure_id)
                    if measure.scope == "city":
                        self.assertIsNone(decision.district_id)
                    else:
                        self.assertIn(decision.district_id, district_ids)

    def test_source_pairs_are_excluded_from_generated_candidates_and_locks_apply(self):
        locked = (Decision("M7", "nura"), Decision("M12"))
        candidates = generate_candidates(
            self.source, self.dataset, ReviewConstraints(locked=locked),
        )
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertTrue(set(locked).issubset(candidate))
            self.assertEqual(len(set(self.source.decisions) - set(candidate)), 1)

    def test_limit_accepts_only_strict_int_inclusive_range_zero_to_twenty(self):
        for limit in (0, 1, 10, 20):
            with self.subTest(limit=limit):
                generated = generate_candidates(
                    self.source, self.dataset, ReviewConstraints(), limit=limit,
                )
                self.assertLessEqual(len(generated), limit)
                if limit == 0:
                    self.assertEqual(generated, ())
        for limit in (-1, 21, True, False, 1.0, "1", None):
            with self.subTest(invalid_limit=limit):
                with self.assertRaises(ValueError):
                    generate_candidates(self.source, self.dataset, ReviewConstraints(), limit=limit)

    def test_zero_changes_and_all_locked_have_empty_generator_result(self):
        self.assertEqual(generate_candidates(
            self.source, self.dataset, ReviewConstraints(max_changes=0),
        ), ())
        self.assertEqual(generate_candidates(
            self.source, self.dataset, ReviewConstraints(locked=self.source.decisions),
        ), ())

    def test_generator_prioritizes_critical_indicator_help_and_is_deterministic(self):
        cheapest_source = simulate(CHEAPEST, self.dataset)
        first = generate_candidates(cheapest_source, self.dataset, ReviewConstraints())
        second = generate_candidates(cheapest_source, self.dataset, ReviewConstraints())
        self.assertEqual(first, second)
        self.assertTrue(first)
        # S2 is still critical in Nura for this source. M8 in Nura is the only
        # available replacement that improves that critical indicator.
        added = set(first[0]) - set(cheapest_source.decisions)
        self.assertEqual(added, {Decision("M8", "nura")})

    def test_invalid_source_and_constraints_fail_before_search(self):
        for invalid_source in (baseline(self.dataset), replace(self.source, cost=1),
                               replace(self.source, decisions=REFERENCE[:4])):
            with self.subTest(source=invalid_source):
                with self.assertRaises(ValueError):
                    generate_candidates(invalid_source, self.dataset, ReviewConstraints())
        for constraints in (ReviewConstraints(max_changes=True),
                            ReviewConstraints(locked=(Decision("M1", "esil"),))):
            with self.subTest(constraints=constraints):
                with self.assertRaises(ValueError):
                    generate_candidates(self.source, self.dataset, constraints)


class ReviewCandidatesTests(SearchTestCase):
    def test_official_reference_and_improved_neighbor_are_real_engine_results(self):
        self.assertEqual(self.source.cost, 95)
        self.assertAlmostEqual(self.source.after.score, 56.54307, places=7)
        improved_result = simulate(IMPROVED, self.dataset)
        self.assertEqual(improved_result.cost, 86)
        self.assertAlmostEqual(improved_result.after.score, 56.98582, places=5)
        result = review_candidates(self.source, (IMPROVED,), self.dataset, ReviewConstraints())
        self.assertEqual(result.source, self.source)
        self.assertEqual(result.best.decisions, IMPROVED)
        self.assertEqual(result.best.cost, 86)
        self.assertEqual(result.outcome, "improved")
        self.assertEqual(result.status, "completed_limited")
        self.assertEqual(len(result.checks), 1)
        self.assertEqual(result.checks[0].result, improved_result)

    def test_official_cheapest_scenario_is_valid_reference(self):
        cheapest = simulate(CHEAPEST, self.dataset)
        self.assertEqual(cheapest.cost, 61)
        self.assertTrue(validate_scenario(CHEAPEST, self.dataset).valid)
        result = review_candidates(cheapest, (), self.dataset, ReviewConstraints())
        self.assertEqual(result.best, cheapest)
        self.assertEqual(result.checks, ())

    def test_source_does_not_consume_candidate_limit_or_appear_as_check(self):
        result = review_candidates(self.source, (self.source.decisions,), self.dataset,
                                   ReviewConstraints())
        self.assertEqual(result.best, self.source)
        self.assertEqual(result.outcome, "unchanged")
        self.assertEqual(result.checks, ())

    def test_permutations_deduplicate_candidates_but_duplicate_rows_remain_for_validation(self):
        result = review_candidates(
            self.source, (CHEAPEST, tuple(reversed(CHEAPEST))), self.dataset,
            ReviewConstraints(),
        )
        self.assertEqual(len(result.checks), 1)
        duplicate = (REFERENCE[0], REFERENCE[0], *REFERENCE[2:])
        duplicate_result = review_candidates(
            self.source, (duplicate,), self.dataset, ReviewConstraints(),
        )
        self.assertEqual(len(duplicate_result.checks), 1)
        check = duplicate_result.checks[0]
        self.assertEqual(check.decisions, tuple(sorted(
            duplicate, key=lambda d: (int(d.measure_id[1:]), d.district_id or ""),
        )))
        self.assertIsNone(check.result)
        self.assertIn("duplicate_measure", {issue.code for issue in check.errors})

    def test_bad_engine_candidates_keep_errors_and_never_get_a_simulation_result(self):
        unknown = (Decision("M99", "nura"), *REFERENCE[1:])
        four = REFERENCE[:4]
        six = (*REFERENCE, Decision("M9", "esil"))
        double = (REFERENCE[0], REFERENCE[0], *REFERENCE[2:])
        locked_change = (Decision("M5", "esil"), *REFERENCE[1:])
        change_limit = (Decision("M5", "esil"), Decision("M7", "esil"), *REFERENCE[2:])
        inputs = (unknown, four, six, double, locked_change, change_limit)
        constraints = ReviewConstraints(locked=(REFERENCE[0],), max_changes=0)
        with patch("citysim.search.simulate", wraps=simulate) as simulation:
            result = review_candidates(self.source, inputs, self.dataset, constraints)
        self.assertEqual(simulation.call_count, 0)
        self.assertEqual(len(result.checks), len(inputs))
        key = lambda rows: tuple(sorted(rows, key=lambda d: (
            int(d.measure_id[1:]) if d.measure_id.startswith("M") and d.measure_id[1:].isdigit() else 9999,
            d.district_id or "",
        )))
        by_decisions = {check.decisions: check for check in result.checks}
        self.assertIn("unknown_measure", {e.code for e in by_decisions[key(unknown)].errors})
        self.assertIn("decision_count", {e.code for e in by_decisions[key(four)].errors})
        self.assertIn("decision_count", {e.code for e in by_decisions[key(six)].errors})
        self.assertIn("duplicate_measure", {e.code for e in by_decisions[key(double)].errors})
        self.assertIn("locked_changed", {e.code for e in by_decisions[key(locked_change)].errors})
        self.assertIn("change_limit", {e.code for e in by_decisions[key(change_limit)].errors})
        self.assertTrue(all(check.result is None for check in result.checks))

    def test_simulate_runs_only_for_valid_candidates(self):
        invalid = REFERENCE[:4]
        with patch("citysim.search.simulate", wraps=simulate) as simulation:
            result = review_candidates(self.source, (invalid, IMPROVED), self.dataset,
                                       ReviewConstraints())
        self.assertEqual(simulation.call_count, 1)
        self.assertIsNone(result.checks[0].result)
        self.assertIsNotNone(result.checks[1].result)

    def test_worse_or_equal_candidates_do_not_displace_source(self):
        # M9 replaces M7 in Nura: valid and cheaper, but the resulting score falls.
        worse = tuple(d for d in REFERENCE if d.measure_id != "M7") + (Decision("M9", "nura"),)
        self.assertLess(simulate(worse, self.dataset).after.score, self.source.after.score)
        for candidate in (worse, REFERENCE):
            with self.subTest(candidate=candidate):
                result = review_candidates(self.source, (candidate,), self.dataset,
                                           ReviewConstraints())
                self.assertEqual(result.best, self.source)
                self.assertEqual(result.outcome, "unchanged")

    def test_distinct_equal_score_and_cost_candidate_keeps_a(self):
        dataset = replace(self.dataset, measures=tuple(
            replace(m, effects={}) for m in self.dataset.measures
        ))
        source = simulate(REFERENCE, dataset)
        equal = (Decision("M5", "esil"), *REFERENCE[1:])
        expected = simulate(equal, dataset)
        self.assertEqual((expected.after.score, expected.cost), (source.after.score, source.cost))
        review = review_candidates(source, (equal,), dataset, ReviewConstraints())
        self.assertEqual(review.best, source)
        self.assertEqual(review.checks[0].result, expected)

    def test_unknown_strings_and_duplicate_unknowns_are_validation_errors(self):
        unknown = (Decision("not-a-measure", "nura"), *REFERENCE[1:])
        repeated = (Decision("?"), Decision("?"), *REFERENCE[2:])
        review = review_candidates(self.source, (unknown, repeated), self.dataset, ReviewConstraints())
        self.assertIn("unknown_measure", {e.code for e in review.checks[0].errors})
        self.assertIn("duplicate_measure", {e.code for e in review.checks[1].errors})
        self.assertTrue(all(check.result is None for check in review.checks))

    def test_none_and_empty_district_are_not_deduplicated(self):
        proposals = tuple((Decision("M5", target), *REFERENCE[1:]) for target in (None, ""))
        review = review_candidates(self.source, proposals, self.dataset, ReviewConstraints())
        self.assertEqual(len(review.checks), 2)
        self.assertIn("district_required", {e.code for e in review.checks[0].errors})
        self.assertIn("unknown_district", {e.code for e in review.checks[1].errors})

    def test_malformed_types_raise_before_candidate_simulation(self):
        for proposals in (None, "text", (({},),), ((Decision(1),),), ((Decision("M5", []),),)):
            with self.subTest(proposals=proposals), patch("citysim.search.simulate") as simulation:
                with self.assertRaises(ValueError):
                    review_candidates(self.source, proposals, self.dataset, ReviewConstraints())
                simulation.assert_not_called()
        for completed in (0, 1, None, "false"):
            with self.subTest(completed=completed), self.assertRaises(ValueError):
                review_candidates(self.source, (), self.dataset, ReviewConstraints(), completed=completed)

    def test_incomplete_can_preserve_an_improvement(self):
        result = review_candidates(self.source, (IMPROVED,), self.dataset,
                                   ReviewConstraints(), completed=False)
        self.assertEqual(result.status, "incomplete")
        self.assertEqual(result.outcome, "improved")
        self.assertEqual(result.best.decisions, IMPROVED)

    def test_previous_is_copied_deduplicated_and_shared_twenty_limit_is_enforced(self):
        first = review_candidates(self.source, (IMPROVED,), self.dataset, ReviewConstraints())
        snapshot = deepcopy(first)
        next_result = review_candidates(
            self.source, (tuple(reversed(IMPROVED)), REFERENCE), self.dataset,
            ReviewConstraints(), previous=first,
        )
        self.assertEqual(first, snapshot)
        self.assertEqual(len(next_result.checks), 1)
        self.assertEqual(next_result.checks[0], first.checks[0])
        self.assertIsNot(next_result.checks[0].result, first.checks[0].result)
        next_result.checks[0].result.districts_after[0].indicators["T1"] = -99
        self.assertNotEqual(first.checks[0].result.districts_after[0].indicators["T1"], -99)
        self.assertEqual(next_result.best, first.best)

    def test_twenty_candidate_limit_spans_previous_and_preflights_atomically(self):
        previous_candidates = tuple(
            (Decision("M99", f"unknown-{index}"),) for index in range(19)
        )
        previous = review_candidates(
            self.source, previous_candidates, self.dataset, ReviewConstraints(),
        )
        self.assertEqual(len(previous.checks), 19)

        accepted = review_candidates(
            self.source, (IMPROVED,), self.dataset, ReviewConstraints(), previous=previous,
        )
        self.assertEqual(len(accepted.checks), 20)
        self.assertEqual(accepted.checks[-1].decisions, IMPROVED)
        self.assertIsNotNone(accepted.checks[-1].result)

        # With only the 19-item previous snapshot, one valid new proposal reaches
        # 20; the following unique proposal overflows. The entire call is preflighted.
        with patch("citysim.search.simulate", wraps=simulate) as simulation:
            with self.assertRaises(ValueError):
                review_candidates(
                    self.source, (IMPROVED, CHEAPEST), self.dataset,
                    ReviewConstraints(), previous=previous,
                )
        simulation.assert_not_called()

    def test_second_round_changes_are_still_measured_from_original_source(self):
        first_replacement = (REFERENCE[0], Decision("M7", "esil"), *REFERENCE[2:])
        first = review_candidates(self.source, (first_replacement,), self.dataset,
                                  ReviewConstraints())
        self.assertIsNotNone(first.checks[0].result)
        self.assertEqual(first.checks[0].errors, ())
        chained = (*first_replacement[:2], Decision("M8", "esil"), *REFERENCE[3:])
        self.assertTrue(validate_scenario(chained, self.dataset).valid)
        second = review_candidates(self.source, (chained,), self.dataset,
                                   ReviewConstraints(), previous=first)
        check = next(check for check in second.checks if set(check.decisions) == set(chained))
        self.assertIn("change_limit", {issue.code for issue in check.errors})
        self.assertIsNone(check.result)

    def test_invalid_source_or_constraints_raise_before_candidate_work(self):
        with patch("citysim.search.simulate", wraps=simulate) as simulation:
            with self.assertRaises(ValueError):
                review_candidates(baseline(self.dataset), (CHEAPEST,), self.dataset,
                                  ReviewConstraints())
            with self.assertRaises(ValueError):
                review_candidates(self.source, (CHEAPEST,), self.dataset,
                                  ReviewConstraints(max_changes=True))
        simulation.assert_not_called()

    def test_more_than_twenty_unique_candidates_raise_atomically(self):
        # Cheap valid source-neighbourhood candidates are not required here; malformed
        # sequences still count as unique proposals and must be preflighted as a batch.
        candidates = tuple((Decision("M99", str(index)),) for index in range(21))
        with patch("citysim.search.simulate", wraps=simulate) as simulation:
            with self.assertRaises(ValueError):
                review_candidates(self.source, candidates, self.dataset, ReviewConstraints())
        simulation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
