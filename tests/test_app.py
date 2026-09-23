"""Real calculation journeys with offline AI and persistent saved plans."""
import os
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from citysim.engine import InvalidScenarioError
from citysim.models import Explanation, ValidationIssue, ValidationResult

ROOT = Path(__file__).resolve().parents[1]

class ApplicationSmokeTest(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'DEMO_MODE': '1', 'OPENAI_API_KEY': '', 'OPENAI_MODEL': ''})
        env.start()
        self.addCleanup(env.stop)
        network = patch('openai.OpenAI', side_effect=AssertionError('No API in demo'))
        network.start()
        self.addCleanup(network.stop)

    def open_app(self):
        app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=20)
        self.assertFalse(app.exception)
        return app

    def reference(self, app):
        app.button(key='load_reference').click().run()
        self.assertFalse(app.exception)
        return app

    def test_initial_empty_draft_and_baseline(self):
        app = self.open_app()
        self.assertTrue(any(m.value == '52.5577' for m in app.metric))
        self.assertIsNone(app.session_state['scenario_state'].plan_a)
        self.assertEqual(app.session_state['scenario_state'].draft, ())
        for i in range(5):
            self.assertIsNone(app.selectbox(key=f'measure_{i}').value)

    def test_reference_calculation_and_persistent_demo_explanation(self):
        from citysim.ai import explain_result
        app = self.reference(self.open_app())
        with patch('citysim.ai.explain_result', wraps=explain_result) as explain:
            app.button(key='calculate').click().run()
            self.assertFalse(app.exception)
            result = app.session_state['scenario_state'].plan_a
            self.assertEqual((result.cost, result.remaining_budget, result.after.n_crit), (95, 5, 0))
            self.assertAlmostEqual(result.after.score, 56.54307, places=7)
            explain.assert_not_called()
            app.button(key='explain_plan').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(explain.call_count, 1)
            self.assertTrue(any('56.5431' in item.value for item in app.markdown))
            app.radio(key='scene_layer').set_value('ecology').run()
            app.selectbox(key='scene_indicator').set_value('E1').run()
            self.assertEqual(explain.call_count, 1)
            self.assertTrue(any('56.5431' in item.value for item in app.markdown))

    def test_district_to_city_drops_district(self):
        app = self.open_app()
        app.selectbox(key='measure_0').set_value('M7').run()
        app.selectbox(key='district_0').set_value('nura').run()
        self.assertEqual(app.session_state['scenario_state'].draft[0].district_id, 'nura')
        app.selectbox(key='measure_0').set_value('M12').run()
        self.assertFalse(app.exception)
        self.assertFalse(any(w.key == 'district_0' for w in app.selectbox))
        self.assertIsNone(app.session_state['scenario_state'].draft[0].district_id)

    def test_duplicate_choices_excluded_from_other_slots(self):
        app = self.open_app()
        app.selectbox(key='measure_0').set_value('M7').run()
        self.assertFalse(any(o.startswith('M7 ·') for o in app.selectbox(key='measure_1').options))
        self.assertEqual(app.selectbox(key='measure_0').value, 'M7')

    def test_over_budget_never_simulates_or_calls_ai(self):
        app = self.open_app()
        for i, (measure, district) in enumerate([
            ('M3', 'esil'), ('M5', 'saryarka'), ('M2', None), ('M12', None), ('M11', 'almaty'),
        ]):
            app.selectbox(key=f'measure_{i}').set_value(measure).run()
            if district:
                app.selectbox(key=f'district_{i}').set_value(district).run()
        with patch('citysim.engine.simulate') as simulate, patch('citysim.ai.explain_result') as explain:
            app.button(key='calculate').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('бюджет' in e.value.lower() for e in app.error))
            self.assertIsNone(app.session_state['scenario_state'].plan_a)
            simulate.assert_not_called()
            explain.assert_not_called()

    def test_invalid_edit_preserves_saved_plan_and_explanation(self):
        app = self.reference(self.open_app())
        app.button(key='calculate').click().run()
        app.button(key='explain_plan').click().run()
        saved = deepcopy(app.session_state['scenario_state'].plan_a)
        with patch('citysim.engine.simulate') as simulate, patch('citysim.ai.explain_result') as explain:
            app.selectbox(key='measure_0').set_value(None).run()
            app.button(key='calculate').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['scenario_state'].plan_a, saved)
            self.assertTrue(any('черновик' in w.value.lower() for w in app.warning))
            self.assertTrue(app.error)
            self.assertTrue(any('56.5431' in item.value for item in app.markdown))
            simulate.assert_not_called()
            explain.assert_not_called()

    def test_engine_exception_preserves_previous_result(self):
        app = self.reference(self.open_app())
        app.button(key='calculate').click().run()
        saved = deepcopy(app.session_state['scenario_state'].plan_a)
        rejected = ValidationResult(101, (ValidationIssue('budget_exceeded', 'Бюджет превышен.'),))
        with patch('citysim.engine.simulate', side_effect=InvalidScenarioError(rejected)), patch('citysim.ai.explain_result') as explain:
            app.button(key='calculate').click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Бюджет превышен' in e.value for e in app.error))
            self.assertEqual(app.session_state['scenario_state'].plan_a, saved)
            explain.assert_not_called()

    def test_new_calculation_clears_old_explanation(self):
        app = self.reference(self.open_app())
        app.button(key='calculate').click().run()
        with patch('citysim.ai.explain_result', return_value=Explanation('OLD_EXPLANATION', 'demo')):
            app.button(key='explain_plan').click().run()
        self.assertTrue(any('OLD_EXPLANATION' in m.value for m in app.markdown))
        app.selectbox(key='district_0').set_value('esil').run()
        app.button(key='calculate').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(any('OLD_EXPLANATION' in m.value for m in app.markdown))
        self.assertTrue(any(d.measure_id == 'M7' and d.district_id == 'esil' for d in app.session_state['scenario_state'].plan_a.decisions))

    def test_scene_switches_saved_a_and_baseline_without_using_draft(self):
        with patch('components.city3d.render_city', return_value={}) as scene:
            app = self.open_app()
            self.assertEqual(scene.call_args.args[0]['states'][0]['id'], 'baseline')
            app = self.reference(app)
            app.button(key='calculate').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.radio(key='scene_state').value, 'A')
            saved_payload = deepcopy(scene.call_args.args[0])
            snapshot = saved_payload['states'][0]
            self.assertEqual(snapshot['id'], 'A')
            self.assertEqual(snapshot['score'], app.session_state['scenario_state'].plan_a.after.score)
            nura = next(d for d in snapshot['districts'] if d['id'] == 'nura')
            self.assertEqual((nura['indicators']['S1'], nura['indicators']['S2']), (48, 43.75))
            app.selectbox(key='measure_0').set_value('M3').run()
            self.assertEqual(scene.call_args.args[0], saved_payload)
            app.radio(key='scene_state').set_value('baseline').run()
            self.assertEqual(scene.call_args.args[0]['states'][0]['id'], 'baseline')
            nura = next(d for d in scene.call_args.args[0]['states'][0]['districts'] if d['id'] == 'nura')
            self.assertEqual(nura['indicators']['S1'], 38)
            app.radio(key='scene_state').set_value('A').run()
            self.assertEqual(scene.call_args.args[0], saved_payload)

    def test_scene_clear_and_context_error_keep_data_available(self):
        with patch('components.city3d.render_city', return_value={}) as scene:
            app = self.reference(self.open_app())
            app.button(key='calculate').click().run()
            saved = deepcopy(app.session_state['scenario_state'].plan_a)
            scene.return_value = {'district_selected': {'district_id': None}, 'render_error': {'code': 'context_lost'}}
            app.run()
            self.assertFalse(app.exception)
            self.assertIsNone(app.session_state['selected_city_district'])
            self.assertEqual(app.session_state['scenario_state'].plan_a, saved)
            self.assertTrue(any('Все районы' in item.value for item in app.caption))
            self.assertTrue(any('контекст' in item.value.lower() for item in app.warning))
            table = next(item.value for item in app.dataframe if 'Значение на сцене' in item.value.columns)
            self.assertEqual(len(table), 5)
            self.assertEqual(table.loc[table['Район'] == 'Нура', 'Значение на сцене'].iloc[0], 48)


if __name__ == '__main__':
    unittest.main()
