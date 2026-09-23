"""The Streamlit boundary returns only typed, recognized scene events."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from citysim.data import load_dataset
from citysim.engine import baseline
from components.city3d import render_city
from ui.scene import build_scene_payload


class SceneComponentTest(unittest.TestCase):
    def setUp(self):
        dataset = load_dataset()
        self.payload = build_scene_payload(dataset, baseline(dataset))

    def test_normalizes_component_result_and_preserves_clear_event(self):
        component = Mock(return_value=SimpleNamespace(
            district_selected={'district_id': None, 'unexpected': 'discard'},
            render_error={'code': 'context_lost'}, unrelated='discard'))
        with patch('components.city3d.st.components.v2.component', return_value=component):
            event = render_city(self.payload, key='stable-scene')
        self.assertEqual(event, {'district_selected': {'district_id': None},
                                 'render_error': {'code': 'context_lost'}})
        arguments = component.call_args.kwargs
        self.assertEqual(arguments['data']['view_key'], 'stable-scene')
        self.assertIsNone(arguments['default']['render_error'])
        self.assertNotIn('view_key', self.payload)

    def test_discards_unknown_event_values(self):
        component = Mock(return_value={'district_selected': {'district_id': 'unknown'},
                                       'render_error': {'code': 'raw exception text'}})
        with patch('components.city3d.st.components.v2.component', return_value=component):
            self.assertEqual(render_city(self.payload), {})

    def test_missing_bundle_returns_fallback_event(self):
        with TemporaryDirectory() as directory, \
                patch('components.city3d.BUILD', Path(directory)), \
                patch('components.city3d.st.warning'), \
                patch('components.city3d.st.components.v2.component') as component:
            self.assertEqual(render_city(self.payload), {'render_error': {'code': 'render_failed'}})
            component.assert_not_called()
