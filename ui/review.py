"""Views of two saved snapshots and a bounded, verified review."""
import streamlit as st

from citysim.models import Dataset, SimulationResult
from citysim.review_models import ReviewResult
from ui.labels import INDICATORS
from ui.state import ScenarioState


def build_comparison(a: SimulationResult, b: SimulationResult, dataset: Dataset) -> dict:
    values_a = {d.id: d.indicators for d in a.districts_after}
    values_b = {d.id: d.indicators for d in b.districts_after}
    city_values = [('Стоимость', a.cost, b.cost), ('Остаток бюджета', a.remaining_budget, b.remaining_budget),
                   ('Score', a.after.score, b.after.score), ('Ncrit', a.after.n_crit, b.after.n_crit)]
    return {
        'city': [{'Показатель': label, 'A': av, 'B': bv, 'B − A': bv-av} for label,av,bv in city_values],
        'districts': [
            {'Район': d.name, 'A': a.after.district_scores[d.id], 'B': b.after.district_scores[d.id],
             'B − A': b.after.district_scores[d.id]-a.after.district_scores[d.id]} for d in dataset.districts],
        'indicators': [
            {'Район': d.name, 'Код': code, 'Показатель': INDICATORS[code], 'A': values_a[d.id][code],
             'B': values_b[d.id][code], 'B − A': values_b[d.id][code]-values_a[d.id][code]}
            for d in dataset.districts for code in dataset.weights],
    }


def review_summary(review: ReviewResult) -> dict:
    return {
        'status': 'Проверка не завершена — показан лучший из уже проверенных вариантов'
                  if review.status == 'incomplete' else 'Ограниченная проверка завершена',
        'outcome': {'improved': 'Найдено улучшение Score', 'cheaper_equal': 'Найден более дешёвый план при равном Score',
                    'unchanged': 'В проверенных вариантах улучшений нет'}[review.outcome],
        'checked': len(review.checks),
    }


def build_review_log(review: ReviewResult, dataset: Dataset) -> list[dict]:
    districts = {d.id:d.name for d in dataset.districts}
    return [
        {'№': index, 'Решения': '; '.join(f'{d.measure_id} / {districts.get(d.district_id, d.district_id or "город")}'
                                         for d in check.decisions),
         'Проверка': 'Допустим' if check.result is not None else 'Отклонён',
         'Стоимость': check.result.cost if check.result is not None else None,
         'Score': check.result.after.score if check.result is not None else None,
         'Причины': '; '.join(f'{error.code}: {error.message}' for error in check.errors)}
        for index, check in enumerate(review.checks, 1)
    ]


def render_review_result(state: ScenarioState, dataset: Dataset) -> None:
    if state.review is not None:
        summary = review_summary(state.review)
        (st.warning if state.review.status == 'incomplete' else st.info)(summary['status'])
        (st.info if state.review.outcome == 'unchanged' else st.success)(summary['outcome'])
        st.caption(f"Проверено вариантов: {summary['checked']} из не более 20. Полный перебор не выполнялся.")
        if state.review_explanation is not None:
            explanation = state.review_explanation
            st.caption('Источник предложений: OpenAI' if explanation.mode == 'openai' else 'Источник предложений: demo — локальный поиск')
            st.markdown(explanation.text)
            if explanation.warning:
                st.warning(explanation.warning)
        with st.expander('Журнал проверенных вариантов'):
            rows = build_review_log(state.review, dataset)
            if rows:
                st.dataframe(rows, hide_index=True, width='stretch')
            else:
                st.caption('При этих ограничениях новые варианты не проверялись.')
    if state.plan_b is None or state.plan_a is None:
        return
    st.subheader('Сравнение сохранённых планов A и B')
    st.caption('B — предложение ревизора; A ещё не изменён.' if state.review is not None
               else 'B рассчитан из черновика вручную; A ещё не изменён.')
    comparison = build_comparison(state.plan_a, state.plan_b, dataset)
    st.dataframe(comparison['city'], hide_index=True, width='stretch')
    st.dataframe(comparison['districts'], hide_index=True, width='stretch')
    names = {d.id: d.name for d in dataset.districts}
    measures = {m.id:m.name for m in dataset.measures}
    st.dataframe([
        {'План': label, 'Код': d.measure_id, 'Мера': measures[d.measure_id],
         'Где': names.get(d.district_id, 'Весь город'),
         'Отличие': 'Только в этом плане' if d not in other.decisions else 'Общее решение'}
        for label,result,other in [('A',state.plan_a,state.plan_b),('B',state.plan_b,state.plan_a)]
        for d in result.decisions
    ], hide_index=True, width='stretch')
    with st.expander('Все показатели A/B и ухудшения'):
        st.dataframe(comparison['indicators'], hide_index=True, width='stretch')
        declines = [row for row in comparison['indicators'] if row['B − A'] < 0]
        if declines:
            st.warning('В B есть ухудшения отдельных показателей: ' + '; '.join(
                f"{r['Район']} {r['Код']}: {r['A']:g} → {r['B']:g}" for r in declines))
        else:
            st.caption('В B нет показателей ниже соответствующих значений A.')
