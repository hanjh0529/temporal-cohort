-- Temporal Cohort Reconciliation, phase-0 fixture input schema v1.
-- All timestamp text is UTC ISO 8601, exact YYYY-MM-DDTHH:MM:SSZ.
CREATE TABLE persons (
    person_id TEXT PRIMARY KEY,
    coverage_start TEXT NOT NULL,
    coverage_end TEXT NOT NULL
);

CREATE TABLE event_revisions (
    revision_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    event_kind TEXT NOT NULL CHECK(event_kind IN ('INDEX', 'SUPPORT', 'BLOCK')),
    valid_start TEXT,
    valid_end TEXT,
    recorded_at TEXT NOT NULL,
    operation TEXT NOT NULL CHECK(operation IN ('CREATE', 'CORRECT', 'RETRACT')),
    supersedes_revision_id TEXT
);

-- Deliberately denormalized/advisory projection. It can be internally coherent,
-- perfectly formatted and factually stale. The authoritative inputs are above.
-- This table may be used for diagnostics but is never a source of cohort truth.
CREATE TABLE cached_candidates (
    person_id TEXT NOT NULL,
    snapshot_as_of TEXT NOT NULL,
    cached_eligible INTEGER NOT NULL CHECK(cached_eligible IN (0, 1)),
    cached_index_event_id TEXT,
    PRIMARY KEY (person_id, snapshot_as_of)
);

CREATE INDEX ix_event_revisions_event_asof
ON event_revisions(event_id, recorded_at, revision_id);
CREATE INDEX ix_event_revisions_person_asof
ON event_revisions(person_id, recorded_at);
