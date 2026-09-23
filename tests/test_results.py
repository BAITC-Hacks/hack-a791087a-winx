"""Passport tables preserve engine facts, including clipping and negative effects."""
from copy import deepcopy
import unittest
from citysim.data import load_dataset
from citysim.engine import simulate
from citysim.models import Decision
from ui.results import build_passport

REFERENCE = (Decision('M7', 'nura'), Decision('M8', 'nura'), Decision('M10', 'nura'), Decision('M12'), Decision('M5', 'saryarka'))

class PassportTests(unittest.TestCase):
    def test_reference_contains_every_saved_decision_and_calculated_change(self):
        dataset = load_dataset()
        result = simulate(REFERENCE, dataset)
        original = deepcopy(result)
        passport = build_passport(result, dataset)
        self.assertEqual(len(passport['decisions']), 5)
        self.assertEqual(len(passport['districts']), 5)
        self.assertEqual(len(passport['indicators']), 50)
        self.assertEqual(passport['remaining_critical'], [])
        self.assertEqual({r['Код'] for r in passport['resolved_critical']}, {'S1', 'S2'})
        self.assertEqual(passport['weakest_name'], 'Нура')
        city = next(row for row in passport['decisions'] if row['Код'] == 'M12')
        self.assertEqual(city['Где'], 'Весь город')
        for row in passport['indicators']:
            district_id = next(d.id for d in dataset.districts if d.name == row['Район'])
            self.assertEqual(row['Изменение'], result.indicator_deltas[district_id][row['Код']])
        self.assertEqual(result, original)

    def test_trace_and_clipped_change_remain_distinct(self):
        dataset = deepcopy(load_dataset())
        next(d for d in dataset.districts if d.id == 'nura').indicators['S1'] = 99
        result = simulate(REFERENCE, dataset)
        passport = build_passport(result, dataset)
        row = next(r for r in passport['indicators'] if r['Район'] == 'Нура' and r['Код'] == 'S1')
        effect = next(r for r in passport['effects'] if r['Источник'] == 'M7' and r['Код'] == 'S1')
        self.assertEqual((row['До'], row['После'], row['Изменение']), (99, 100, 1))
        self.assertGreater(effect['Эффект до clip'], 1)

    def test_m11_negative_delta_and_remaining_critical_are_visible(self):
        dataset = load_dataset()
        decisions = (Decision('M9', 'nura'), Decision('M11', 'nura'), Decision('M10', 'nura'), Decision('M12'), Decision('M4', 'saryarka'))
        passport = build_passport(simulate(decisions, dataset), dataset)
        row = next(r for r in passport['indicators'] if r['Район'] == 'Нура' and r['Код'] == 'T1')
        self.assertEqual(row['Изменение'], -1.75)
        self.assertEqual({r['Код'] for r in passport['remaining_critical']}, {'S2'})
        self.assertEqual({r['Код'] for r in passport['resolved_critical']}, {'S1'})

if __name__ == '__main__':
    unittest.main()
