"""Streamlit skeleton for the five-hour Akim dashboard."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from citysim.ai import explain_result
from citysim.data import load_dataset
from citysim.engine import baseline
from components.city3d import render_city
from ui.scene import build_scene_payload, validate_district_selection


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)


def _demo_enabled() -> bool:
    return os.getenv("DEMO_MODE", "1").strip().lower() not in {"0", "false", "no", "off"}


st.set_page_config(page_title="Аким на 5 часов", page_icon="🏙️", layout="wide")
st.title("Аким на 5 часов")
st.caption("Прототип 3D · пять районов и исходные показатели города")
st.info("3D показывает исходное состояние. Выбор пяти решений и сравнение сценариев подключаются следующими этапами.", icon="ℹ️")

dataset = load_dataset()
result = baseline(dataset)

left, right = st.columns(2)
left.metric("Бюджет", f"{dataset.budget}", help="Доступно для будущего сценария")
right.metric("Базовый Score", f"{result.after.score:.4f}", help="Исходное состояние без выбранных мер")
st.metric("Ncrit", result.after.n_crit, help="Количество критических показателей в baseline")

indicator_labels = {
    "T1": "Разгрузка дорог", "T2": "Доступность общественного транспорта",
    "E1": "Озеленение", "E2": "Качество воздуха",
    "S1": "Школы и детсады", "S2": "Поликлиники и первичная медпомощь",
    "B1": "Безопасность улиц", "B2": "Безопасность дорожного движения",
    "C1": "Надёжность ЖКХ", "C2": "Скорость решения обращений жителей",
}
indicator = st.selectbox(
    "Показатель на 3D-макете", list(indicator_labels), index=4,
    format_func=lambda code: f"{code} · {indicator_labels[code]}", key="scene_indicator",
)
st.session_state.setdefault("selected_city_district", "nura")
payload = build_scene_payload(
    dataset, result, selected_indicator=indicator,
    selected_district=st.session_state.selected_city_district,
)
event = render_city(payload)
if event is not None:
    selected = validate_district_selection(event.district_selected, dataset)
    if selected and selected != st.session_state.selected_city_district:
        st.session_state.selected_city_district = selected
        st.rerun()
selected_name = next(
    district.name for district in dataset.districts
    if district.id == st.session_state.selected_city_district
)
st.caption(f"Выбран район: {selected_name}. Все числа в сцене — из расчётного движка.")

st.subheader("Районы: базовое состояние")
district_names = {district.id: district.name for district in dataset.districts}
direction_labels = {
    "transport": "Транспорт",
    "ecology": "Экология",
    "social": "Социальная сфера",
    "safety": "Безопасность",
    "services": "Городские услуги",
}
critical_by_district = {
    district.id: [key for key, value in district.indicators.items() if value < 40]
    for district in result.districts_after
}
st.dataframe(
    [
        {
            "Район": district_names[district_id],
            "Базовый балл": f"{score:.4f}",
            "Показатели ниже 40": ", ".join(critical_by_district[district_id]) or "—",
        }
        for district_id, score in result.after.district_scores.items()
    ],
    hide_index=True,
    width="stretch",
)

with st.expander(f"Каталог мер · {len(dataset.measures)}"):
    st.dataframe(
        [
            {
                "Код": measure.id,
                "Мера": measure.name,
                "Направление": direction_labels[measure.direction],
                "Охват": "город" if measure.scope == "city" else "район",
                "Стоимость": measure.cost,
                "Лаг": measure.lag,
            }
            for measure in dataset.measures
        ],
        hide_index=True,
        width="stretch",
    )

if st.button("Объяснить базовый результат"):
    explanation = explain_result(
        result,
        demo_mode=_demo_enabled(),
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL"),
    )
    st.caption(f"Режим объяснения: {explanation.mode}")
    st.markdown(explanation.text)
    if explanation.warning:
        st.warning(explanation.warning)
