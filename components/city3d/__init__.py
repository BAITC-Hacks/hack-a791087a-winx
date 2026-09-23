"""Streamlit bridge for the locally bundled baseline 3D prototype."""

from pathlib import Path

import streamlit as st

BUILD = Path(__file__).resolve().parent / 'build'


def render_city(payload: dict, *, key: str = 'city3d'):
    """Mount trusted local assets; data travels separately from executable code."""
    js = BUILD / 'city3d.js'
    css = BUILD / 'city3d.css'
    if not js.is_file() or not css.is_file():
        st.warning('3D-сборка отсутствует. Показатели города доступны в таблице ниже.')
        return None
    component = st.components.v2.component(
        'city_view',
        html='<section class="city-root" aria-label="Трёхмерный макет пяти районов"></section>',
        js=js.read_text(encoding='utf-8'),
        css=css.read_text(encoding='utf-8'),
    )
    return component(
        data={**payload, 'view_key': key},
        key=key,
        height='content',
        default={'district_selected': {'district_id': payload['selected_district']}},
        on_district_selected_change=lambda: None,
        on_render_error_change=lambda: None,
    )
