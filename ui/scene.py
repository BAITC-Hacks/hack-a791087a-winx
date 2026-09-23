"""Build and validate the Python boundary for the version 1 scene protocol."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict
import math
from typing import Any

from citysim.engine import validate_scenario
from citysim.models import Dataset, ScoreResult, SimulationResult
from citysim.review_models import (
    SCENE_SCHEMA_VERSION,
    SceneEvents,
    ScenePayload,
    SceneState,
)


_STATE_ORDER = ("baseline", "A", "B")
_RENDER_ERROR_CODES = frozenset({
    "webgl_unavailable", "context_lost", "render_failed", "unsupported_schema",
})


def build_scene_details(result: SimulationResult, dataset: Dataset, indicator: str,
                        district_id: str | None) -> dict:
    """Filter catalog measures and applied engine effects for the chosen indicator."""
    names = {d.id: d.name for d in dataset.districts}
    if indicator not in dataset.weights or (district_id is not None and district_id not in names):
        raise ValueError('Unknown scene selection')
    measures = {m.id: m for m in dataset.measures}
    return {
        'measures': [
            {'Код': d.measure_id, 'Мера': measures[d.measure_id].name,
             'Где': names.get(d.district_id, 'Весь город'), 'Лаг, кварталы': measures[d.measure_id].lag}
            for d in result.decisions if indicator in measures[d.measure_id].effects
            and (district_id is None or d.district_id in (None, district_id))],
        'effects': [
            {'Источник': e.source, 'Район': names[e.district_id], 'Показатель': e.indicator,
             'Эффект до ограничения 0–100': e.delta}
            for e in result.effects if e.indicator == indicator
            and (district_id is None or e.district_id == district_id)],
    }


def _finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _validate_result(result: SimulationResult, state_id: str, dataset: Dataset) -> None:
    if not isinstance(result, SimulationResult):
        raise ValueError(f"State {state_id!r} must be a SimulationResult")
    if type(result.is_baseline) is not bool or result.is_baseline != (state_id == "baseline"):
        raise ValueError(f"State {state_id!r} has an inconsistent baseline marker")
    if not isinstance(result.before, ScoreResult) or not isinstance(result.after, ScoreResult):
        raise ValueError(f"State {state_id!r} has invalid score results")
    if state_id == "baseline":
        if result.decisions:
            raise ValueError("Baseline state must not contain decisions")
    else:
        try:
            validation = validate_scenario(result.decisions, dataset)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(f"State {state_id!r} has malformed decisions") from exc
        if not validation.valid:
            raise ValueError(f"State {state_id!r} has invalid decisions")

    if not isinstance(result.cost, int) or isinstance(result.cost, bool):
        raise ValueError(f"State {state_id!r} has an invalid cost")
    if not isinstance(result.remaining_budget, int) or isinstance(result.remaining_budget, bool):
        raise ValueError(f"State {state_id!r} has an invalid remaining budget")
    score_values = (
        result.before.d_avg, result.before.d_min, result.before.score,
        result.after.d_avg, result.after.d_min, result.after.score,
    )
    if any(not _finite_number(value) for value in score_values):
        raise ValueError(f"State {state_id!r} has a non-finite score")
    if not _finite_number(result.score_delta):
        raise ValueError(f"State {state_id!r} has a non-finite score delta")

    district_ids = tuple(district.id for district in dataset.districts)
    indicator_keys = tuple(dataset.weights)
    if tuple(district.id for district in result.districts_after) != district_ids:
        raise ValueError(f"State {state_id!r} has districts in an invalid order")
    if tuple(result.after.district_scores) != district_ids:
        raise ValueError(f"State {state_id!r} has district scores in an invalid shape")
    for district, expected in zip(result.districts_after, dataset.districts):
        if district.name != expected.name or tuple(district.indicators) != indicator_keys:
            raise ValueError(f"State {state_id!r} has an invalid district shape")
        if any(not _finite_number(value) or not 0 <= value <= 100
               for value in district.indicators.values()):
            raise ValueError(f"State {state_id!r} has an indicator outside 0..100")
    for scores in (result.before.district_scores, result.after.district_scores):
        if tuple(scores) != district_ids or any(not _finite_number(score) for score in scores.values()):
            raise ValueError(f"State {state_id!r} has invalid district scores")

    if tuple(result.indicator_deltas) != district_ids:
        raise ValueError(f"State {state_id!r} has deltas in an invalid shape")
    for deltas in result.indicator_deltas.values():
        if tuple(deltas) != indicator_keys or any(not _finite_number(value) for value in deltas.values()):
            raise ValueError(f"State {state_id!r} has invalid indicator deltas")
    if any(not _finite_number(effect.delta) for effect in result.effects):
        raise ValueError(f"State {state_id!r} has a non-finite effect delta")


def _scene_state(result: SimulationResult, state_id: str, dataset: Dataset) -> SceneState:
    _validate_result(result, state_id, dataset)
    labels = {
        "baseline": "Исходное состояние",
        "A": "Сохранённый план A",
        "B": "Сохранённый план B",
    }
    return {
        "id": state_id,  # type: ignore[typeddict-item]
        "label": labels[state_id],
        "is_baseline": result.is_baseline,
        "decisions": [asdict(decision) for decision in result.decisions],
        "cost": result.cost,
        "remaining_budget": result.remaining_budget,
        "score": result.after.score,
        "districts": [
            {"id": district.id, "name": district.name, "indicators": deepcopy(district.indicators)}
            for district in result.districts_after
        ],
        "district_scores": deepcopy(result.after.district_scores),
    }


def build_scene_payload(
    dataset: Dataset,
    states: Mapping[str, SimulationResult] | SimulationResult,
    *,
    selected_indicator: str = "S1",
    selected_district: str | None = None,
    diff_only: bool = False,
) -> ScenePayload:
    """Build a copied scene payload from saved simulation snapshots."""
    if not isinstance(selected_indicator, str) or selected_indicator not in dataset.weights:
        raise ValueError(f"Unknown indicator: {selected_indicator!r}")
    district_ids = {district.id for district in dataset.districts}
    if selected_district is not None and (
        not isinstance(selected_district, str) or selected_district not in district_ids
    ):
        raise ValueError(f"Unknown district: {selected_district!r}")
    if type(diff_only) is not bool:
        raise ValueError("diff_only must be a bool")

    if isinstance(states, SimulationResult):
        state_id = "baseline" if states.is_baseline else "A"
        state_map: Mapping[str, SimulationResult] = {state_id: states}
    elif isinstance(states, Mapping):
        state_map = states
    else:
        raise ValueError("states must be a SimulationResult or a mapping of saved states")

    if not state_map:
        raise ValueError("At least one saved state is required")
    if any(not isinstance(state_id, str) or state_id not in _STATE_ORDER for state_id in state_map):
        raise ValueError("Unknown scene state id")
    if "B" in state_map and "A" not in state_map:
        raise ValueError("State B requires state A")
    if diff_only and not {"A", "B"}.issubset(state_map):
        raise ValueError("diff_only requires states A and B")

    scene_states = [
        _scene_state(state_map[state_id], state_id, dataset)
        for state_id in _STATE_ORDER if state_id in state_map
    ]
    return {
        "schema_version": SCENE_SCHEMA_VERSION,
        "states": scene_states,
        "selected_indicator": selected_indicator,
        "selected_district": selected_district,
        "diff_only": diff_only,
    }


def _get(value: object, key: str) -> tuple[bool, Any]:
    if isinstance(value, Mapping):
        return key in value, value.get(key)
    try:
        return hasattr(value, key), getattr(value, key, None)
    except Exception:
        return False, None


def normalize_scene_events(event: object, district_ids: object) -> SceneEvents:
    """Copy only known, valid component events into a SceneEvents dictionary."""
    try:
        known_districts = set(district_ids)  # type: ignore[arg-type]
    except TypeError:
        known_districts = set()
    normalized: SceneEvents = {}
    for key in ("district_selected", "render_error"):
        present, value = _get(event, key)
        if not present:
            continue
        if value is None:
            normalized[key] = None  # type: ignore[literal-required]
            continue
        field = "district_id" if key == "district_selected" else "code"
        has_field, field_value = _get(value, field)
        if not has_field:
            continue
        if key == "district_selected":
            if field_value is None or (
                isinstance(field_value, str) and field_value in known_districts
            ):
                normalized[key] = {"district_id": field_value}
        elif isinstance(field_value, str) and field_value in _RENDER_ERROR_CODES:
            normalized[key] = {"code": field_value}  # type: ignore[typeddict-item]
    return normalized


def validate_district_selection(event: object, dataset: Dataset) -> str | None:
    """Return a known district id from an event, ignoring malformed events."""
    if not isinstance(event, dict):
        return None
    district_id = event.get("district_id")
    if not isinstance(district_id, str):
        return None
    if district_id not in {district.id for district in dataset.districts}:
        return None
    return district_id
