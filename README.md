# Temporal Cohort Reconciliation

This repository contains a Python 3.12 CLI for reconstructing synthetic cohort membership from a versioned SQLite event ledger. Only the Python standard library is needed. Run from `/app/temporal-cohort`.

## Run

```bash
python -m temporal_cohort \
  --db examples/demo.sqlite3 \
  --as-of 2026-02-10T00:00:00Z \
  --out-dir out
```

The CLI writes UTF-8 `out/cohort.json` and `out/evidence.json`. On a validation failure it writes a diagnostic to stderr, exits with code **2**, and does not write partial results. Input SQLite databases must not be modified. No network access is required.

## SQLite contract

Required tables and columns (additional tables and columns are permitted and ignored):

```sql
CREATE TABLE persons (
  person_id TEXT PRIMARY KEY,
  coverage_start TEXT NOT NULL,
  coverage_end TEXT NOT NULL
);
CREATE TABLE event_revisions (
  revision_id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  person_id TEXT NOT NULL,
  event_kind TEXT NOT NULL,
  valid_start TEXT,
  valid_end TEXT,
  recorded_at TEXT NOT NULL,
  operation TEXT NOT NULL,
  supersedes_revision_id TEXT
);
CREATE TABLE cached_candidates (
  person_id TEXT NOT NULL,
  snapshot_as_of TEXT NOT NULL,
  cached_eligible INTEGER NOT NULL,
  cached_index_event_id TEXT,
  PRIMARY KEY(person_id, snapshot_as_of)
);
```

Values of `event_kind`: `INDEX`, `SUPPORT`, `BLOCK`. Values of `operation`: `CREATE`, `CORRECT`, `RETRACT`. `cached_candidates` is a derived, potentially stale advisory table; it does not determine true eligibility and may include irrelevant persons or stale data. Every person in `persons`, including those with no event, must appear once in outputs.

IDs (`person_id`, `event_id`, `revision_id` and non-null predecessor IDs) match `[A-Za-z0-9][A-Za-z0-9_.-]*` in ASCII. Time values must be real canonical UTC instants of format `YYYY-MM-DDTHH:MM:SSZ`, without offsets or fractional seconds. The CLI `--as-of` value has the same format. UTC days are exactly 24 hours for this task. SQL row order must not influence output.

A coverage interval is `[coverage_start, coverage_end)`, with start strictly before end. For CREATE/CORRECT, event validity is `[valid_start, valid_end)` with strict start-before-end. For RETRACT, both `valid_start` and `valid_end` are SQL NULL. Do not interpret a `valid_*` date as a recording date. An event known at `--as-of` may describe a later valid-time interval (for example, a scheduled synthetic event); there is no implicit `valid_start <= --as-of` filter. Only the explicit cohort rules determine its effect.

## Revision resolution at the as-of cutoff

Use only revisions with `recorded_at <= --as-of` when reconstructing a historical event state. The equality boundary is **inclusive**. Validate timestamp syntax and identifiers for every input row, even rows recorded after the cutoff. Semantic chain validity and person references are checked for rows **inside** the cutoff; future relations do not affect an earlier snapshot.

For every `event_id` with any in-scope revisions:

- There is exactly one CREATE root with NULL `supersedes_revision_id`.
- Every other revision is CORRECT or RETRACT and must refer to its immediate previous revision of the **same** event, with strictly later `recorded_at` than its predecessor. The chain must be linear, connected and unbranched. Reject missing predecessors, duplicate roots, forks, cycles, invalid transitions and attempts to revise an already retracted event.
- All revisions in a chain have the same `event_id` and `person_id` (a correction may change `event_kind` and the event-time interval). The referenced `person_id` must exist in `persons` for an in-scope revision.
- For RETRACT, the required `event_kind` field is syntactically validated but does not influence event resolution; it need not equal the predecessor kind. An in-scope RETRACT at the head removes the event from the active set. Otherwise the head revision's kind and validity interval are the effective event payload.

The same `event_id` appearing across valid revisions is expected and is **not** a duplicate event. Multiple CREATE roots are invalid. Do not pick the newest recorded row without verifying the chain.

## Cohort rules

For each person, sort all active INDEX events by `(valid_start, event_id)`. Each INDEX is a candidate with anchor `a = valid_start` and horizon `H = [a, a+30 days)`.

1. `COVERED`: `coverage_start <= a AND a+30 days <= coverage_end`. If not covered, candidate status is `UNCOVERED`.
2. `support_ids`: active SUPPORT events with `a <= support.valid_start < a+30 days`, sorted by ID. Their end time is not used in this qualifying condition (the SUPPORT interval itself still must be valid).
3. `blocker_ids`: active BLOCK events whose valid intervals overlap H: `block.valid_start < a+30 days AND block.valid_end > a`, sorted by ID. Events merely touching either endpoint are not overlapping. A BLOCK starting **before** the anchor may overlap.
4. Candidate status priority: `UNCOVERED`, else `BLOCKED` if any blocker, else `NO_SUPPORT` if no supporting event, else `QUALIFIED`.

If **any** candidate is QUALIFIED, subject membership is `eligible=true`, `reason=INCLUDED`; select the first qualified candidate sorted by `(valid_start, event_id)`. Do not stop after a failing early anchor.

Otherwise, subject is excluded: `NO_INDEX` if no active INDEX; `NO_COVERED_INDEX` if INDEX events exist but none covered; else choose the status (`BLOCKED` or `NO_SUPPORT`) of the **first covered INDEX** in sorted order as the subject's reason. Include all candidates with their statuses in evidence, not merely the selected one. SUPPORT or BLOCK alone does not create an INDEX.

## Exact output structure

`cohort.json` has exactly:

```json
{
  "as_of": "2026-02-10T00:00:00Z",
  "subjects": [
    {
      "eligible": false,
      "person_id": "example_subject",
      "reason": "NO_INDEX",
      "selected_index_event_id": null
    }
  ]
}
```

Allowed reason values: `INCLUDED`, `NO_INDEX`, `NO_COVERED_INDEX`, `BLOCKED`, `NO_SUPPORT`. Non-null selected index iff eligible.

`evidence.json` has exactly:

```json
{
  "as_of": "2026-02-10T00:00:00Z",
  "subjects": [
    {
      "active_event_revisions": [],
      "candidate_indexes": [],
      "person_id": "example_subject"
    }
  ]
}
```

For each active event, the `active_event_revisions` entry has exactly `event_id`, `revision_id`, `event_kind`, sorted by `event_id`. It references the **effective as-of** revision head. Each `candidate_indexes` entry has exactly `event_id`, `status`, `support_ids` and `blocker_ids`; candidates are ordered by `(valid_start, event_id)`. For an UNCOVERED candidate, `support_ids` and `blocker_ids` are still computed from active events and included in the evidence; UNCOVERED controls status, not whether candidate-window evidence exists. Lists of IDs are lexicographically sorted. All arrays may be empty.

The two `subjects` arrays are sorted by `person_id` and have identical complete subject sets. Their membership decisions and candidate evidence must be mutually consistent. No host paths, cache contents, timestamps of execution, or random IDs appear in outputs.

## Errors and reproducibility

All invalid command inputs, malformed relevant revision graphs, missing tables/columns, invalid person coverage or event intervals, unknown in-scope person IDs, or malformed identifiers/timestamps are errors: exit **2**, stderr message, and no partial output on validation errors. Do not silently prune malformed events. Data after `--as-of` is syntactically validated but does not influence historical chain resolution.

For the same database contents, cutoff, and CLI configuration, output bytes must be identical across runs of the same implementation. Files are UTF-8 JSON with sorted object keys, indent of two spaces and one trailing newline, no non-finite numbers. SQLite input is immutable. A full recomputation is a legitimate solution; neither incremental caching nor a particular SQL implementation is mandated.

Performance tests may include a larger synthetic database; runtime/memory budgets are derived from a measured correct implementation in the pinned environment. No sublinear total-work performance guarantee is specified.
