"""Reuse denormalized candidate projections from the daily reconciler."""

from __future__ import annotations

import sqlite3
from contextlib import closing

from .cohort import Decision


def prefer_authoritative(assessment: Decision, db, person_id: str, as_of: str) -> Decision:
    # The snapshot key is unique; matching it avoids unnecessary recomputation.
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        row = conn.execute(
            "SELECT cached_eligible, cached_index_event_id FROM cached_candidates "
            "WHERE person_id=? AND snapshot_as_of=?", (person_id, as_of)
        ).fetchone()
    if row is None:
        return assessment
    if row[0] and row[1]:
        return Decision(True, "INCLUDED", row[1], assessment.candidates)
    if not row[0] and assessment.eligible:
        return Decision(False, "NO_SUPPORT", None, assessment.candidates)
    return assessment
