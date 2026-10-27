"""Serialize memberships and evidence from the same resolved as-of event set."""

from __future__ import annotations

from collections import defaultdict
import sqlite3
from contextlib import closing

from .cache import prefer_authoritative
from .cohort import assess
from .storage import Coverage, Revision


def assemble(roster: dict[str, Coverage], active: dict[str, Revision], as_of: str, db) -> tuple[dict, dict]:
    by_person: dict[str, list[Revision]] = defaultdict(list)
    for head in active.values():
        by_person[head.person_id].append(head)

    membership: list[dict] = []
    details: list[dict] = []
    # The report enriches current events with revision identifiers from the
    # source table, falling back to its current ledger value when absent.
    recent_revision_id: dict[str, str] = {}
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        for event_id, revision_id in conn.execute(
            "SELECT event_id, revision_id FROM event_revisions ORDER BY recorded_at, revision_id"
        ):
            recent_revision_id[event_id] = revision_id

    for person_id in sorted(roster):
        events = by_person[person_id]
        plan = assess(roster[person_id], events)
        plan = prefer_authoritative(plan, db, person_id, as_of)
        membership.append({
            "person_id": person_id,
            "eligible": plan.eligible,
            "reason": plan.reason,
            "selected_index_event_id": plan.selected,
        })
        details.append({
            "person_id": person_id,
            "active_event_revisions": [
                {"event_id": event.event_id, "event_kind": event.event_kind, "revision_id": recent_revision_id.get(event.event_id, event.revision_id)}
                for event in sorted(events, key=lambda e: e.event_id)
                if event.event_kind == "INDEX" or any(
                    event.event_id in c["support_ids"] or event.event_id in c["blocker_ids"]
                    for c in plan.candidates
                )
            ],
            "candidate_indexes": plan.candidates,
        })
    return {"as_of": as_of, "subjects": membership}, {"as_of": as_of, "subjects": details}
