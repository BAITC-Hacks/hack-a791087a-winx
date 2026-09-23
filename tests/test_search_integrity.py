"""Integrity and exact-ranking tests for the S1 reviewer contract."""

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from citysim.data import load_dataset
from citysim.engine import simulate, validate_scenario
from citysim.models import Decision
from citysim import review_models
from citysim.review_models import EPS, ReviewConstraints


REFERENCE = (
    Decision("M7", "nura"), Decision("M8", "nura"), Decision("M10", "nura"),
    Decision("M12"), Decision("M5", "saryarka"),
)


def alternative_candidates(dataset, count=4):
    """Return valid one-change candidates without relying on search generation."""
    result = []
    for index, original in enumerate(REFERENCE):
        for measure in dataset.measures:
            targets = (None,) if measure.scope == "city" else tuple(d.id for d in dataset.districts)
            for district_id in targets:
                decision = Decision(measure.id, district_id)
                if decision == original:
                    continue
                candidate = list(REFERENCE)
                candidate[index] = decision
                candidate = tuple(candidate)
                if validate_scenario(candidate, dataset).valid and candidate not in result:
                    result.append(candidate)
                    if len(result) == count:
                        return tuple(result)
    if len(result) < count:
        raise AssertionError("Expected enough valid one-change alternatives")
    return tuple(result)


def canonical(decisions):
    return tuple(sorted(decisions, key=lambda d: (
        (0, int(d.measure_id[1:])) if d.measure_id[1:].isdigit() else (1, d.measure_id),
        d.district_id or "",
    )))


class PreviousIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.source = simulate(REFERENCE, self.dataset)
        self.candidates = alternative_candidates(self.dataset, 2)

    def make_previous(self, candidate=None):
        from citysim.search import review_candidates

        return review_candidates(self.source, [candidate or self.candidates[0]], self.dataset,
                                 ReviewConstraints())

    def test_previous_rejects_dataset_change_outside_source_effects(self):
        from citysim.search import review_candidates

        previous = self.make_previous()
        changed = deepcopy(self.dataset)
        measures = list(changed.measures)
        index = next(i for i, measure in enumerate(measures) if measure.id == "M1")
        measures[index] = replace(measures[index], cost=measures[index].cost + 1)
        changed = replace(changed, measures=tuple(measures))
        with self.assertRaises(ValueError):
            review_candidates(self.source, [self.candidates[1]], changed,
                              ReviewConstraints(), previous=previous)

    def test_previous_rejects_mutation_of_each_public_snapshot_part(self):
        from citysim.search import review_candidates

        mutations = (
            lambda p: replace(p, source=replace(p.source, cost=-1)),
            lambda p: replace(p, best=replace(p.best, cost=-1)),
            lambda p: (p.checks[0].result.indicator_deltas[next(iter(p.checks[0].result.indicator_deltas))].__setitem__("T1", -999) or p),
            lambda p: replace(p, checks=(replace(p.checks[0], errors=(replace(p.checks[0].errors[0], message="changed"),)), *p.checks[1:])),
            lambda p: replace(p, status="incomplete" if p.status == "completed_limited" else "completed_limited"),
            lambda p: replace(p, outcome="unchanged" if p.outcome != "unchanged" else "improved"),
            lambda p: replace(p, constraints=replace(p.constraints, max_changes=0)),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                previous = self.make_previous((Decision("M404"),)) if index == 3 else self.make_previous()
                previous = mutate(previous)
                with self.assertRaises(ValueError):
                    review_candidates(self.source, [self.candidates[1]], self.dataset,
                                      ReviewConstraints(), previous=previous)

    def test_untouched_previous_reuses_checks_without_simulating_them_again(self):
        from citysim import search

        previous = self.make_previous()
        prior_decisions = {check.decisions for check in previous.checks}
        real_search_simulate = search.simulate
        recalculated = []

        def tracked_simulate(decisions, dataset):
            recalculated.append(tuple(decisions))
            return real_search_simulate(decisions, dataset)

        with patch.object(search, "simulate", side_effect=tracked_simulate), \
             patch.object(review_models, "simulate", wraps=simulate) as source_simulate:
            combined = search.review_candidates(
                self.source, [self.candidates[1]], self.dataset,
                ReviewConstraints(), previous=previous,
            )
        self.assertEqual(source_simulate.call_count, 1)
        self.assertTrue(prior_decisions)
        self.assertTrue(prior_decisions.isdisjoint(recalculated))
        self.assertEqual(len(combined.checks), len(previous.checks) + 1)


class ExactRankingTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.source = simulate(REFERENCE, self.dataset)
        self.candidates = alternative_candidates(self.dataset, 5)

    def run_ranked(self, scores_and_costs, *, previous=None):
        from citysim import search

        candidates = self.candidates[:len(scores_and_costs)]
        by_decisions = {
            canonical(candidate): replace(self.source, decisions=canonical(candidate), cost=cost,
                               after=replace(self.source.after, score=score))
            for candidate, (score, cost) in zip(candidates, scores_and_costs)
        }
        with patch.object(search, "simulate", side_effect=lambda ds, _dataset: by_decisions[canonical(ds)]):
            return search.review_candidates(
                self.source, candidates, self.dataset, ReviewConstraints(), previous=previous,
            )

    def test_improved_candidate_outranks_cheaper_equal_candidate(self):
        review = self.run_ranked(((self.source.after.score + 2 * EPS, 99),
                                  (self.source.after.score + .5 * EPS, 1)))
        self.assertEqual(canonical(review.best.decisions), canonical(self.candidates[0]))
        self.assertEqual(review.outcome, "improved")

    def test_improved_uses_exact_score_then_cost_then_canonical_key(self):
        score = self.source.after.score + 2 * EPS
        review = self.run_ranked(((score, 80), (score + .25 * EPS, 90)))
        self.assertEqual(canonical(review.best.decisions), canonical(self.candidates[1]))

        review = self.run_ranked(((score, 81), (score, 80)))
        self.assertEqual(canonical(review.best.decisions), canonical(self.candidates[1]))

        tied = self.run_ranked(((score, 80), (score, 80)))
        expected = min(map(canonical, self.candidates[:2]), key=lambda row: tuple(
            (((0, int(d.measure_id[1:])) if d.measure_id[1:].isdigit() else (1, d.measure_id)),
             d.district_id or "") for d in row
        ))
        self.assertEqual(canonical(tied.best.decisions), expected)

    def test_cheaper_equal_uses_price_then_exact_score(self):
        score = self.source.after.score - .5 * EPS
        review = self.run_ranked(((score, 90), (score + .25 * EPS, 89)))
        self.assertEqual(canonical(review.best.decisions), canonical(self.candidates[1]))

        review = self.run_ranked(((score, 89), (score + .25 * EPS, 89)))
        self.assertEqual(canonical(review.best.decisions), canonical(self.candidates[1]))

    def test_second_round_compares_to_original_a_without_epsilon_chaining(self):
        from citysim import search

        first_candidate, second_candidate = self.candidates[:2]
        first_result = replace(self.source, decisions=first_candidate, cost=90,
                               after=replace(self.source.after, score=self.source.after.score - .75 * EPS))
        second_result = replace(self.source, decisions=second_candidate, cost=80,
                                after=replace(self.source.after, score=self.source.after.score - 1.5 * EPS))
        with patch.object(search, "simulate", return_value=first_result):
            first = search.review_candidates(self.source, [first_candidate], self.dataset,
                                             ReviewConstraints())
        with patch.object(search, "simulate", return_value=second_result):
            second = search.review_candidates(self.source, [second_candidate], self.dataset,
                                              ReviewConstraints(), previous=first)
        self.assertEqual(first.outcome, "cheaper_equal")
        self.assertEqual(canonical(second.best.decisions), canonical(first.best.decisions))
        self.assertEqual(second.outcome, "cheaper_equal")


if __name__ == "__main__":
    unittest.main()
