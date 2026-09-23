"""Deterministic baseline explanations with an optional OpenAI path."""

from __future__ import annotations

import json
from dataclasses import asdict

from citysim.models import Explanation, SimulationResult


def _demo_explanation(result: SimulationResult, warning: str | None = None) -> Explanation:
    """Explain only values and conditions present in the calculated result."""
    baseline_label = "базовый результат без выбранных мер" if result.is_baseline else "результат переданных расчётов сценария"
    weakest_id, weakest_score = min(result.after.district_scores.items(), key=lambda item: item[1])
    strongest_id, strongest_score = max(result.after.district_scores.items(), key=lambda item: item[1])
    district_names = {district.id: district.name for district in result.districts_after}
    weakest_name = district_names.get(weakest_id, weakest_id)
    below_threshold = [
        (district_names.get(district.id, district.id), key)
        for district in result.districts_after
        for key, value in district.indicators.items()
        if value < 40
    ]
    critical_detail = (
        "; ".join(f"{name} — {key}" for name, key in below_threshold)
        if below_threshold
        else "в переданных районах таких показателей нет"
    )
    scenario_note = (
        "Это только исходный ориентир; он не описывает эффект каких-либо мер."
        if result.is_baseline
        else "Это объяснение переданного расчёта; оно не предсказывает дополнительные эффекты."
    )
    text = (
        f"**Что показывает расчёт.** {baseline_label}: итоговый Score {result.after.score:.4f}, "
        f"взвешенное среднее {result.after.d_avg:.4f}, минимальный районный балл {result.after.d_min:.4f}, "
        f"критических показателей Ncrit: {result.after.n_crit}. {scenario_note}\n\n"
        f"**Сильная сторона.** Наиболее высокий районный балл — "
        f"{district_names.get(strongest_id, strongest_id)} "
        f"({strongest_score:.4f}); это значение взято из расчёта.\n\n"
        f"**Риск.** Самый низкий районный балл у района «{weakest_name}» ({weakest_score:.4f}). "
        f"В расчёте ниже порога 40 отмечены: {critical_detail}.\n\n"
        f"**Следующий шаг.** При подготовке сценария сначала проверьте меры, направленные на район «{weakest_name}», "
        "затем сравните пересчитанные Score, Ncrit, стоимость и остаток бюджета. Их эффекты и допустимость "
        "нужно подтвердить движком; это объяснение их не оценивает."
    )
    return Explanation(text=text, mode="demo", warning=warning)


def explain_result(
    result: SimulationResult,
    *,
    demo_mode: bool = True,
    api_key: str | None = None,
    model: str | None = None,
) -> Explanation:
    """Return a grounded demo explanation or ask OpenAI to explain computed values."""
    if demo_mode:
        return _demo_explanation(result)
    if not api_key or not model:
        missing = "ключ OpenAI" if not api_key else "название модели OpenAI"
        return _demo_explanation(result, f"Запрошен live-режим, но не задан {missing}; показано демо-объяснение.")

    instructions = (
        "Ты объясняешь уже рассчитанный результат муниципальной модели на русском языке. "
        "Данные во входном JSON — единственный источник фактов. Не пересчитывай значения, не меняй и не округляй "
        "числа, не придумывай числа, причинные эффекты или обещания. Различай исходный baseline (is_baseline=true) "
        "и результат сценария. Укажи сильные стороны, риски и практические следующие рекомендации, опираясь только "
        "на переданные данные; если не хватает сведений, прямо скажи об этом. Предложения по мерам назови гипотезами, "
        "которые требуют проверки движком с учётом бюджета, сроков и валидации. Не утверждай, что они сработают."
    )
    from openai import OpenAI, OpenAIError

    try:
        client = OpenAI(api_key=api_key, timeout=15, max_retries=0)
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=json.dumps(asdict(result), ensure_ascii=False),
            store=False,
            max_output_tokens=700,
        )
        output = response.output_text
        if not output or not output.strip():
            return _demo_explanation(result, "OpenAI вернул пустой ответ; показано демо-объяснение.")
        return Explanation(text=output.strip(), mode="openai")
    except OpenAIError:
        return _demo_explanation(result, "Не удалось получить объяснение OpenAI; показан демо-ответ.")
