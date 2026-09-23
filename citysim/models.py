"""Shared API v1. Changes require an API: commit and docs/API.md update."""

from dataclasses import dataclass
from typing import Literal

Direction = Literal["transport", "ecology", "social", "safety", "services"]
Scope = Literal["district", "city"]


@dataclass(frozen=True)
class District:
    id: str
    name: str
    population_share: float
    indicators: dict[str, float]


@dataclass(frozen=True)
class Measure:
    id: str
    name: str
    direction: Direction
    scope: Scope
    cost: int
    lag: int
    effects: dict[str, float]


@dataclass(frozen=True)
class Dataset:
    districts: tuple[District, ...]
    measures: tuple[Measure, ...]
    weights: dict[str, float]
    budget: int = 100
    horizon: int = 8


@dataclass(frozen=True)
class Decision:
    measure_id: str
    district_id: str | None = None


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    cost: int
    errors: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class ScoreResult:
    district_scores: dict[str, float]
    d_avg: float
    d_min: float
    n_crit: int
    score: float


@dataclass(frozen=True)
class Effect:
    """Applied delta before final clipping; source is M1 or e.g. M10+M12."""

    source: str
    district_id: str
    indicator: str
    delta: float


@dataclass(frozen=True)
class SimulationResult:
    decisions: tuple[Decision, ...]
    cost: int
    remaining_budget: int
    before: ScoreResult
    after: ScoreResult
    districts_after: tuple[District, ...]
    indicator_deltas: dict[str, dict[str, float]]
    effects: tuple[Effect, ...]
    score_delta: float
    is_baseline: bool = False


@dataclass(frozen=True)
class Explanation:
    text: str
    mode: Literal["demo", "openai"]
    warning: str | None = None
