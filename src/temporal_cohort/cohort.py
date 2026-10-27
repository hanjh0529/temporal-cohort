"""Derive cohort decisions and candidate-specific audit facts from active events."""

from __future__ import annotations

from dataclasses import dataclass

from .intervals import block_overlaps, covered, horizon_end, support_within
from .storage import Coverage, Revision


@dataclass(slots=True)
class Decision:
    eligible: bool
    reason: str
    selected: str | None
    candidates: list[dict]


def assess(coverage: Coverage, events: list[Revision]) -> Decision:
    indexes = sorted((e for e in events if e.event_kind == "INDEX"), key=lambda e: (e.start, e.event_id))
    supports = [e for e in events if e.event_kind == "SUPPORT"]
    blocks = [e for e in events if e.event_kind == "BLOCK"]
    candidates: list[dict] = []
    first_qualified: str | None = None
    first_candidate: str | None = indexes[0].event_id if indexes else None
    first_covered_reason: str | None = None

    for index in indexes:
        anchor = index.start
        stop = horizon_end(anchor)
        support_ids = sorted(e.event_id for e in supports if support_within(e, anchor, stop))
        blocker_ids = sorted(e.event_id for e in blocks if block_overlaps(e, anchor, stop))
        is_covered = covered(coverage, anchor, stop)
        if not is_covered:
            status = "UNCOVERED"
        elif blocker_ids:
            status = "BLOCKED"
        elif not support_ids:
            status = "NO_SUPPORT"
        else:
            status = "QUALIFIED"
        candidates.append({
            "event_id": index.event_id, "status": status,
            "support_ids": support_ids, "blocker_ids": blocker_ids,
        })
        if is_covered and first_covered_reason is None:
            first_covered_reason = status
        if status == "QUALIFIED" and first_qualified is None and index.event_id == first_candidate:
            first_qualified = index.event_id

    if first_qualified is not None:
        return Decision(True, "INCLUDED", first_qualified, candidates)
    if not indexes:
        reason = "NO_INDEX"
    elif first_covered_reason is None:
        reason = "NO_COVERED_INDEX"
    else:
        reason = first_covered_reason
    return Decision(False, reason, None, candidates)
