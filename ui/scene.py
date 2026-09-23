"""Build scene data for the private 3D prototype."""

from dataclasses import asdict

from citysim.models import Dataset, SimulationResult


def build_scene_payload(
    dataset: Dataset,
    result: SimulationResult,
    *,
    selected_indicator: str = "S1",
    selected_district: str | None = None,
) -> dict:
    """Copy computed simulation data into the version 1 scene payload."""
    if not isinstance(selected_indicator, str) or selected_indicator not in dataset.weights:
        raise ValueError(f"Unknown indicator: {selected_indicator!r}")

    district_ids = {district.id for district in dataset.districts}
    if selected_district is not None and (
        not isinstance(selected_district, str) or selected_district not in district_ids
    ):
        raise ValueError(f"Unknown district: {selected_district!r}")

    return {
        "schema_version": 1,
        "states": [{
            "id": "baseline",
            "label": "Исходное состояние",
            "is_baseline": result.is_baseline,
            "decisions": [asdict(decision) for decision in result.decisions],
            "cost": result.cost,
            "remaining_budget": result.remaining_budget,
            "score": result.after.score,
            "districts": [
                {
                    "id": district.id,
                    "name": district.name,
                    "indicators": dict(district.indicators),
                }
                for district in result.districts_after
            ],
            "district_scores": dict(result.after.district_scores),
        }],
        "selected_indicator": selected_indicator,
        "selected_district": selected_district,
        "diff_only": False,
    }


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
