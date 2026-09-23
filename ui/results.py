"""Passport views of the saved engine result; no simulation formulas here."""

import streamlit as st

from citysim.models import Dataset, SimulationResult
from ui.labels import DIRECTIONS, INDICATORS


def build_passport(result: SimulationResult, dataset: Dataset) -> dict:
    measures = {measure.id: measure for measure in dataset.measures}
    originals = {district.id: district for district in dataset.districts}
    names = {district.id: district.name for district in dataset.districts}
    indicators = [
        {
            "Район": district.name, "Код": code, "Показатель": INDICATORS[code],
            "До": originals[district.id].indicators[code], "После": value,
            "Изменение": result.indicator_deltas[district.id][code],
        }
        for district in result.districts_after for code, value in district.indicators.items()
    ]
    weakest_id = min(result.after.district_scores, key=result.after.district_scores.get)
    return {
        "decisions": [
            {"Код": decision.measure_id, "Мера": measures[decision.measure_id].name,
             "Где": names[decision.district_id] if decision.district_id else "Весь город",
             "Направление": DIRECTIONS[measures[decision.measure_id].direction],
             "Стоимость": measures[decision.measure_id].cost}
            for decision in result.decisions
        ],
        "districts": [
            {"Район": district.name, "До": result.before.district_scores[district.id],
             "После": result.after.district_scores[district.id]}
            for district in dataset.districts
        ],
        "indicators": indicators,
        "remaining_critical": [dict(row) for row in indicators if row["После"] < 40],
        "resolved_critical": [dict(row) for row in indicators if row["До"] < 40 <= row["После"]],
        "weakest_name": names[weakest_id],
        "effects": [
            {"Источник": effect.source, "Тип": "Синергия" if "+" in effect.source else "Мера",
             "Район": names[effect.district_id], "Код": effect.indicator,
             "Эффект до clip": effect.delta}
            for effect in result.effects
        ],
    }


def render_result(result: SimulationResult, dataset: Dataset) -> None:
    passport = build_passport(result, dataset)
    st.subheader("2. Паспорт сохранённого плана A")
    st.caption("Результат этих пяти решений за 8 кварталов. Числа рассчитаны движком по официальной модели.")
    cost, remaining, score, critical = st.columns(4)
    cost.metric("Стоимость плана A", result.cost)
    remaining.metric("Остаток бюджета A", result.remaining_budget)
    score.metric("Score плана A", f"{result.after.score:.4f}", f"{result.score_delta:+.4f}")
    critical.metric("Ncrit плана A", result.after.n_crit)
    st.dataframe(passport["decisions"], hide_index=True, width="stretch", key="saved_decisions")
    st.markdown("**Город: до и после**")
    st.dataframe([
        {"Показатель": "Score", "До": f"{result.before.score:.4f}", "После": f"{result.after.score:.4f}"},
        {"Показатель": "Взвешенный средний балл", "До": f"{result.before.d_avg:.4f}", "После": f"{result.after.d_avg:.4f}"},
        {"Показатель": "Минимальный районный балл", "До": f"{result.before.d_min:.4f}", "После": f"{result.after.d_min:.4f}"},
        {"Показатель": "Критические показатели (<40)", "До": str(result.before.n_crit), "После": str(result.after.n_crit)},
    ], hide_index=True, width="stretch")
    st.markdown(f"**Самый низкий районный балл после мер:** {passport['weakest_name']} · {result.after.d_min:.4f}")
    st.dataframe(passport["districts"], hide_index=True, width="stretch", column_config={
        "До": st.column_config.NumberColumn(format="%.4f"), "После": st.column_config.NumberColumn(format="%.4f"),
    })
    if passport["resolved_critical"]:
        pairs = "; ".join(f"{row['Район']} — {row['Код']}: {row['До']:g} → {row['После']:g}" for row in passport["resolved_critical"])
        st.success(f"Порог 40 достигнут: {pairs}")
    if passport["remaining_critical"]:
        pairs = "; ".join(f"{row['Район']} — {row['Код']}: {row['После']:g}" for row in passport["remaining_critical"])
        st.warning(f"Остаются показатели ниже 40: {pairs}")
    else:
        st.info("После мер показателей ниже 40 нет. Это критерий модели, а не отсутствие всех городских проблем.")
    with st.expander("Все показатели: до, после и изменение"):
        st.dataframe(passport["indicators"], hide_index=True, width="stretch")
    with st.expander("Почему изменились показатели: эффекты и синергии"):
        st.caption("Эффекты учитывают лаг и показаны до ограничения значений диапазоном 0–100 (clip). Фактические изменения — в таблице показателей. Эффект меры не является её отдельным вкладом в Score.")
        st.dataframe(passport["effects"], hide_index=True, width="stretch")
