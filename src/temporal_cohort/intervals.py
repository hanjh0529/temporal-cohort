"""Half-open event-time window operations."""

from __future__ import annotations

from datetime import datetime, timedelta

from .errors import ContractError
from .storage import Coverage, Revision

DURATION = timedelta(days=30)


def horizon_end(anchor: datetime) -> datetime:
    try:
        return anchor + DURATION
    except OverflowError as exc:
        raise ContractError("horizon outside supported timestamps") from exc


def covered(coverage: Coverage, anchor: datetime, stop: datetime) -> bool:
    return coverage.start <= anchor and stop <= coverage.end


def support_within(event: Revision, anchor: datetime, stop: datetime) -> bool:
    return anchor <= event.start < stop


def block_overlaps(event: Revision, anchor: datetime, stop: datetime) -> bool:
    return anchor <= event.start < stop and anchor < event.end
