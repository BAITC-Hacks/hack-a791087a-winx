"""Five decisions, a saved calculated plan, and grounded explanations."""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from citysim import ai, engine
from citysim.data import load_dataset
from components.city3d import render_city
from ui.forms import render_decisions
from ui.labels import DIRECTIONS, INDICATORS
from ui.results import render_result
from ui.scene import build_scene_payload
from ui.state import ScenarioState, draft_matches_saved, save_a, set_draft

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env', override=False)


def _demo_enabled() -> bool:
    return os.getenv('DEMO_MODE', '1').strip().lower() not in {'0', 'false', 'no', 'off'}


def _explain(result):
    return ai.explain_result(result, demo_mode=_demo_enabled(),
                             api_key=os.getenv('OPENAI_API_KEY'), model=os.getenv('OPENAI_MODEL'))


def _show_explanation(explanation):
    st.caption(f'Режим объяснения: {explanation.mode}')
    st.markdown(explanation.text)
    if explanation.warning:
        st.warning(explanation.warning)


st.set_page_config(page_title='Аким на 5 часов', page_icon='🏙️', layout='wide')
st.title('Аким на 5 часов')
st.caption('Пять решений для города · выберите меры, рассчитайте последствия и сохраните свой план')
dataset = load_dataset()
baseline = engine.baseline(dataset)
district_names = {district.id: district.name for district in dataset.districts}

budget, score, critical = st.columns(3)
budget.metric('Доступный бюджет', dataset.budget)
score.metric('Базовый Score', f'{baseline.after.score:.4f}')
critical.metric('Ncrit исходного города', baseline.after.n_crit, help='Число пар район/показатель со значением ниже 40')

st.session_state.setdefault('scenario_state', ScenarioState())
decisions = render_decisions(dataset)
state = set_draft(st.session_state.scenario_state, decisions)
validation = engine.validate_scenario(decisions, dataset)
draft_cost, draft_remaining = st.columns(2)
draft_cost.metric('Стоимость черновика', validation.cost)
draft_remaining.metric('Остаток по черновику', dataset.budget - validation.cost)
calculate = st.button('Рассчитать и сохранить A', type='primary', key='calculate')
if calculate and validation.valid:
    try:
        computed = engine.simulate(decisions, dataset)
    except engine.InvalidScenarioError as error:
        validation = error.validation
    else:
        state = save_a(state, computed)
        st.session_state.scene_state = 'A'
        st.session_state.pop('plan_explanation', None)
        st.session_state.pop('plan_review', None)
        st.success('План A рассчитан и сохранён.')
st.session_state.scenario_state = state
if validation.valid:
    st.caption('Набор прошёл проверку правил. Расчёт выполняется по кнопке.')
elif decisions or calculate:
    for issue in validation.errors:
        st.error(issue.message)
else:
    st.info('Выберите пять мер и районы для районных мер или начните с примера из задания.')

if state.plan_a is not None:
    st.divider()
    if not draft_matches_saved(state):
        st.warning('Черновик изменён. Ниже сохранённый план A и объяснение именно этого плана. Чтобы обновить результат, рассчитайте черновик заново.')
    render_result(state.plan_a, dataset)
    st.subheader('3. Объяснение плана A')
    st.caption('Объяснение относится к сохранённым решениям. Числа в паспорте берутся из движка.')
    if st.button('Объяснить сохранённый план A', key='explain_plan'):
        with st.spinner('Готовим объяснение сохранённого плана…'):
            st.session_state.plan_explanation = _explain(state.plan_a)
    if st.session_state.get('plan_explanation') is not None:
        _show_explanation(st.session_state.plan_explanation)

with st.expander(f'Каталог мер · {len(dataset.measures)}'):
    st.dataframe([
        {'Код': measure.id, 'Мера': measure.name, 'Направление': DIRECTIONS[measure.direction],
         'Охват': 'город' if measure.scope == 'city' else 'район',
         'Стоимость': measure.cost, 'Лаг': measure.lag}
        for measure in dataset.measures
    ], hide_index=True, width='stretch')

st.divider()
st.subheader('Город в 3D')
st.caption('Сравните исходный город с сохранённым планом A. Изменения черновика попадут на макет после расчёта.')
scene_states = {'baseline': baseline}
if state.plan_a is not None:
    scene_states['A'] = state.plan_a
scene_labels = {'baseline': 'Исходное состояние', 'A': 'Сохранённый план A'}
if st.session_state.get('scene_state') not in scene_states:
    st.session_state.scene_state = 'baseline'
scene_id = st.radio('Состояние города', list(scene_states),
                    format_func=scene_labels.get, horizontal=True, key='scene_state')
scene_result = scene_states[scene_id]
indicator = st.selectbox(
    'Показатель на 3D-макете', list(INDICATORS), index=4,
    format_func=lambda code: f'{code} · {INDICATORS[code]}', key='scene_indicator',
)
st.session_state.setdefault('selected_city_district', 'nura')
payload = build_scene_payload(dataset, {scene_id: scene_result}, selected_indicator=indicator,
                              selected_district=st.session_state.selected_city_district)
event = render_city(payload)
if event.get('district_selected') is not None:
    selected = event['district_selected']['district_id']
    if selected != st.session_state.selected_city_district:
        st.session_state.selected_city_district = selected
        st.rerun()
render_error = event.get('render_error')
if render_error:
    error_messages = {
        'webgl_unavailable': 'Браузер не смог запустить WebGL.',
        'context_lost': 'Потерян графический контекст 3D.',
        'render_failed': 'Не удалось отрисовать 3D-макет.',
        'unsupported_schema': 'Версия данных сцены не поддерживается.',
    }
    st.warning(f"{error_messages[render_error['code']]} Показатели выбранного состояния доступны в таблице ниже.")
selected_name = district_names.get(st.session_state.selected_city_district, 'Все районы')
st.caption(f'{scene_labels[scene_id]} · {selected_name}. Все числа в сцене — из расчётного движка.')
with st.expander('Показатели сцены — таблица', expanded=bool(render_error)):
    st.dataframe([
        {'Район': district.name, 'Показатель': f'{indicator} · {INDICATORS[indicator]}',
         'Значение на сцене': district.indicators[indicator],
         'Районный балл': scene_result.after.district_scores[district.id]}
        for district in scene_result.districts_after
    ], hide_index=True, width='stretch')

with st.expander('Районы: базовое состояние'):
    st.dataframe([
        {'Район': district.name, 'Базовый балл': f'{baseline.after.district_scores[district.id]:.4f}',
         'Показатели ниже 40': ', '.join(code for code, value in district.indicators.items() if value < 40) or '—'}
        for district in baseline.districts_after
    ], hide_index=True, width='stretch')
    if st.button('Объяснить базовый результат', key='explain_baseline'):
        with st.spinner('Готовим объяснение исходного города…'):
            st.session_state.baseline_explanation = _explain(baseline)
    if st.session_state.get('baseline_explanation') is not None:
        _show_explanation(st.session_state.baseline_explanation)
