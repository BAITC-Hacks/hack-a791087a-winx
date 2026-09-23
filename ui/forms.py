"""Five draft slots; engine validation remains authoritative."""

import streamlit as st

from citysim.models import Dataset, Decision
from ui.labels import DIRECTIONS, INDICATORS


REFERENCE = (
    Decision("M7", "nura"), Decision("M8", "nura"), Decision("M10", "nura"),
    Decision("M12"), Decision("M5", "saryarka"),
)


def _load_reference() -> None:
    for index, decision in enumerate(REFERENCE):
        st.session_state[f"measure_{index}"] = decision.measure_id
        st.session_state[f"district_{index}"] = decision.district_id


def render_decisions(dataset: Dataset) -> tuple[Decision, ...]:
    st.subheader("1. Выберите пять мер")
    st.caption(f"На все решения дано {dataset.budget} условных единиц. Выберите пять разных мер; из одного направления можно взять не больше двух.")
    st.button("Подставить пример из задания", key="load_reference", on_click=_load_reference,
              help="Подставляет готовый пример в пять полей. Это ещё не расчёт и не меняет сохранённый план A.")
    measures = {measure.id: measure for measure in dataset.measures}
    districts = {district.id: district.name for district in dataset.districts}
    # Old session values can remain after a slot is cleared or its option disappears.
    # Clear invalid values before constructing selectboxes so Streamlit never sees
    # a value that is absent from that widget's options.
    choices = [st.session_state.get(f"measure_{i}") for i in range(5)]
    seen = set()
    for index, value in enumerate(choices):
        if value is not None and (value not in measures or value in seen):
            st.session_state[f"measure_{index}"] = None
        elif value is not None:
            seen.add(value)
    choices = [st.session_state.get(f"measure_{i}") for i in range(5)]
    decisions = []
    for index in range(5):
        measure_column, district_column = st.columns([3, 2])
        occupied = {value for slot, value in enumerate(choices) if slot != index and value}
        available = [None] + [mid for mid in measures if mid not in occupied or mid == choices[index]]
        with measure_column:
            measure_id = st.selectbox(
                f"Решение {index + 1} · мера", available, key=f"measure_{index}",
                format_func=lambda mid: "Выберите меру" if mid is None else f"{measures[mid].name} · {measures[mid].cost} ед.",
            )
        if measure_id is None:
            with district_column:
                st.caption("Сначала выберите меру")
            continue
        measure = measures[measure_id]
        if measure.scope == "district" and st.session_state.get(f"district_{index}") not in districts:
            st.session_state[f"district_{index}"] = None
        with district_column:
            if measure.scope == "district":
                district_id = st.selectbox(
                    f"Решение {index + 1} · район", [None] + list(districts),
                    key=f"district_{index}",
                    format_func=lambda did: "Выберите район" if did is None else districts[did],
                )
            else:
                district_id = None
                st.caption("Весь город · выбор района не требуется")
        effect_names = [f"{name.lower()} {'↑' if measure.effects[code] > 0 else '↓'}"
                        for code, name in INDICATORS.items() if code in measure.effects]
        effect_text = ", ".join(effect_names) if effect_names else "—"
        scope_text = "весь город" if measure.scope == "city" else "один выбранный район"
        measure_column.caption(
            f"{DIRECTIONS[measure.direction]} · охват: {scope_text} · цена: {measure.cost} из {dataset.budget} ед. "
            f"Работает с {measure.lag}-го кв. Затрагивает (↑ улучшение, ↓ ухудшение): {effect_text}."
        )
        decisions.append(Decision(measure_id, district_id))
    return tuple(decisions)
