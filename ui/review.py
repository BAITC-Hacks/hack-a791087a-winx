"""Views of two saved snapshots and a bounded, verified review."""
import streamlit as st

from citysim.models import Dataset, SimulationResult
from citysim.review_models import ReviewResult
from ui.labels import INDICATORS, MODE_LABELS
from ui.state import ScenarioState


def build_comparison(a: SimulationResult, b: SimulationResult, dataset: Dataset) -> dict:
    values_a = {d.id: d.indicators for d in a.districts_after}
    values_b = {d.id: d.indicators for d in b.districts_after}
    city_values = [('Потрачено из 100', a.cost, b.cost), ('Останется', a.remaining_budget, b.remaining_budget),
                   ('Общий балл города', a.after.score, b.after.score),
                   ('Пар «район и показатель» ниже 40', a.after.n_crit, b.after.n_crit)]
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
        'status': 'Проверка остановилась раньше срока. Ниже лучший уже проверенный вариант.'
                  if review.status == 'incomplete' else 'Проверка выбранных вариантов завершена.',
        'outcome': {'improved': 'У одного из проверенных вариантов общий балл выше',
                    'cheaper_equal': 'Есть вариант дешевле при почти таком же общем балле',
                    'unchanged': 'Среди проверенных вариантов подходящего улучшения нет'}[review.outcome],
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
        st.caption(f"Проверено вариантов: {summary['checked']} из максимум 20. Это ограниченный поиск, он не гарантирует лучший вариант из всех возможных.")
        if state.review_explanation is not None:
            explanation = state.review_explanation
            source = ('резервный локальный поиск; ранее проверенные предложения OpenAI сохранены, если были'
                      if explanation.mode == 'demo' and explanation.warning else MODE_LABELS[explanation.mode])
            st.caption(f"Как искали варианты: {source}.")
            st.markdown(explanation.text)
            if explanation.warning:
                st.warning(explanation.warning)
        with st.expander('Подробности проверки вариантов'):
            rows = build_review_log(state.review, dataset)
            if rows:
                st.dataframe(rows, hide_index=True, width='stretch')
            else:
                st.caption('При этих ограничениях новые варианты не проверялись.')
    if state.plan_b is None or state.plan_a is None:
        return
    st.subheader('Сравнение плана A и варианта B')
    st.caption('B предложен автоматической проверкой; A пока сохранён отдельно.' if state.review is not None
               else 'B рассчитан из текущего черновика; A пока сохранён отдельно.')
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
    declines = [row for row in comparison['indicators'] if row['B − A'] < 0]
    if declines:
        st.warning('В варианте B снизятся отдельные показатели: ' + '; '.join(
            f"{r['Район']} — {r['Показатель']}: {r['A']:g} → {r['B']:g}" for r in declines))
    else:
        st.caption('Ни один показатель в B не ниже соответствующего значения A.')
    with st.expander('Все показатели и возможные ухудшения'):
        st.dataframe(comparison['indicators'], hide_index=True, width='stretch')
