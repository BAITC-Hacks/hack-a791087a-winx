"""Five decisions, a saved calculated plan, and grounded explanations."""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from citysim import ai, engine, reviewer
from citysim.data import load_dataset
from citysim.review_models import ReviewConstraints
from components.city3d import render_city
from ui.forms import render_decisions
from ui.labels import DIRECTIONS, INDICATORS, LAYERS
from ui.results import render_result
from ui.review import render_review_result
from ui.scene import build_scene_details, build_scene_payload
from ui.state import (ScenarioState, accept_b, draft_matches_saved, keep_a, save_a,
                      save_b, save_review, set_constraints, set_draft)

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


def _reset_review_controls():
    st.session_state.review_locked = []
    st.session_state.review_max_changes = 1
    st.session_state.scene_diff_only = False


def _accept_b():
    state = accept_b(st.session_state.scenario_state)
    st.session_state.scenario_state = state
    for index, decision in enumerate(state.draft):
        st.session_state[f'measure_{index}'] = decision.measure_id
        st.session_state[f'district_{index}'] = decision.district_id
    _reset_review_controls()
    st.session_state.pop('plan_explanation', None)
    st.session_state.pop('plan_review', None)
    st.session_state.scene_state = 'A'
    st.session_state.plan_notice = 'План B принят как новый A. Черновик обновлён, прежняя ревизия очищена.'


def _keep_a():
    st.session_state.scenario_state = keep_a(st.session_state.scenario_state)
    st.session_state.scene_state = 'A'
    st.session_state.scene_diff_only = False
    st.session_state.plan_notice = 'План A оставлен. Предложение B удалено; черновик сохранён.'


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
if notice := st.session_state.pop('plan_notice', None):
    st.success(notice)
decisions = render_decisions(dataset)
state = set_draft(st.session_state.scenario_state, decisions)
validation = engine.validate_scenario(decisions, dataset)
draft_cost, draft_remaining = st.columns(2)
draft_cost.metric('Стоимость черновика', validation.cost)
draft_remaining.metric('Остаток по черновику', dataset.budget - validation.cost)
calculate_column, compare_column = st.columns(2)
calculate = calculate_column.button('Рассчитать и сохранить A', type='primary', key='calculate')
calculate_b = compare_column.button('Рассчитать черновик как B', key='save_manual_b',
                                   disabled=state.plan_a is None,
                                   help='Сохраняет альтернативу для сравнения; план A остаётся прежним.')
if (calculate or calculate_b) and validation.valid:
    try:
        computed = engine.simulate(decisions, dataset)
    except engine.InvalidScenarioError as error:
        validation = error.validation
    else:
        if calculate:
            state = save_a(state, computed)
            _reset_review_controls()
            st.session_state.scene_state = 'A'
            st.session_state.pop('plan_explanation', None)
            st.session_state.pop('plan_review', None)
            st.success('План A рассчитан и сохранён.')
        else:
            state = save_b(state, computed)
            st.session_state.scene_state = 'B'
            st.success('План B рассчитан из черновика. План A сохранён без изменений.')
st.session_state.scenario_state = state
if validation.valid:
    st.caption('Набор прошёл проверку правил. Расчёт выполняется по кнопке.')
elif decisions or calculate or calculate_b:
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

    st.subheader('4. Проверка плана и альтернатива B')
    st.caption('Ревизор проверяет сохранённый A, даже если черновик изменён. Изменение ограничений очищает прежние B и ревизию.')
    measures = {m.id: m.name for m in dataset.measures}
    decisions_by_id = {d.measure_id: d for d in state.plan_a.decisions}
    locked_ids = st.multiselect(
        'Какие решения A нельзя менять', list(decisions_by_id), key='review_locked',
        format_func=lambda mid: f'{mid} · {measures[mid]} · {district_names.get(decisions_by_id[mid].district_id, "Весь город")}',
    )
    if st.session_state.get('review_max_changes') not in (0, 1):
        st.session_state.review_max_changes = 1
    max_changes = st.selectbox('Сколько решений разрешено заменить', [0, 1], index=None, key='review_max_changes')
    constraints = ReviewConstraints(tuple(d for d in state.plan_a.decisions if d.measure_id in locked_ids), max_changes)
    state = set_constraints(state, constraints)
    st.caption('Режим ревизора: demo — локальный поиск без API.' if _demo_enabled()
               else 'Режим ревизора: OpenAI — до двух API-запросов по кнопке; при ошибке используется локальный поиск.')
    if st.button('Проверить план A', key='run_review', type='primary'):
        try:
            with st.spinner('Проверяем альтернативы сохранённому A…'):
                review, explanation = reviewer.review_scenario(
                    state.plan_a, dataset, state.constraints, demo_mode=_demo_enabled(),
                    api_key=os.getenv('OPENAI_API_KEY'), model=os.getenv('OPENAI_MODEL'))
                state = save_review(state, review, explanation)
                st.session_state.scene_state = 'B'
        except Exception:
            st.error('Новая проверка не выполнена. Сохранённые A и B не изменены. Попробуйте ещё раз.')
    st.session_state.scenario_state = state
    render_review_result(state, dataset)
    if state.plan_b is not None:
        accept_column, keep_column = st.columns(2)
        accept_column.button('Принять B как новый A', key='accept_b', on_click=_accept_b, type='primary')
        keep_column.button('Оставить A', key='keep_a', on_click=_keep_a)

with st.expander(f'Каталог мер · {len(dataset.measures)}'):
    st.dataframe([
        {'Код': measure.id, 'Мера': measure.name, 'Направление': DIRECTIONS[measure.direction],
         'Охват': 'город' if measure.scope == 'city' else 'район',
         'Стоимость': measure.cost, 'Лаг': measure.lag}
        for measure in dataset.measures
    ], hide_index=True, width='stretch')

st.divider()
st.subheader('Город в 3D')
st.caption('Переключайте сохранённые A и B или исходный город. Черновик не меняет макет до расчёта.')
scene_states = {'baseline': baseline}
if state.plan_a is not None:
    scene_states['A'] = state.plan_a
if state.plan_b is not None:
    scene_states['B'] = state.plan_b
scene_labels = {'baseline': 'Исходное состояние', 'A': 'Сохранённый план A', 'B': 'Предложение B'}
if st.session_state.get('scene_state') not in scene_states:
    st.session_state.scene_state = 'baseline'
scene_id = st.radio('Состояние города', list(scene_states), index=None,
                    format_func=scene_labels.get, horizontal=True, key='scene_state')
scene_result = scene_states[scene_id]
layer = st.radio('Слой города', list(LAYERS), index=2, format_func=DIRECTIONS.get,
                 horizontal=True, key='scene_layer')
if st.session_state.get('scene_indicator') not in LAYERS[layer]:
    st.session_state.scene_indicator = LAYERS[layer][0]
indicator = st.selectbox(
    'Показатель на 3D-макете', list(LAYERS[layer]), index=None,
    format_func=lambda code: f'{code} · {INDICATORS[code]}', key='scene_indicator',
)
st.session_state.setdefault('selected_city_district', 'nura')
can_compare = state.plan_a is not None and state.plan_b is not None and scene_id != 'baseline'
if not can_compare:
    st.session_state.scene_diff_only = False
diff_only = st.checkbox('Только различия A/B по выбранному показателю', key='scene_diff_only', disabled=not can_compare)
display_states = {'A': state.plan_a, 'B': state.plan_b} if can_compare else {scene_id: scene_result}
payload = build_scene_payload(dataset, display_states, selected_indicator=indicator,
                              selected_district=st.session_state.selected_city_district, diff_only=diff_only)
event = render_city(payload, active_state=scene_id)
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
    a_values = {d.id: d.indicators[indicator] for d in state.plan_a.districts_after} if can_compare else {}
    b_values = {d.id: d.indicators[indicator] for d in state.plan_b.districts_after} if can_compare else {}
    st.dataframe([
        {'Район': district.name, 'Показатель': f'{indicator} · {INDICATORS[indicator]}',
         'Значение на сцене': district.indicators[indicator],
         'Районный балл': scene_result.after.district_scores[district.id],
         **({'A': a_values[district.id], 'B': b_values[district.id],
             'B − A': b_values[district.id]-a_values[district.id]} if can_compare else {})}
        for district in scene_result.districts_after
    ], hide_index=True, width='stretch')

details = build_scene_details(scene_result, dataset, indicator, st.session_state.selected_city_district)
with st.expander(f'Меры и эффекты: {selected_name} · {indicator}', expanded=True):
    st.caption(f'{scene_labels[scene_id]} · {INDICATORS[indicator]}. Меры отобраны по их показателям в каталоге; эффекты и синергии — из движка.')
    if details['measures']:
        st.dataframe(details['measures'], hide_index=True, width='stretch')
    else:
        st.caption('В этом плане нет прямых мер для выбранного района и показателя.')
    if details['effects']:
        st.dataframe(details['effects'], hide_index=True, width='stretch')
        st.caption('Эффекты указаны до ограничения 0–100; итоговые значения доступны в сцене и таблице.')
    else:
        st.caption('Для этого выбора нет применённых эффектов.')

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
