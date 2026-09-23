"""Pure scenario validation and simulation using the official dataset rules."""

from collections import Counter
from copy import deepcopy
from collections.abc import Mapping, Sequence
from dataclasses import replace

from citysim.models import (
    Dataset, Decision, District, Effect, ScoreResult, SimulationResult,
    ValidationIssue, ValidationResult,
)


# Fixed bonuses from DATASET.md, applied in the first measure's district.
SYNERGIES = (("M1", "M2", "T1", 2.0), ("M10", "M12", "B1", 2.0),
             ("M5", "M6", "E2", 2.0))
DIRECTION_NAMES = {
    "transport": "Транспорт", "ecology": "Экология", "social": "Соцсфера",
    "safety": "Безопасность", "services": "Сервисы",
}


class InvalidScenarioError(ValueError):
    def __init__(self, validation: ValidationResult):
        self.validation = validation
        super().__init__("; ".join(issue.message for issue in validation.errors))


def compute_score(
    districts: Sequence[District], weights: Mapping[str, float],
) -> ScoreResult:
    """Score already computed indicators; no effects or rounding here."""
    scores = {
        district.id: sum(weights[key] * district.indicators[key] for key in weights)
        for district in districts
    }
    d_avg = sum(d.population_share * scores[d.id] for d in districts)
    d_min = min(scores.values())
    n_crit = sum(d.indicators[key] < 40 for d in districts for key in weights)
    return ScoreResult(scores, d_avg, d_min, n_crit, .7 * d_avg + .3 * d_min - n_crit)


def baseline(dataset: Dataset) -> SimulationResult:
    """Reference state only; zero decisions is NOT a valid submitted scenario."""
    result = compute_score(dataset.districts, dataset.weights)
    return SimulationResult(
        decisions=(), cost=0, remaining_budget=dataset.budget,
        before=result, after=deepcopy(result),
        districts_after=deepcopy(dataset.districts),
        indicator_deltas={d.id: {key: 0.0 for key in dataset.weights} for d in dataset.districts},
        effects=(), score_delta=0.0, is_baseline=True,
    )


def validate_scenario(decisions: Sequence[Decision], dataset: Dataset) -> ValidationResult:
    """Collect all applicable rule violations without calculating any Score."""
    measures = {measure.id: measure for measure in dataset.measures}
    districts = {district.id: district for district in dataset.districts}
    errors: list[ValidationIssue] = []
    counts = Counter(decision.measure_id for decision in decisions)
    directions: Counter[str] = Counter()
    targets: dict[str, set[str]] = {}
    cost = 0

    if len(decisions) != 5:
        errors.append(ValidationIssue(
            "decision_count", f"Нужно выбрать ровно 5 мер; выбрано {len(decisions)}.",
        ))
    for measure_id, count in counts.items():
        if count > 1:
            errors.append(ValidationIssue(
                "duplicate_measure", f"Мера {measure_id} выбрана {count} раз; повторы запрещены.",
            ))

    for decision in decisions:
        measure = measures.get(decision.measure_id)
        if measure is None:
            errors.append(ValidationIssue(
                "unknown_measure", f"Неизвестная мера: {decision.measure_id}.",
            ))
            continue
        cost += measure.cost
        directions[measure.direction] += 1
        if measure.scope == "city":
            if decision.district_id is not None:
                errors.append(ValidationIssue(
                    "district_forbidden", f"Для городской меры {measure.id} район не указывается.",
                ))
        elif decision.district_id is None:
            errors.append(ValidationIssue(
                "district_required", f"Для меры {measure.id} необходимо выбрать район.",
            ))
        elif decision.district_id not in districts:
            errors.append(ValidationIssue(
                "unknown_district", f"Неизвестный район для меры {measure.id}: {decision.district_id!r}.",
            ))
        else:
            targets.setdefault(measure.id, set()).add(decision.district_id)

    if cost > dataset.budget:
        errors.append(ValidationIssue(
            "budget_exceeded", f"Стоимость {cost} превышает бюджет {dataset.budget}.",
        ))
    for direction, count in directions.items():
        if count > 2:
            errors.append(ValidationIssue(
                "direction_limit",
                f"В направлении «{DIRECTION_NAMES[direction]}» выбрано {count} мер; максимум 2.",
            ))
    if "M1" in counts and "M3" in counts:
        errors.append(ValidationIssue(
            "incompatible_measures", "Меры M1 и M3 несовместимы в любых районах: выберите одну.",
        ))
    for first, second in (("M4", "M7"), ("M5", "M13")):
        for district_id in sorted(targets.get(first, set()) & targets.get(second, set())):
            errors.append(ValidationIssue(
                "incompatible_measures",
                f"Меры {first} и {second} несовместимы в одном районе: {districts[district_id].name}.",
            ))
    return ValidationResult(cost, tuple(errors))


def simulate(decisions: Sequence[Decision], dataset: Dataset) -> SimulationResult:
    """Validate, sum lagged effects and fixed bonuses, clip once, then score."""
    validation = validate_scenario(decisions, dataset)
    if not validation.valid:
        raise InvalidScenarioError(validation)

    canonical = tuple(sorted(decisions, key=lambda d: (int(d.measure_id[1:]), d.district_id or "")))
    measures = {measure.id: measure for measure in dataset.measures}
    selected = {decision.measure_id: decision for decision in canonical}
    effects: list[Effect] = []
    for decision in canonical:
        measure = measures[decision.measure_id]
        targets = (tuple(d.id for d in dataset.districts) if measure.scope == "city"
                   else (decision.district_id,))
        fraction = (dataset.horizon - measure.lag) / dataset.horizon
        for district_id in targets:
            for indicator, full_delta in measure.effects.items():
                effects.append(Effect(measure.id, district_id, indicator, full_delta * fraction))

    for first, second, indicator, delta in SYNERGIES:
        if first in selected and second in selected:
            effects.append(Effect(
                f"{first}+{second}", selected[first].district_id, indicator, delta,
            ))
    effects.sort(key=lambda e: (
        tuple(int(part[1:]) for part in e.source.split("+")), e.district_id, e.indicator,
    ))

    totals = {d.id: {key: 0.0 for key in dataset.weights} for d in dataset.districts}
    for effect in effects:
        totals[effect.district_id][effect.indicator] += effect.delta
    districts_after = tuple(
        replace(d, indicators={
            key: min(100.0, max(0.0, value + totals[d.id][key]))
            for key, value in d.indicators.items()
        })
        for d in dataset.districts
    )
    indicator_deltas = {
        before.id: {key: after.indicators[key] - before.indicators[key] for key in dataset.weights}
        for before, after in zip(dataset.districts, districts_after)
    }
    before = compute_score(dataset.districts, dataset.weights)
    after = compute_score(districts_after, dataset.weights)
    return SimulationResult(
        decisions=canonical, cost=validation.cost, remaining_budget=dataset.budget - validation.cost,
        before=before, after=after, districts_after=districts_after,
        indicator_deltas=indicator_deltas, effects=tuple(effects),
        score_delta=after.score - before.score,
    )
