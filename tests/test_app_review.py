"""End-to-end A/B actions; no provider calls during automatic reruns."""
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from citysim.models import Explanation
from citysim.data import load_dataset
from citysim.reviewer import review_scenario

ROOT = Path(__file__).resolve().parents[1]


class ReviewAppTests(unittest.TestCase):
    def setUp(self):
        for patcher in (
            patch.dict(os.environ, {'DEMO_MODE':'1','OPENAI_API_KEY':'','OPENAI_MODEL':''}),
            patch('openai.AsyncOpenAI', side_effect=AssertionError('No SDK in demo')),
            patch('openai.OpenAI', side_effect=AssertionError('No SDK in demo')),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def saved_a(self):
        app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=20)
        app.button(key='load_reference').click().run()
        app.button(key='calculate').click().run()
        self.assertFalse(app.exception)
        return app

    def test_demo_review_only_on_button_and_draft_does_not_change_a_b(self):
        with patch('citysim.reviewer.review_scenario', wraps=review_scenario) as review, \
                patch('components.city3d.render_city', return_value={}) as scene:
            app = self.saved_a()
            a = deepcopy(app.session_state['scenario_state'].plan_a)
            review.assert_not_called()
            app.button(key='run_review').click().run()
            self.assertFalse(app.exception)
            saved = deepcopy(app.session_state['scenario_state'])
            self.assertEqual(saved.plan_a, a)
            self.assertEqual(saved.plan_b.cost, 80)
            self.assertAlmostEqual(saved.plan_b.after.score, 56.69056)
            self.assertEqual(len(saved.review.checks), 20)
            self.assertEqual(review.call_count, 1)
            app.radio(key='scene_state').set_value('B').run()
            self.assertEqual(scene.call_args.kwargs['active_state'], 'B')
            self.assertEqual([s['id'] for s in scene.call_args.args[0]['states']], ['A','B'])
            app.selectbox(key='measure_0').set_value('M3').run()
            self.assertEqual(app.session_state['scenario_state'].plan_a, a)
            self.assertEqual(app.session_state['scenario_state'].plan_b, saved.plan_b)
            self.assertEqual(review.call_count, 1)

    def test_constraints_invalidate_review_and_b_without_another_request(self):
        with patch('citysim.reviewer.review_scenario', wraps=review_scenario) as review:
            app = self.saved_a()
            app.button(key='run_review').click().run()
            app.multiselect(key='review_locked').set_value(['M5']).run()
            self.assertFalse(app.exception)
            self.assertIsNone(app.session_state['scenario_state'].review)
            self.assertIsNone(app.session_state['scenario_state'].plan_b)
            self.assertEqual(review.call_count, 1)
            app.selectbox(key='review_max_changes').set_value(0).run()
            app.button(key='run_review').click().run()
            self.assertTrue(any('Среди проверенных вариантов' in item.value for item in app.info))
            self.assertEqual(app.session_state['scenario_state'].plan_a,
                             app.session_state['scenario_state'].plan_b)

    def test_manual_b_keep_and_accept_update_form_and_clear_old_explanation(self):
        app = self.saved_a()
        a = deepcopy(app.session_state['scenario_state'].plan_a)
        app.button(key='explain_plan').click().run()
        app.selectbox(key='district_0').set_value('esil').run()
        app.button(key='save_manual_b').click().run()
        self.assertFalse(app.exception)
        b = deepcopy(app.session_state['scenario_state'].plan_b)
        self.assertNotEqual(a, b)
        self.assertEqual(app.session_state['scenario_state'].plan_a, a)
        app.button(key='keep_a').click().run()
        self.assertEqual(app.session_state['scenario_state'].plan_a, a)
        self.assertIsNone(app.session_state['scenario_state'].plan_b)
        app.button(key='save_manual_b').click().run()
        app.button(key='accept_b').click().run()
        self.assertFalse(app.exception)
        state = app.session_state['scenario_state']
        self.assertEqual(state.plan_a, b)
        self.assertIsNone(state.plan_b)
        self.assertIsNone(state.review)
        self.assertEqual(set(state.draft), set(b.decisions))
        self.assertNotIn('plan_explanation', app.session_state)
        self.assertEqual(app.radio(key='scene_state').value, 'A')

    def test_incomplete_improvement_warning_and_failure_preserve_a(self):
        app = self.saved_a()
        state = app.session_state['scenario_state']
        a = deepcopy(state.plan_a)
        review, _ = review_scenario(a, load_dataset(), state.constraints)
        with patch('citysim.reviewer.review_scenario', return_value=(
                replace(review, status='incomplete'), Explanation('Частичный результат', 'demo', 'Лимит времени'))):
            app.button(key='run_review').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('остановилась раньше срока' in item.value.lower() for item in app.warning))
        self.assertTrue(any('Лимит времени' in item.value for item in app.warning))
        self.assertFalse(app.button(key='accept_b').disabled)
        b = deepcopy(app.session_state['scenario_state'].plan_b)
        with patch('citysim.reviewer.review_scenario', side_effect=RuntimeError('PRIVATE_PROVIDER_ERROR')):
            app.button(key='run_review').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['scenario_state'].plan_a, a)
        self.assertEqual(app.session_state['scenario_state'].plan_b, b)
        self.assertFalse(any('PRIVATE_PROVIDER_ERROR' in item.value for item in app.error))

    def test_scene_layers_differences_and_fallback_share_saved_b(self):
        with patch('components.city3d.render_city', return_value={}) as scene:
            app = self.saved_a()
            app.button(key='run_review').click().run()
            app.radio(key='scene_state').set_value('B').run()
            app.radio(key='scene_layer').set_value('transport').run()
            self.assertEqual(app.selectbox(key='scene_indicator').value, 'T1')
            app.checkbox(key='scene_diff_only').check().run()
            self.assertTrue(scene.call_args.args[0]['diff_only'])
            b = deepcopy(app.session_state['scenario_state'].plan_b)
            scene.return_value = {'render_error': {'code': 'webgl_unavailable'}}
            app.run()
            self.assertFalse(app.exception)
            table = next(item.value for item in app.dataframe if 'Значение на сцене' in item.value.columns)
            self.assertEqual(table.loc[table['Район']=='Нура','Значение на сцене'].iloc[0], 53.25)
            self.assertEqual(app.session_state['scenario_state'].plan_b, b)
            app.radio(key='scene_state').set_value('baseline').run()
            self.assertFalse(scene.call_args.args[0]['diff_only'])

    def test_invalid_manual_draft_preserves_b_and_never_simulates(self):
        app = self.saved_a()
        app.button(key='run_review').click().run()
        saved = deepcopy(app.session_state['scenario_state'])
        app.selectbox(key='measure_0').set_value('M3').run()
        with patch('citysim.engine.simulate') as simulate:
            app.button(key='save_manual_b').click().run()
        self.assertFalse(app.exception)
        simulate.assert_not_called()
        self.assertEqual(app.session_state['scenario_state'].plan_a, saved.plan_a)
        self.assertEqual(app.session_state['scenario_state'].plan_b, saved.plan_b)

    def test_live_settings_are_passed_only_on_explicit_review_click(self):
        app = self.saved_a()
        state = app.session_state['scenario_state']
        response = review_scenario(state.plan_a, load_dataset(), state.constraints)
        with patch.dict(os.environ, {'DEMO_MODE':'0','OPENAI_API_KEY':'test-key','OPENAI_MODEL':'test-model'}), \
                patch('citysim.reviewer.review_scenario', return_value=response) as review:
            app.run()
            review.assert_not_called()
            app.button(key='run_review').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(review.call_count, 1)
            self.assertEqual(review.call_args.kwargs, {'demo_mode':False,'api_key':'test-key','model':'test-model'})

    def test_clearing_limit_restores_default_without_losing_saved_a(self):
        app = self.saved_a()
        a = deepcopy(app.session_state['scenario_state'].plan_a)
        app.selectbox(key='review_max_changes').set_value(None).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['scenario_state'].constraints.max_changes, 1)
        self.assertEqual(app.session_state['scenario_state'].plan_a, a)
