"""Pure numerical core. Scenario validation/application is the next milestone."""

from copy import deepcopy
from collections.abc import Mapping, Sequence

from citysim.models import (
    Dataset, Decision, District, ScoreResult, SimulationResult, ValidationResult,
)


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
    """API v1 stub; implement all rules in docs/API.md before enabling submission."""
    raise NotImplementedError("Этап E1: валидатор ещё не реализован")


def simulate(decisions: Sequence[Decision], dataset: Dataset) -> SimulationResult:
    """API v1 stub; validate first, then effects, synergies, clipping and Score."""
    raise NotImplementedError("Этап E1: применение мер ещё не реализовано")
