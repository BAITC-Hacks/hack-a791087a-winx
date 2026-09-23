"""E2 boundary and effect-trace acceptance tests."""

import unittest
from copy import deepcopy
from dataclasses import replace

from citysim.data import load_dataset
from citysim.engine import simulate, validate_scenario
from citysim.models import Decision


class EngineBoundaryTests(unittest.TestCase):
    def test_budget_limit_accepts_exactly_100(self):
        decisions = (
            Decision("M3", "esil"), Decision("M7", "nura"),
            Decision("M8", "nura"), Decision("M14"), Decision("M11", "almaty"),
        )
        result = simulate(decisions, load_dataset())
        self.assertEqual((result.cost, result.remaining_budget), (100, 0))
        # The adjacent 101 case is covered by ValidationTests.test_over_budget.

    def test_critical_threshold_is_strict_after_simulation(self):
        base = load_dataset()
        nura = base.districts[-1]
        fillers = (Decision("M9", "esil"), Decision("M10", "esil"),
                   Decision("M11", "almaty"), Decision("M2"))
        decisions = (Decision("M7", "nura"), *fillers)

        for initial, expected, critical in ((30.0, 40.0, False),
                                           (29.999, 39.999, True)):
            with self.subTest(initial=initial):
                district = replace(nura, indicators={**nura.indicators, "S1": initial})
                dataset = replace(base, districts=(*base.districts[:-1], district))
                result = simulate(decisions, dataset)
                nura_after = next(d for d in result.districts_after if d.id == "nura")
                self.assertAlmostEqual(nura_after.indicators["S1"], expected)
                self.assertEqual(result.after.n_crit, int(critical) + 1)  # Nura S2 remains below 40.

    def test_lag_and_city_versus_district_effects(self):
        decisions = (
            Decision("M2"), Decision("M6"), Decision("M7", "nura"),
            Decision("M10", "nura"), Decision("M12"),
        )
        dataset = load_dataset()
        result = simulate(decisions, dataset)
        effects = {(e.source, e.district_id, e.indicator): e.delta for e in result.effects}

        # L=2 (M2): 4 and 3 are scaled by 6/8; city effects reach every district.
        for district in dataset.districts:
            self.assertEqual(effects[("M2", district.id, "T1")], 3.0)
            self.assertEqual(effects[("M2", district.id, "B2")], 2.25)
        # M6 has L=4; its city-wide effect is scaled by 4/8.
        for district in dataset.districts:
            self.assertEqual(effects[("M6", district.id, "E1")], 2.5)
            self.assertEqual(effects[("M6", district.id, "E2")], 1.5)
        # District measures apply only to their selected district; M7 has L=3.
        self.assertEqual(effects[("M7", "nura", "S1")], 10.0)
        self.assertNotIn(("M7", "esil", "S1"), effects)
        self.assertEqual(effects[("M10", "nura", "B1")], 10.5)
        self.assertEqual(effects[("M12", "esil", "C2")], 4.375)
        self.assertEqual(effects[("M12", "nura", "C2")], 4.375)

    def test_m11_negative_t1_and_lagged_b2_are_traced(self):
        decisions = (Decision("M11", "nura"), Decision("M7", "esil"),
                     Decision("M8", "esil"), Decision("M4", "almaty"),
                     Decision("M5", "saryarka"))
        result = simulate(decisions, load_dataset())
        effects = {(e.source, e.district_id, e.indicator): e.delta for e in result.effects}
        self.assertEqual(effects[("M11", "nura", "T1")], -1.75)
        self.assertEqual(effects[("M11", "nura", "B2")], 10.5)
        self.assertEqual(result.indicator_deltas["nura"]["T1"], -1.75)
        self.assertEqual(result.indicator_deltas["nura"]["B2"], 10.5)

    def test_all_synergies_are_fixed_and_target_the_first_measure_district(self):
        cases = (
            ((Decision("M1", "esil"), Decision("M2"), Decision("M7", "nura"),
              Decision("M8", "nura"), Decision("M10", "baikonur")),
             "M1+M2", "esil", "T1"),
            ((Decision("M10", "nura"), Decision("M12"), Decision("M7", "saryarka"),
              Decision("M8", "nura"), Decision("M5", "almaty")),
             "M10+M12", "nura", "B1"),
            ((Decision("M5", "saryarka"), Decision("M6"), Decision("M9", "nura"),
              Decision("M10", "esil"), Decision("M12")),
             "M5+M6", "saryarka", "E2"),
        )
        for decisions, source, district_id, indicator in cases:
            with self.subTest(source=source):
                result = simulate(decisions, load_dataset())
                bonuses = [e for e in result.effects if e.source == source]
                self.assertEqual(len(bonuses), 1)
                self.assertEqual((bonuses[0].district_id, bonuses[0].indicator,
                                  bonuses[0].delta), (district_id, indicator, 2.0))

    def test_synergy_is_absent_when_its_pair_is_incomplete(self):
        cases = (
            ((Decision("M1", "esil"), Decision("M7", "nura"), Decision("M8", "nura"),
              Decision("M10", "baikonur"), Decision("M12")), "M1+M2"),
            ((Decision("M10", "nura"), Decision("M7", "esil"), Decision("M8", "esil"),
              Decision("M5", "saryarka"), Decision("M14")), "M10+M12"),
            ((Decision("M5", "saryarka"), Decision("M7", "nura"), Decision("M8", "nura"),
              Decision("M10", "esil"), Decision("M12")), "M5+M6"),
        )
        for decisions, source in cases:
            with self.subTest(source=source):
                result = simulate(decisions, load_dataset())
                self.assertNotIn(source, {e.source for e in result.effects})

    def test_repeated_rows_do_not_hide_any_incompatibility(self):
        cases = (
            # M1/M3 is global, even with duplicate M1 rows and different districts.
            ((Decision("M1", "nura"), Decision("M1", "esil"),
              Decision("M3", "saryarka"), Decision("M7", "nura"),
              Decision("M8", "esil")), "M1", "M3"),
            # M4/M7 is local; a repeated M4 in the conflicting district still conflicts.
            ((Decision("M4", "esil"), Decision("M4", "nura"),
              Decision("M7", "esil"), Decision("M10", "nura"),
              Decision("M12")), "M4", "M7"),
            # M5/M13 is local; duplicate M5 elsewhere must not suppress the intersection.
            ((Decision("M5", "saryarka"), Decision("M5", "nura"),
              Decision("M13", "nura"), Decision("M9", "esil"),
              Decision("M10", "almaty")), "M5", "M13"),
        )
        for decisions, first, second in cases:
            with self.subTest(pair=(first, second)):
                validation = validate_scenario(decisions, load_dataset())
                codes = [issue.code for issue in validation.errors]
                self.assertIn("duplicate_measure", codes)
                self.assertIn("incompatible_measures", codes)

    def test_local_conflicts_are_allowed_in_different_districts_even_with_duplicate(self):
        cases = (
            (Decision("M4", "esil"), Decision("M4", "saryarka"),
             Decision("M7", "nura"), Decision("M10", "nura"), Decision("M12")),
            (Decision("M5", "esil"), Decision("M5", "saryarka"),
             Decision("M13", "nura"), Decision("M9", "nura"), Decision("M10", "almaty")),
        )
        for decisions in cases:
            with self.subTest(measures=tuple(d.measure_id for d in decisions)):
                codes = {issue.code for issue in validate_scenario(decisions, load_dataset()).errors}
                self.assertIn("duplicate_measure", codes)
                self.assertNotIn("incompatible_measures", codes)

    def test_clipping_happens_once_after_opposing_effects_and_trace_stays_unclipped(self):
        base = load_dataset()
        scenario = (Decision("M2"), Decision("M11", "esil"), Decision("M4", "saryarka"),
                    Decision("M7", "nura"), Decision("M8", "nura"))
        original_esil = next(d for d in base.districts if d.id == "esil")
        # At the upper boundary: +3 from M2 and -1.75 from M11 sum to +1.25,
        # then clip 99.5 + 1.25 to 100. The trace retains both raw contributions.
        upper_district = replace(original_esil, indicators={**original_esil.indicators, "T1": 99.5})
        upper = replace(base, districts=(upper_district, *base.districts[1:]))
        upper_result = simulate(scenario, upper)
        upper_raw = sum(e.delta for e in upper_result.effects
                        if e.district_id == "esil" and e.indicator == "T1")
        self.assertEqual(upper_raw, 1.25)
        self.assertEqual(upper_result.indicator_deltas["esil"]["T1"], 0.5)
        self.assertEqual(upper_result.districts_after[0].indicators["T1"], 100.0)

        # At the lower boundary, reverse the synthetic M2/M11 signs. The canonical
        # effect order applies the early negative contribution first: stepwise clip
        # would give 1.75, while sum-then-clip correctly gives 0.
        lower_district = replace(original_esil, indicators={**original_esil.indicators, "T1": 3.0})
        lower_measures = tuple(
            replace(m, effects={**m.effects, "T1": -8}) if m.id == "M2"
            else replace(m, effects={**m.effects, "T1": 2}) if m.id == "M11"
            else m for m in base.measures
        )
        lower = replace(base, districts=(lower_district, *base.districts[1:]), measures=lower_measures)
        lower_result = simulate(scenario, lower)
        lower_raw = sum(e.delta for e in lower_result.effects
                        if e.district_id == "esil" and e.indicator == "T1")
        self.assertEqual(lower_raw, -4.25)
        self.assertEqual(lower_result.indicator_deltas["esil"]["T1"], -3.0)
        self.assertEqual(lower_result.districts_after[0].indicators["T1"], 0.0)

    def test_effects_and_deltas_reconstruct_every_indicator(self):
        dataset = load_dataset()
        decisions = (Decision("M1", "esil"), Decision("M2"), Decision("M7", "nura"),
                     Decision("M10", "nura"), Decision("M12"))
        result = simulate(decisions, dataset)
        raw = {d.id: {key: 0.0 for key in dataset.weights} for d in dataset.districts}
        for effect in result.effects:
            raw[effect.district_id][effect.indicator] += effect.delta

        before_by_id = {d.id: d for d in dataset.districts}
        after_by_id = {d.id: d for d in result.districts_after}
        for district_id, before in before_by_id.items():
            after = after_by_id[district_id]
            for indicator in dataset.weights:
                expected = min(100.0, max(0.0, before.indicators[indicator] + raw[district_id][indicator]))
                self.assertAlmostEqual(after.indicators[indicator], expected)
                self.assertAlmostEqual(result.indicator_deltas[district_id][indicator],
                                       after.indicators[indicator] - before.indicators[indicator])

    def test_effects_use_canonical_composite_measure_ids(self):
        dataset = load_dataset()
        decisions = (Decision("M12"), Decision("M10", "nura"), Decision("M5", "saryarka"),
                     Decision("M7", "nura"), Decision("M8", "nura"))
        result = simulate(decisions, dataset)
        keys = [(tuple(int(part[1:]) for part in effect.source.split("+")),
                 effect.district_id, effect.indicator) for effect in result.effects]
        self.assertEqual(keys, sorted(keys))
        reversed_result = simulate(tuple(reversed(decisions)), dataset)
        self.assertEqual(result.effects, reversed_result.effects)

    def test_result_dictionaries_are_independent_from_input_and_other_results(self):
        dataset = load_dataset()
        original = deepcopy(dataset)
        decisions = (Decision("M7", "nura"), Decision("M8", "nura"),
                     Decision("M10", "nura"), Decision("M12"),
                     Decision("M5", "saryarka"))
        first = simulate(decisions, dataset)
        second = simulate(decisions, dataset)
        self.assertIsNot(first.before.district_scores, first.after.district_scores)
        self.assertIsNot(first.indicator_deltas["esil"], first.districts_after[0].indicators)
        self.assertIsNot(first.districts_after[0].indicators,
                         next(d for d in dataset.districts if d.id == "esil").indicators)

        first.before.district_scores["nura"] = -1
        first.after.district_scores["nura"] = -2
        first.districts_after[0].indicators["T1"] = -3
        first.indicator_deltas["nura"]["S1"] = -4
        self.assertEqual(dataset, original)
        self.assertGreater(second.before.district_scores["nura"], 0)
        self.assertGreater(second.after.district_scores["nura"], 0)
        self.assertGreater(second.districts_after[0].indicators["T1"], 0)
        self.assertGreater(second.indicator_deltas["nura"]["S1"], 0)


if __name__ == "__main__":
    unittest.main()
