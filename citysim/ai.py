"""Deterministic baseline explanations with an optional OpenAI path."""

from __future__ import annotations

import json
from dataclasses import asdict

from citysim.models import Explanation, SimulationResult


def _demo_explanation(result: SimulationResult, warning: str | None = None) -> Explanation:
    """Explain only values and conditions present in the calculated result."""
    weakest_id, weakest_score = min(result.after.district_scores.items(), key=lambda item: item[1])
    strongest_id, strongest_score = max(result.after.district_scores.items(), key=lambda item: item[1])
    district_names = {district.id: district.name for district in result.districts_after}
    weakest_name = district_names.get(weakest_id, weakest_id)
    if result.is_baseline:
        below_threshold = [
            (district_names.get(district.id, district.id), key)
            for district in result.districts_after
            for key, value in district.indicators.items()
            if value < 40
        ]
        critical_detail = (
            "; ".join(f"{name} — {key}" for name, key in below_threshold)
            if below_threshold else "в переданных районах таких показателей нет"
        )
        text = (
            f"**Что показывает расчёт.** Базовый результат без выбранных мер: итоговый Score "
            f"{result.after.score:.4f}, взвешенное среднее {result.after.d_avg:.4f}, "
            f"минимальный районный балл {result.after.d_min:.4f}, критических показателей "
            f"Ncrit: {result.after.n_crit}. Это только исходный ориентир; он не описывает эффект мер.\n\n"
            f"**Сильная сторона.** Наиболее высокий районный балл — "
            f"{district_names.get(strongest_id, strongest_id)} ({strongest_score:.4f}).\n\n"
            f"**Риск.** Самый низкий районный балл у района «{weakest_name}» ({weakest_score:.4f}). "
            f"Ниже порога 40 отмечены: {critical_detail}.\n\n"
            f"**Следующий шаг.** При подготовке сценария проверьте меры для района «{weakest_name}» "
            "и сравните новые Score, Ncrit, стоимость и остаток бюджета после расчёта движком."
        )
        return Explanation(text=text, mode="demo", warning=warning)

    def critical_pairs(*, before: bool) -> list[str]:
        pairs = []
        for district in result.districts_after:
            name = district_names.get(district.id, district.id)
            for indicator, after_value in district.indicators.items():
                value = after_value - result.indicator_deltas[district.id][indicator] if before else after_value
                if value < 40:
                    pairs.append(f"{name} — {indicator}")
        return pairs

    before_critical = critical_pairs(before=True)
    after_critical = critical_pairs(before=False)
    before_detail = "; ".join(before_critical) if before_critical else "нет"
    after_detail = "; ".join(after_critical) if after_critical else "нет"
    changed = [
        (district_names.get(district_id, district_id), indicator, delta)
        for district_id, values in result.indicator_deltas.items()
        for indicator, delta in values.items()
        if delta
    ]
    positive = sorted((item for item in changed if item[2] > 0), key=lambda item: item[2], reverse=True)[:3]
    negative = sorted((item for item in changed if item[2] < 0), key=lambda item: item[2])[:3]

    def describe_deltas(items: list[tuple[str, str, float]]) -> str:
        return "; ".join(f"{name} — {indicator} {delta:+.4f}" for name, indicator, delta in items)

    positive_detail = describe_deltas(positive) if positive else "положительных изменений индикаторов нет"
    negative_detail = describe_deltas(negative) if negative else "отрицательных изменений индикаторов нет"
    negative_sources = []
    for name, indicator, delta in negative:
        district_id = next((key for key, label in district_names.items() if label == name), None)
        sources = sorted({
            effect.source for effect in result.effects
            if effect.district_id == district_id and effect.indicator == indicator and effect.delta < 0
        })
        if sources:
            negative_sources.append(f"{', '.join(sources)}: {name} — {indicator}")
    source_detail = (
        f" Отрицательные прибавки до ограничения в трассировке: {'; '.join(negative_sources)}."
        if negative_sources else ""
    )
    score_sign = "+" if result.score_delta > 0 else ""
    text = (
        f"**Результат сценария.** Стоимость {result.cost}, остаток бюджета {result.remaining_budget}; "
        f"Score до {result.before.score:.4f}, после {result.after.score:.4f} "
        f"(изменение {score_sign}{result.score_delta:.4f}). Ncrit: {result.before.n_crit} → "
        f"{result.after.n_crit}; критические пары до: {before_detail}, после: {after_detail}.\n\n"
        f"**Сильная сторона.** Наибольший районный балл после расчёта у района "
        f"«{district_names.get(strongest_id, strongest_id)}» ({strongest_score:.4f}). "
        f"Фактические положительные дельты индикаторов: {positive_detail}.\n\n"
        f"**Риски и компромисс.** Самый низкий районный балл после расчёта у района "
        f"«{weakest_name}» ({weakest_score:.4f}). Фактические отрицательные дельты индикаторов: "
        f"{negative_detail}.{source_detail} Прибавки в трассировке мер указаны до ограничения диапазона; "
        "дельты индикаторов — фактическое «после минус до». Это не линейные вклады в Score.\n\n"
        f"**Следующий шаг.** Проверьте альтернативы для района «{weakest_name}» и сравните их "
        "пересчитанные Score, критические пары, стоимость и остаток бюджета. Предложенные изменения "
        "нужно проверить движком; этот расчёт сам по себе не доказывает будущий эффект."
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
        "Данные во входном JSON — единственный источник фактов. Не пересчитывай значения, не меняй числа и не "
        "придумывай числа, причинные эффекты, прогнозы или обещания. Различай baseline и сценарий. Для сценария "
        "объясни стоимость и остаток бюджета, Score до и после, Ncrit и конкретные пары район/индикатор ниже 40 "
        "до и после, сильные стороны, риски и компромиссы. Используй indicator_deltas как фактические изменения "
        "«после минус до», а effects — как прибавки до ограничения значений; не смешивай эти числа и не называй "
        "их линейными вкладами в Score. Не утверждай, что улучшился каждый критерий, и не заявляй оптимальность. "
        "Дай практический следующий шаг только на основе этих данных; предложения по мерам назови гипотезами, "
        "которые требуется перепроверить движком. Если данных недостаточно, прямо скажи об этом."
    )
    # Luna defaults to medium reasoning, which can consume the whole text budget.
    # Do not infer support for 'none' from another model's name or family.
    luna = model == "gpt-6-luna"
    if luna:
        instructions += " Ответь кратко, до 250 слов: результат, сильные стороны, риски, следующий шаг."
    from openai import OpenAI, OpenAIError

    try:
        client = OpenAI(api_key=api_key, timeout=15, max_retries=0)
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=json.dumps(asdict(result), ensure_ascii=False),
            store=False,
            max_output_tokens=1600 if luna else 700,
            **({"reasoning": {"effort": "none"}} if luna else {}),
        )
        if response.status != "completed":
            return _demo_explanation(result, "OpenAI не завершил ответ; показано демо-объяснение.")
        output = response.output_text
        if not output or not output.strip():
            return _demo_explanation(result, "OpenAI вернул пустой ответ; показано демо-объяснение.")
        return Explanation(text=output.strip(), mode="openai")
    except OpenAIError:
        return _demo_explanation(result, "Не удалось получить объяснение OpenAI; показан демо-ответ.")
