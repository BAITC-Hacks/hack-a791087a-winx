"""Comparison uses saved engine snapshots and the review's real checks."""
import unittest
from dataclasses import replace

from citysim.data import load_dataset
from citysim.engine import simulate
from citysim.models import Decision
from citysim.review_models import ReviewConstraints
from citysim.reviewer import review_scenario
from ui.review import build_comparison, build_review_log, review_summary
from ui.scene import build_scene_details

REFERENCE = (Decision('M7','nura'), Decision('M8','nura'), Decision('M10','nura'),
             Decision('M12'), Decision('M5','saryarka'))


class ReviewPresentationTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset()
        self.a = simulate(REFERENCE, self.dataset)
        self.review, _ = review_scenario(self.a, self.dataset, ReviewConstraints())
        self.b = self.review.best

    def test_comparison_is_a_to_b_not_baseline_delta(self):
        comparison = build_comparison(self.a, self.b, self.dataset)
        score = next(row for row in comparison['city'] if row['Показатель'] == 'Score')
        self.assertAlmostEqual(score['B − A'], 56.69056 - 56.54307)
        self.assertNotEqual(score['B − A'], self.b.score_delta)
        self.assertEqual(len(comparison['indicators']), 50)
        self.assertTrue(any(row['B − A'] < 0 for row in comparison['indicators']))
        self.assertEqual(len(comparison['districts']), 5)

    def test_incomplete_is_independent_of_improvement_and_real_check_count(self):
        summary = review_summary(replace(self.review, status='incomplete'))
        self.assertIn('не завершена', summary['status'].lower())
        self.assertIn('улучшение', summary['outcome'].lower())
        self.assertEqual(summary['checked'], len(self.review.checks))
        self.assertEqual(len(build_review_log(self.review, self.dataset)), len(self.review.checks))

    def test_no_changes_is_not_a_claim_of_global_optimum(self):
        review, _ = review_scenario(self.a, self.dataset, ReviewConstraints(max_changes=0))
        summary = review_summary(review)
        self.assertEqual(summary['outcome'], 'В проверенных вариантах улучшений нет')
        self.assertEqual(summary['checked'], 0)
        self.assertNotIn('оптимален', str(summary))

    def test_scene_details_filter_measure_catalog_and_engine_effects(self):
        details = build_scene_details(self.a, self.dataset, 'B1', 'nura')
        self.assertEqual([row['Код'] for row in details['measures']], ['M10'])
        self.assertTrue(any(row['Источник'] == 'M10+M12' for row in details['effects']))
        self.assertTrue(all(row['Район'] == 'Нура' for row in details['effects']))
        city = build_scene_details(self.a, self.dataset, 'C2', 'esil')
        self.assertEqual([row['Код'] for row in city['measures']], ['M12'])
        self.assertEqual(len(city['effects']), 1)
        self.assertEqual(build_scene_details(self.a, self.dataset, 'S1', 'esil')['measures'], [])
