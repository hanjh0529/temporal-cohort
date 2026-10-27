"""Read source-of-truth SQLite rows, validating syntax before as-of filtering.

The cache table is required for schema compatibility, but its data is advisory.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3

from .errors import ContractError
from .timeutil import identifier, instant


@dataclass(frozen=True, slots=True)
class Coverage:
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class Revision:
    revision_id: str
    event_id: str
    person_id: str
    event_kind: str
    start: datetime | None
    end: datetime | None
    known: datetime
    operation: str
    parent: str | None


_REQUIRED: dict[str, set[str]] = {
    "persons": {"person_id", "coverage_start", "coverage_end"},
    "event_revisions": {
        "revision_id", "event_id", "person_id", "event_kind", "valid_start",
        "valid_end", "recorded_at", "operation", "supersedes_revision_id",
    },
    "cached_candidates": {
        "person_id", "snapshot_as_of", "cached_eligible", "cached_index_event_id",
    },
}


def load(db: Path, cutoff: datetime) -> tuple[dict[str, Coverage], dict[str, list[Revision]]]:
    """Return all persons and in-scope event groups; never query cache values."""
    if not db.is_file():
        raise ContractError("database does not exist")
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        for table, expected in _REQUIRED.items():
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if not expected.issubset(columns):
                raise ContractError(f"missing schema for {table}")

        roster: dict[str, Coverage] = {}
        for row in conn.execute("SELECT person_id, coverage_start, coverage_end FROM persons"):
            person = identifier(row["person_id"], "person_id")
            start = instant(row["coverage_start"], "coverage_start")
            end = instant(row["coverage_end"], "coverage_end")
            if person in roster or start >= end:
                raise ContractError("invalid or duplicate coverage")
            roster[person] = Coverage(start, end)

        groups: dict[str, list[Revision]] = defaultdict(list)
        seen_revision_ids: set[str] = set()
        query = ("SELECT revision_id, event_id, person_id, event_kind, "
                 "valid_start, valid_end, recorded_at, operation, "
                 "supersedes_revision_id FROM event_revisions")
        for row in conn.execute(query):
            rid = identifier(row["revision_id"], "revision_id")
            event = identifier(row["event_id"], "event_id")
            person = identifier(row["person_id"], "person_id")
            if rid in seen_revision_ids:
                raise ContractError("duplicate revision_id")
            seen_revision_ids.add(rid)
            kind = row["event_kind"]
            op = row["operation"]
            if kind not in ("INDEX", "SUPPORT", "BLOCK") or op not in ("CREATE", "CORRECT", "RETRACT"):
                raise ContractError("invalid event_kind or operation")
            predecessor = row["supersedes_revision_id"]
            if predecessor is not None:
                predecessor = identifier(predecessor, "supersedes_revision_id")
            known = instant(row["recorded_at"], "recorded_at")
            if op == "RETRACT":
                if row["valid_start"] is not None or row["valid_end"] is not None:
                    raise ContractError("RETRACT must have NULL interval")
                start = end = None
            else:
                start = instant(row["valid_start"], "valid_start")
                end = instant(row["valid_end"], "valid_end")
                if start >= end:
                    raise ContractError("invalid event interval")
            if known <= cutoff:
                if person not in roster:
                    raise ContractError("unknown in-scope person")
                groups[event].append(Revision(rid, event, person, kind, start, end, known, op, predecessor))
        return roster, groups
    except sqlite3.Error as exc:
        raise ContractError("malformed SQLite input") from exc
    finally:
        if conn is not None:
            conn.close()
