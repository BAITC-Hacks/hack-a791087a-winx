"""Typed Streamlit bridge for locally bundled saved-state 3D scenes."""

from pathlib import Path

import streamlit as st
from citysim.review_models import SceneEvents, ScenePayload
from ui.scene import normalize_scene_events

BUILD = Path(__file__).resolve().parent / 'build'


def render_city(payload: ScenePayload, *, key: str = 'city3d') -> SceneEvents:
    """Mount trusted local assets; data travels separately from executable code."""
    js = BUILD / 'city3d.js'
    css = BUILD / 'city3d.css'
    if not js.is_file() or not css.is_file():
        st.warning('3D-сборка отсутствует. Показатели города доступны в таблице ниже.')
        return {'render_error': {'code': 'render_failed'}}
    component = st.components.v2.component(
        'city_view',
        html='<section class="city-root" aria-label="Трёхмерный макет пяти районов"></section>',
        js=js.read_text(encoding='utf-8'),
        css=css.read_text(encoding='utf-8'),
    )
    result = component(
        data={**payload, 'view_key': key},
        key=key,
        height='content',
        default={'district_selected': {'district_id': payload['selected_district']}, 'render_error': None},
        on_district_selected_change=lambda: None,
        on_render_error_change=lambda: None,
    )
    return normalize_scene_events(result, [district['id'] for district in payload['states'][0]['districts']])
