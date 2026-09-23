"""Numerical baseline acceptance tests; scenario rules are milestone E1."""

import unittest
from copy import deepcopy
from dataclasses import replace

from citysim.data import load_dataset
from citysim.engine import baseline, compute_score


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
