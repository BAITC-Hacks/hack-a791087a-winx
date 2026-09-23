"""Immutable scenario-state transitions for the planning interface."""

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field

from citysim.models import Decision, Explanation, SimulationResult
from citysim.review_models import ReviewConstraints, ReviewResult


@dataclass(frozen=True)
class ScenarioState:
    draft: tuple[Decision, ...] = ()
    plan_a: SimulationResult | None = None
    plan_b: SimulationResult | None = None
    review: ReviewResult | None = None
    review_explanation: Explanation | None = None
    constraints: ReviewConstraints = field(default_factory=ReviewConstraints)


def _copy_state(state: ScenarioState, **changes) -> ScenarioState:
    values = {
        "draft": state.draft,
        "plan_a": state.plan_a,
        "plan_b": state.plan_b,
        "review": state.review,
        "review_explanation": state.review_explanation,
        "constraints": state.constraints,
    }
    values.update(changes)
    return ScenarioState(**deepcopy(values))


def _constraint_key(constraints: ReviewConstraints) -> tuple[int, frozenset[Decision]]:
    return constraints.max_changes, frozenset(constraints.locked)


def _validate_constraints(constraints: ReviewConstraints, plan_a: SimulationResult | None) -> None:
    if not isinstance(constraints, ReviewConstraints):
        raise ValueError("constraints must be ReviewConstraints")
    if type(constraints.max_changes) is not int or constraints.max_changes not in (0, 1):
        raise ValueError("max_changes must be 0 or 1")
    if not isinstance(constraints.locked, tuple) or not all(
        isinstance(decision, Decision) for decision in constraints.locked
    ):
        raise ValueError("locked must be a tuple of Decision")
    if len(set(constraints.locked)) != len(constraints.locked):
        raise ValueError("locked decisions must be unique")
    if plan_a is None and constraints.locked:
        raise ValueError("locked decisions require a saved plan A")
    if plan_a is not None and not set(constraints.locked).issubset(plan_a.decisions):
        raise ValueError("locked decisions must be exact pairs from saved plan A")


def set_draft(state: ScenarioState, decisions: Iterable[Decision]) -> ScenarioState:
    """Return a state with a new draft and independent saved snapshots."""
    return _copy_state(state, draft=tuple(decisions))


def save_a(state: ScenarioState, result: SimulationResult) -> ScenarioState:
    """Save a simulation as A and reset B, review, and review constraints."""
    if result.is_baseline:
        raise ValueError("A baseline cannot be saved as a plan.")
    return _copy_state(
        state, plan_a=result, plan_b=None, review=None, review_explanation=None,
        constraints=ReviewConstraints(),
    )


def save_b(state: ScenarioState, result: SimulationResult) -> ScenarioState:
    """Save a manually selected non-baseline simulation as B."""
    if state.plan_a is None:
        raise ValueError("Plan A must be saved before plan B.")
    if result.is_baseline:
        raise ValueError("A baseline cannot be saved as plan B.")
    return _copy_state(state, plan_b=result, review=None, review_explanation=None)


def save_review(
    state: ScenarioState, review: ReviewResult, explanation: Explanation,
) -> ScenarioState:
    """Save a review only when it belongs to the current A and constraints."""
    if state.plan_a is None:
        raise ValueError("Plan A must be saved before a review.")
    if not isinstance(review, ReviewResult) or not isinstance(explanation, Explanation):
        raise ValueError("review and explanation must have their expected types")
    if review.source != state.plan_a:
        raise ValueError("Review source does not match saved plan A")
    if _constraint_key(review.constraints) != _constraint_key(state.constraints):
        raise ValueError("Review constraints do not match current constraints")
    _validate_constraints(state.constraints, state.plan_a)
    if review.best.is_baseline:
        raise ValueError("A baseline cannot be saved as plan B")
    return _copy_state(state, review=review, review_explanation=explanation, plan_b=review.best)


def set_constraints(state: ScenarioState, constraints: ReviewConstraints) -> ScenarioState:
    """Set valid A-relative review constraints and invalidate stale results."""
    _validate_constraints(constraints, state.plan_a)
    if _constraint_key(constraints) == _constraint_key(state.constraints):
        return _copy_state(state)
    return _copy_state(
        state, constraints=constraints, plan_b=None, review=None, review_explanation=None,
    )


def accept_b(state: ScenarioState) -> ScenarioState:
    """Promote B to A and make its decisions the current draft."""
    if state.plan_a is None or state.plan_b is None:
        raise ValueError("Plans A and B are required to accept B")
    return ScenarioState(draft=deepcopy(state.plan_b.decisions), plan_a=deepcopy(state.plan_b))


def keep_a(state: ScenarioState) -> ScenarioState:
    """Discard B and review while retaining A, draft, and current constraints."""
    if state.plan_a is None or state.plan_b is None:
        raise ValueError("Plans A and B are required to keep A")
    return _copy_state(state, plan_b=None, review=None, review_explanation=None)


def draft_matches_saved(state: ScenarioState) -> bool:
    """Whether draft matches A decisions, regardless of order."""
    if state.plan_a is None:
        return False
    key = lambda decision: (decision.measure_id, decision.district_id or "")
    return sorted(state.draft, key=key) == sorted(state.plan_a.decisions, key=key)
