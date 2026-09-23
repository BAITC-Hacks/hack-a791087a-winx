"""Immutable scenario-state transitions for the planning interface."""

from copy import deepcopy
from dataclasses import dataclass
from collections.abc import Iterable

from citysim.models import Decision, SimulationResult


@dataclass(frozen=True)
class ScenarioState:
    draft: tuple[Decision, ...] = ()
    plan_a: SimulationResult | None = None
    plan_b: SimulationResult | None = None


def set_draft(state: ScenarioState, decisions: Iterable[Decision]) -> ScenarioState:
    """Return a state with a new draft and independent saved snapshots."""
    return ScenarioState(
        draft=tuple(deepcopy(tuple(decisions))),
        plan_a=deepcopy(state.plan_a),
        plan_b=deepcopy(state.plan_b),
    )


def save_a(state: ScenarioState, result: SimulationResult) -> ScenarioState:
    """Save a deep-copied simulation as plan A and clear the comparison slot."""
    if result.is_baseline:
        raise ValueError("A baseline cannot be saved as a plan.")
    return ScenarioState(
        draft=tuple(deepcopy(tuple(state.draft))),
        plan_a=deepcopy(result),
        plan_b=None,
    )


def draft_matches_saved(state: ScenarioState) -> bool:
    """Whether the draft has the same decisions as saved plan A, regardless of order."""
    if state.plan_a is None:
        return False
    key = lambda decision: (decision.measure_id, decision.district_id or "")
    return sorted(state.draft, key=key) == sorted(state.plan_a.decisions, key=key)
