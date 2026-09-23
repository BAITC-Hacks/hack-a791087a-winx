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
    mode = os.getenv('DEMO_MODE', 'auto').strip().lower()
    if mode in {'0', 'false', 'no', 'off'}:
        return False
    if mode == 'auto':
        return not (os.getenv('OPENAI_API_KEY', '').strip() and
                    os.getenv('OPENAI_MODEL', '').strip())
    return True


def _mode_caption() -> str:
    mode = os.getenv('DEMO_MODE', 'auto').strip().lower()
    model = os.getenv('OPENAI_MODEL', '').strip()
    configured = bool(os.getenv('OPENAI_API_KEY', '').strip() and model)
    if mode == 'auto' and not configured:
        return 'OpenAI не настроен. Сейчас работает локальный режим; настройте ключ и модель по README, чтобы включить OpenAI.'
    if mode in {'1', 'true', 'yes', 'on'} or (mode not in {'auto', '0', 'false', 'no', 'off'}):
        return 'Демонстрационный режим включён: ответы готовятся локально, OpenAI не вызывается.'
    if not configured:
        return 'OpenAI включён настройкой, но ключ или модель не заданы. При запросе появится локальный ответ с предупреждением.'
    return f'OpenAI настроен · модель {model}. Запрос отправится только после нажатия соответствующей кнопки; при сбое появится локальный ответ.'


def _explain(result):
    return ai.explain_result(result, demo_mode=_demo_enabled(),
                             api_key=os.getenv('OPENAI_API_KEY'), model=os.getenv('OPENAI_MODEL'))


def _show_explanation(explanation):
    st.caption('Ответ ИИ получен от OpenAI.' if explanation.mode == 'openai'
               else 'Локальное объяснение по правилам модели города.')
    if explanation.warning:
        st.warning(explanation.warning)
    st.markdown(explanation.text)


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
    st.session_state.plan_notice = 'Вариант B стал планом A. Черновик обновлён, прежнее сравнение удалено.'


def _keep_a():
    st.session_state.scenario_state = keep_a(st.session_state.scenario_state)
    st.session_state.scene_state = 'A'
    st.session_state.scene_diff_only = False
    st.session_state.plan_notice = 'План A оставлен. Вариант B удалён, текущий черновик сохранён.'


st.set_page_config(page_title='Аким на 5 часов', page_icon='🏙️', layout='wide')
st.title('Аким на 5 часов')
st.markdown('''Вы распределяете общий бюджет **100 условных единиц** между пятью городскими мерами. Расчёт оценивает состояние города через **8 кварталов (2 года)**.

**Как пройти сценарий:** выберите меры или подставьте пример → рассчитайте план A → прочитайте изменения и объяснение → при желании создайте вариант B и сравните его с A. Каждый расчёт показывает модельную оценку, а не обещание реального эффекта.''')
st.info('**A** — ваш сохранённый план. **B** — вариант для сравнения; он заменит A, только если вы сами выберете действие «Сделать B новым планом A».')
dataset = load_dataset()
baseline = engine.baseline(dataset)
district_names = {district.id: district.name for district in dataset.districts}

budget, score, critical = st.columns(3)
budget.metric('Бюджет на пять мер', dataset.budget)
score.metric('Общий балл исходного города', f'{baseline.after.score:.4f}', help='Формула: 70% среднего балла с учётом долей населения районов + 30% балла самого слабого района − 1 балл за каждую пару «район и показатель» ниже 40.')
critical.metric('Значений ниже 40', baseline.after.n_crit, help='Считаются пары «район и показатель». В исходных данных оба таких значения находятся в Нуре.')
st.caption(_mode_caption())

st.session_state.setdefault('scenario_state', ScenarioState())
if notice := st.session_state.pop('plan_notice', None):
    st.success(notice)
decisions = render_decisions(dataset)
state = set_draft(st.session_state.scenario_state, decisions)
validation = engine.validate_scenario(decisions, dataset)
draft_cost, draft_remaining = st.columns(2)
draft_cost.metric('Цена выбранных мер', validation.cost)
draft_remaining.metric('Останется из бюджета', dataset.budget - validation.cost)
calculate_column, compare_column = st.columns(2)
calculate = calculate_column.button('Рассчитать и сохранить план A', type='primary', key='calculate',
                                    help='Считает текущие пять решений. Новый расчёт заменит прежний A и удалит связанный вариант B и проверку.')
calculate_b = compare_column.button('Рассчитать текущий выбор как B', key='save_manual_b',
                                   disabled=state.plan_a is None,
                                   help='Сохраняет текущий черновик как альтернативу для сравнения. Сохранённый план A останется прежним.')
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
            st.success('План A рассчитан и сохранён. Предыдущие B и проверка удалены.')
        else:
            state = save_b(state, computed)
            st.session_state.scene_state = 'B'
            st.success('Вариант B рассчитан из текущего выбора. План A остался без изменений.')
st.session_state.scenario_state = state
if validation.valid:
    st.caption('Пять мер и правила бюджета проверены. Новый результат появится после нажатия кнопки расчёта.')
elif decisions or calculate or calculate_b:
    for issue in validation.errors:
        st.error(issue.message)
else:
    st.info('Выберите пять мер и район для каждой районной меры или начните с готового примера.')

if state.plan_a is not None:
    st.divider()
    if not draft_matches_saved(state):
        st.warning('Вы изменили выбор. Ниже показан прежний сохранённый план A. Чтобы увидеть результат нового выбора, рассчитайте и сохраните его.')
    render_result(state.plan_a, dataset)
    st.subheader('3. Разберите результат плана A')
    st.caption('Объяснение относится к сохранённому A. Все числовые результаты рассчитаны по модели города.')
    if st.button('Показать объяснение результата', key='explain_plan',
                 help='В локальном режиме ответ готовится без API. В режиме OpenAI будет отправлен отдельный запрос; при сбое появится локальное объяснение.'):
        with st.spinner('Готовим объяснение сохранённого плана…'):
            st.session_state.plan_explanation = _explain(state.plan_a)
    if st.session_state.get('plan_explanation') is not None:
        _show_explanation(st.session_state.plan_explanation)

    st.subheader('4. Найдите и сравните вариант B')
    st.caption('Поиск сравнит варианты с сохранённым A, даже если текущий выбор изменён. Изменение условий удалит прежний B и предыдущую проверку.')
    measures = {m.id: m.name for m in dataset.measures}
    decisions_by_id = {d.measure_id: d for d in state.plan_a.decisions}
    locked_ids = st.multiselect(
        'Какие решения A оставить без изменений', list(decisions_by_id), key='review_locked',
        format_func=lambda mid: f'{measures[mid]} · {district_names.get(decisions_by_id[mid].district_id, "Весь город")}',
    )
    if st.session_state.get('review_max_changes') not in (0, 1):
        st.session_state.review_max_changes = 1
    max_changes = st.selectbox('Сколько решений можно изменить', [0, 1], index=None, key='review_max_changes',
                               format_func=lambda count: 'Не менять ни одного' if count == 0 else 'Можно изменить одно')
    max_changes = max_changes if max_changes in (0, 1) else 1
    constraints = ReviewConstraints(tuple(d for d in state.plan_a.decisions if d.measure_id in locked_ids), max_changes)
    state = set_constraints(state, constraints)
    st.caption('Поиск вариантов работает локально без обращения к API.' if _demo_enabled()
               else 'По кнопке отправится до двух запросов OpenAI. При сбое приложение попробует найти варианты локально.')
    if st.button('Подобрать вариант B для плана A', key='run_review', type='primary',
                 help='Проверит до 20 вариантов. Найденный B будет только предложен; он станет A, только если вы его примете.'):
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
        accept_column.button('Сделать B новым планом A', key='accept_b', on_click=_accept_b, type='primary',
                             help='Заменит A выбранным B, загрузит его решения в форму и удалит старое сравнение.')
        keep_column.button('Удалить B и оставить A', key='keep_a', on_click=_keep_a,
                           help='Удалит вариант B и проверку. План A и текущий черновик сохранятся.')

with st.expander(f'Каталог мер · {len(dataset.measures)}'):
    st.dataframe([
        {'Код': measure.id, 'Мера': measure.name, 'Направление': DIRECTIONS[measure.direction],
         'Охват': 'город' if measure.scope == 'city' else 'район',
         'Стоимость': measure.cost, 'Задержка, кварталы': measure.lag}
        for measure in dataset.measures
    ], hide_index=True, width='stretch')

st.divider()
st.subheader('Посмотрите на город')
st.caption('Выберите исходный город или сохранённый план A/B, затем показатель и направление. Текущий черновик появится здесь только после расчёта.')
scene_states = {'baseline': baseline}
if state.plan_a is not None:
    scene_states['A'] = state.plan_a
if state.plan_b is not None:
    scene_states['B'] = state.plan_b
scene_labels = {'baseline': 'Исходное состояние', 'A': 'Сохранённый план A', 'B': 'Предложение B'}
if st.session_state.get('scene_state') not in scene_states:
    st.session_state.scene_state = 'baseline'
scene_id = st.radio('Что показать', list(scene_states), index=None,
                    format_func=scene_labels.get, horizontal=True, key='scene_state')
if scene_id not in scene_states:
    scene_id = 'baseline'
scene_result = scene_states[scene_id]
layer = st.radio('Направление', list(LAYERS), index=2, format_func=DIRECTIONS.get,
                 horizontal=True, key='scene_layer')
if st.session_state.get('scene_indicator') not in LAYERS[layer]:
    st.session_state.scene_indicator = LAYERS[layer][0]
indicator = st.selectbox(
    'Показатель', list(LAYERS[layer]), index=None,
    format_func=lambda code: f'{code} · {INDICATORS[code]}', key='scene_indicator',
)
if indicator not in LAYERS[layer]:
    indicator = LAYERS[layer][0]
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
