"""Canonical UTC timestamp and identifier parsing shared across components."""

from __future__ import annotations

from datetime import datetime, timezone
import re

from .errors import ContractError

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z", re.ASCII)
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z", re.ASCII)


def identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ContractError(f"invalid {field}")
    return value


def instant(value: object, field: str) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise ContractError(f"invalid {field}")
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ContractError(f"invalid {field}") from exc
    canonical = (f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}T"
                 f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}Z")
    if canonical != value:
        raise ContractError(f"noncanonical {field}")
    return dt
