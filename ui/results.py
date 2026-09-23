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
    st.subheader("2. Что даст план A за 8 кварталов")
    st.caption("Показаны расчётные изменения за 8 кварталов (2 года). Score — общий балл города: учитывает средний результат с учётом долей населения, слабейший район и показатели ниже 40.")
    cost, remaining, score, critical = st.columns(4)
    cost.metric("Потрачено из 100", result.cost)
    remaining.metric("Останется", result.remaining_budget)
    score.metric("Общий балл Score", f"{result.after.score:.4f}", f"{result.score_delta:+.4f} к исходному")
    critical.metric("Показателей ниже 40", result.after.n_crit, help="Считаются пары «район и показатель». Чем меньше, тем лучше.")
    st.dataframe(passport["decisions"], hide_index=True, width="stretch", key="saved_decisions")
    st.markdown("**Город: до и после**")
    st.dataframe([
        {"Показатель": "Score", "До": f"{result.before.score:.4f}", "После": f"{result.after.score:.4f}"},
        {"Показатель": "Взвешенный средний балл", "До": f"{result.before.d_avg:.4f}", "После": f"{result.after.d_avg:.4f}"},
        {"Показатель": "Минимальный районный балл", "До": f"{result.before.d_min:.4f}", "После": f"{result.after.d_min:.4f}"},
        {"Показатель": "Пары «район и показатель» ниже 40", "До": str(result.before.n_crit), "После": str(result.after.n_crit)},
    ], hide_index=True, width="stretch")
    st.markdown(f"**Самый низкий балл среди районов:** {passport['weakest_name']} · {result.after.d_min:.4f}")
    st.dataframe(passport["districts"], hide_index=True, width="stretch", column_config={
        "До": st.column_config.NumberColumn(format="%.4f"), "После": st.column_config.NumberColumn(format="%.4f"),
    })
    if passport["resolved_critical"]:
        pairs = "; ".join(f"{row['Район']} — {row['Показатель']}: {row['До']:g} → {row['После']:g}" for row in passport["resolved_critical"])
        st.success(f"Эти значения поднялись до 40 или выше: {pairs}")
    if passport["remaining_critical"]:
        pairs = "; ".join(f"{row['Район']} — {row['Показатель']}: {row['После']:g}" for row in passport["remaining_critical"])
        st.warning(f"Эти значения всё ещё ниже 40: {pairs}")
    else:
        st.info("В расчёте не осталось значений ниже 40. Это порог модели, а не утверждение, что в городе нет проблем.")
    with st.expander("Все показатели: до, после и изменение"):
        st.dataframe(passport["indicators"], hide_index=True, width="stretch")
    with st.expander("Как меры повлияли на показатели (подробности расчёта)"):
        st.caption("Эффекты уже учитывают задержку и сочетания мер, но показаны до ограничения итоговых значений диапазоном 0–100. Итоговые изменения смотрите в таблице выше. Эффекты нельзя складывать в отдельные баллы Score.")
        st.dataframe(passport["effects"], hide_index=True, width="stretch", column_config={
            "Эффект до clip": st.column_config.NumberColumn("Применённый эффект", help="Уже с учётом задержки; до ограничения показателя диапазоном 0–100."),
        })
