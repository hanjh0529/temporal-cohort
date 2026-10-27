"""User-facing command-line entrypoint and stable JSON encoding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from .errors import ContractError
from .evidence import assemble
from .revisions import active_heads
from .storage import load
from .timeutil import instant


def compute(db: Path, as_of: str) -> tuple[dict, dict]:
    cutoff = instant(as_of, "as-of")
    roster, histories = load(db, cutoff)
    heads = active_heads(histories)
    return assemble(roster, heads, as_of, db)


def encode(data: dict) -> bytes:
    return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile synthetic cohort at an as-of cutoff")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        cohort, evidence = compute(args.db, args.as_of)
        cohort_bytes, evidence_bytes = encode(cohort), encode(evidence)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "cohort.json").write_bytes(cohort_bytes)
        (args.out_dir / "evidence.json").write_bytes(evidence_bytes)
    except (ContractError, sqlite3.Error, OSError) as exc:
        print(f"temporal-cohort: {exc}", file=sys.stderr)
        return 2
    return 0
