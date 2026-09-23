"""Five draft slots; engine validation remains authoritative."""

import streamlit as st

from citysim.models import Dataset, Decision
from ui.labels import DIRECTIONS


REFERENCE = (
    Decision("M7", "nura"), Decision("M8", "nura"), Decision("M10", "nura"),
    Decision("M12"), Decision("M5", "saryarka"),
)


def _load_reference() -> None:
    for index, decision in enumerate(REFERENCE):
        st.session_state[f"measure_{index}"] = decision.measure_id
        st.session_state[f"district_{index}"] = decision.district_id


def render_decisions(dataset: Dataset) -> tuple[Decision, ...]:
    st.subheader("1. Соберите пять решений")
    st.caption("Бюджет 100 · без повторов · не более двух мер одного направления. Покрывать все пять направлений не обязательно.")
    st.button("Заполнить пример из задания", key="load_reference", on_click=_load_reference,
              help="Заполняет только черновик. Нажмите «Рассчитать и сохранить A», чтобы получить результат.")
    measures = {measure.id: measure for measure in dataset.measures}
    districts = {district.id: district.name for district in dataset.districts}
    choices = [st.session_state.get(f"measure_{i}") for i in range(5)]
    decisions = []
    for index in range(5):
        measure_column, district_column = st.columns([3, 2])
        occupied = {value for slot, value in enumerate(choices) if slot != index and value}
        available = [None] + [mid for mid in measures if mid not in occupied or mid == choices[index]]
        with measure_column:
            measure_id = st.selectbox(
                f"Решение {index + 1} · мера", available, key=f"measure_{index}",
                format_func=lambda mid: "Выберите меру" if mid is None else f"{mid} · {measures[mid].name} · {measures[mid].cost}",
            )
        if measure_id is None:
            with district_column:
                st.caption("Сначала выберите меру")
            continue
        measure = measures[measure_id]
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
        measure_column.caption(f"{DIRECTIONS[measure.direction]} · лаг {measure.lag} кв.")
        decisions.append(Decision(measure_id, district_id))
    return tuple(decisions)
