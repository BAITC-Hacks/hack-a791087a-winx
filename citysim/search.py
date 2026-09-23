"""Bounded, offline scenario proposals and engine-verified review results."""

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json

from citysim.engine import simulate, validate_scenario
from citysim.models import Dataset, Decision, SimulationResult
from citysim.review_models import (
    MAX_REVIEW_CANDIDATES, CandidateCheck, ReviewConstraints, ReviewResult,
    check_candidate_constraints, classify_outcome, validate_review_input,
)


def _decision_key(decision: Decision) -> tuple:
    """Natural M-ID order, with a stable fallback for invalid identifiers.

    Digit strings avoid parsing arbitrary/oversized unknown IDs as integers.
    None and an invalid empty district remain distinct in rejected proposals.
    """
    measure_id = decision.measure_id
    suffix = measure_id[1:]
    if measure_id.startswith("M") and suffix.isascii() and suffix.isdecimal():
        number = suffix.lstrip("0") or "0"
        prefix = (0, len(number), number, measure_id)
    else:
        prefix = (1, 0, "", measure_id)
    return (*prefix, decision.district_id is not None, decision.district_id or "")


def _canonical(decisions: Sequence[Decision]) -> tuple[Decision, ...]:
    if not isinstance(decisions, Sequence) or isinstance(decisions, (str, bytes)):
        raise ValueError("Кандидат должен быть последовательностью Decision.")
    for decision in decisions:
        if (not isinstance(decision, Decision)
                or not isinstance(decision.measure_id, str)
                or (decision.district_id is not None
                    and not isinstance(decision.district_id, str))):
            raise ValueError("Ожидается Decision со строковыми ID и районом str/None.")
    # Keep repeated rows: the official validator must see duplicate measures.
    return tuple(sorted(decisions, key=_decision_key))


def _scenario_key(decisions: Sequence[Decision]) -> tuple:
    return tuple(_decision_key(decision) for decision in decisions)


def generate_candidates(
    source: SimulationResult, dataset: Dataset, constraints: ReviewConstraints,
    *, limit: int = MAX_REVIEW_CANDIDATES,
) -> tuple[tuple[Decision, ...], ...]:
    """Propose up to limit valid one-pair replacements, without scoring them.

    Prefer additions helping critical indicators of A's weakest district, then
    total cost and canonical IDs. This heuristic does not promise optimality.
    """
    validate_review_input(source, dataset, constraints)
    if type(limit) is not int or not 0 <= limit <= MAX_REVIEW_CANDIDATES:
        raise ValueError("limit должен быть целым числом от 0 до 20.")
    if limit == 0 or constraints.max_changes == 0:
        return ()

    weakest_id = min(source.after.district_scores,
                     key=lambda key: (source.after.district_scores[key], key))
    weakest = next(d for d in source.districts_after if d.id == weakest_id)
    critical = {key for key, value in weakest.indicators.items() if value < 40}
    locked = set(constraints.locked)
    ranked: dict[tuple[Decision, ...], tuple] = {}
    for removed in source.decisions:
        if removed in locked:
            continue
        retained = tuple(d for d in source.decisions if d != removed)
        for measure in dataset.measures:
            targets = ((None,) if measure.scope == "city"
                       else tuple(d.id for d in dataset.districts))
            for district_id in targets:
                candidate = _canonical((*retained, Decision(measure.id, district_id)))
                if candidate == source.decisions or candidate in ranked:
                    continue
                if check_candidate_constraints(source, candidate, constraints):
                    continue
                validation = validate_scenario(candidate, dataset)
                if not validation.valid:
                    continue
                reaches_weakest = measure.scope == "city" or district_id == weakest_id
                benefit_count = sum(measure.effects.get(key, 0) > 0 for key in critical)
                priority = (benefit_count if reaches_weakest and measure.lag < dataset.horizon
                            else 0)
                ranked[candidate] = (-priority, validation.cost, _scenario_key(candidate))
    return tuple(sorted(ranked, key=ranked.__getitem__)[:limit])


def _context_digest(review: ReviewResult, dataset: Dataset) -> str:
    """Consistency checksum, not authentication of untrusted/AI review objects."""
    snapshot = asdict(review)
    snapshot.pop("context_digest")
    payload = json.dumps(
        {"dataset": asdict(dataset), "review": snapshot},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _previous_checks(
    previous: ReviewResult | None, source: SimulationResult,
    dataset: Dataset, constraints: ReviewConstraints,
) -> tuple[CandidateCheck, ...]:
    if previous is None:
        return ()
    if not isinstance(previous, ReviewResult):
        raise ValueError("previous должен быть результатом review_candidates.")
    if previous.source != source or previous.constraints != constraints:
        raise ValueError("previous относится к другому исходному A или ограничениям.")
    try:
        matches = (previous.context_digest is not None
                   and previous.context_digest == _context_digest(previous, dataset))
    except (TypeError, ValueError):
        matches = False
    if not matches:
        raise ValueError("previous изменён, устарел или относится к другому датасету.")
    return deepcopy(previous.checks)


def _select_best(source: SimulationResult, checks: Sequence[CandidateCheck]) -> SimulationResult:
    eligible = []
    for check in checks:
        if check.result is None:
            continue
        result = check.result
        outcome = classify_outcome(source, result)
        if outcome == "improved":
            rank = (0, -result.after.score, result.cost, _scenario_key(result.decisions))
        elif outcome == "cheaper_equal":
            rank = (1, result.cost, -result.after.score, _scenario_key(result.decisions))
        else:
            continue
        eligible.append((rank, result))
    return min(eligible, key=lambda item: item[0])[1] if eligible else source


def review_candidates(
    source: SimulationResult, candidates: Sequence[Sequence[Decision]],
    dataset: Dataset, constraints: ReviewConstraints, *,
    completed: bool = True, previous: ReviewResult | None = None,
) -> ReviewResult:
    """Validate at most 20 unique alternatives across calls, always against A.

    Overflow or malformed typed inputs raise ValueError before new candidates
    are evaluated. Official rule violations are retained in CandidateCheck.
    Pass previous unchanged from an earlier call; it is never recalculated.
    """
    validate_review_input(source, dataset, constraints)
    if type(completed) is not bool:
        raise ValueError("completed должен быть bool.")
    checks = list(_previous_checks(previous, source, dataset, constraints))
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise ValueError("Кандидаты должны быть последовательностью наборов Decision.")

    seen = {check.decisions for check in checks}
    pending = []
    for decisions in candidates:
        candidate = _canonical(decisions)
        if candidate == source.decisions or candidate in seen:
            continue
        seen.add(candidate)
        if len(seen) > MAX_REVIEW_CANDIDATES:
            raise ValueError("За всю ревизию допускается не более 20 уникальных кандидатов.")
        pending.append(candidate)

    for candidate in pending:
        errors = (*check_candidate_constraints(source, candidate, constraints),
                  *validate_scenario(candidate, dataset).errors)
        result = None if errors else simulate(candidate, dataset)
        checks.append(CandidateCheck(candidate, errors, result))

    best = _select_best(source, checks)
    review = ReviewResult(
        source=deepcopy(source), best=deepcopy(best), checks=deepcopy(tuple(checks)),
        status="completed_limited" if completed else "incomplete",
        outcome=classify_outcome(source, best), constraints=deepcopy(constraints),
    )
    return replace(review, context_digest=_context_digest(review, dataset))
