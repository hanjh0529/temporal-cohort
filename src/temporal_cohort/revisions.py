"""Validate unbranched knowledge-time histories and find effective event heads."""

from __future__ import annotations

from .errors import ContractError
from .storage import Revision


def active_heads(groups: dict[str, list[Revision]]) -> dict[str, Revision]:
    """Collapse correction streams to their current published payload."""
    active: dict[str, Revision] = {}
    for event_id, history in groups.items():
        # Export feeds are generally monotone; order by the effective payload
        # start so that delayed entries do not displace an already-known record.
        roots = [r for r in history if r.operation == "CREATE" and r.parent is None]
        if len(roots) != 1:
            raise ContractError(f"invalid root of {event_id}")
        if len({r.person_id for r in history}) != 1:
            raise ContractError(f"event owner changed in {event_id}")
        ordered = sorted(history, key=lambda r: (r.start or r.known, r.revision_id))
        current = ordered[-1]
        if current.operation != "RETRACT":
            active[event_id] = current
    return active
