"""C0 contracts for the bounded reviewer and the JSON scene protocol.

The search and the scene renderer are separate milestones. These types and pure
rules can already be consumed without importing Streamlit or an AI provider.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, TypedDict

from citysim.engine import simulate
from citysim.models import Dataset, Decision, SimulationResult, ValidationIssue


EPS = 1e-9
MAX_REVIEW_ROUNDS = 2
MAX_CANDIDATES_PER_ROUND = 10
MAX_REVIEW_CANDIDATES = MAX_REVIEW_ROUNDS * MAX_CANDIDATES_PER_ROUND
SCENE_SCHEMA_VERSION: Literal[1] = 1

ReviewStatus = Literal["completed_limited", "incomplete"]
ReviewOutcome = Literal["improved", "cheaper_equal", "unchanged"]
SceneStateId = Literal["baseline", "A", "B"]
SceneErrorCode = Literal["webgl_unavailable", "context_lost", "render_failed", "unsupported_schema"]


@dataclass(frozen=True)
class ReviewConstraints:
    """Exact source pairs to retain; C0 supports zero or one replacement."""

    locked: tuple[Decision, ...] = ()
    max_changes: int = 1


@dataclass(frozen=True)
class CandidateCheck:
    """A rejected candidate has errors and result=None; accepted ones have no errors."""

    decisions: tuple[Decision, ...]
    errors: tuple[ValidationIssue, ...]
    result: SimulationResult | None


@dataclass(frozen=True)
class ReviewResult:
    """Completion and outcome are independent; no status claims global optimality."""

    source: SimulationResult
    best: SimulationResult
    checks: tuple[CandidateCheck, ...]
    status: ReviewStatus
    outcome: ReviewOutcome
    constraints: ReviewConstraints


def validate_review_input(
    source: SimulationResult, dataset: Dataset, constraints: ReviewConstraints,
) -> None:
    """Reject invalid inputs before either numerical search or an external AI call.

    Recompute the source once to detect stale data or manually changed numbers.
    No candidate is generated here; S1 remains responsible for the actual search.
    """
    if not isinstance(source, SimulationResult):
        raise ValueError("Исходный план должен быть SimulationResult.")
    if not isinstance(constraints, ReviewConstraints):
        raise ValueError("Ограничения должны быть ReviewConstraints.")
    if source.is_baseline:
        raise ValueError("baseline — ориентир, а не исходный сценарий из пяти решений.")
    if type(constraints.max_changes) is not int or constraints.max_changes not in (0, 1):
        raise ValueError("max_changes должен быть целым числом 0 или 1.")
    if not isinstance(constraints.locked, tuple) or not all(
        isinstance(decision, Decision) for decision in constraints.locked
    ):
        raise ValueError("locked должен быть кортежем Decision.")
    locked = set(constraints.locked)
    if len(locked) != len(constraints.locked):
        raise ValueError("Закреплённые решения не должны повторяться.")
    if not locked.issubset(source.decisions):
        raise ValueError("Закрепить можно только точные пары мера/район исходного плана A.")
    if source != simulate(source.decisions, dataset):
        raise ValueError("Исходный результат не соответствует расчёту текущего датасета.")


def check_candidate_constraints(
    source: SimulationResult, decisions: Sequence[Decision], constraints: ReviewConstraints,
) -> tuple[ValidationIssue, ...]:
    """Check user restrictions against original A after validate_review_input.

    Always also run engine.validate_scenario: this does not check count, budget,
    IDs or compatibility. The change formula applies to valid five-decision sets.
    """
    selected = set(decisions)
    errors: list[ValidationIssue] = []
    if not set(constraints.locked).issubset(selected):
        errors.append(ValidationIssue(
            "locked_changed", "Кандидат изменяет закреплённую пару мера/район исходного плана A.",
        ))
    changes = len(set(source.decisions) - selected)
    if changes > constraints.max_changes:
        errors.append(ValidationIssue(
            "change_limit",
            f"Изменено {changes} решений исходного плана A; допустимо {constraints.max_changes}.",
        ))
    return tuple(errors)


def classify_outcome(source: SimulationResult, candidate: SimulationResult) -> ReviewOutcome:
    """Compare engine-produced results with original A, never the previous best."""
    difference = candidate.after.score - source.after.score
    if difference > EPS:
        return "improved"
    if abs(difference) <= EPS and candidate.cost < source.cost:
        return "cheaper_equal"
    return "unchanged"


class SceneDecision(TypedDict):
    measure_id: str
    district_id: str | None


class SceneDistrict(TypedDict):
    id: str
    name: str
    indicators: dict[str, float]


class SceneState(TypedDict):
    id: SceneStateId
    label: str
    is_baseline: bool
    decisions: list[SceneDecision]
    cost: int
    remaining_budget: int
    score: float
    districts: list[SceneDistrict]
    district_scores: dict[str, float]


class ScenePayload(TypedDict):
    """JSON-compatible data; ui.scene owns construction and runtime validation."""

    schema_version: Literal[1]
    states: list[SceneState]
    selected_indicator: str
    selected_district: str | None
    diff_only: bool


class DistrictSelectedEvent(TypedDict):
    district_id: str | None


class RenderErrorEvent(TypedDict):
    code: SceneErrorCode


class SceneEvents(TypedDict, total=False):
    district_selected: DistrictSelectedEvent | None
    render_error: RenderErrorEvent | None
