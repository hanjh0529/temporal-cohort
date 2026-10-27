"""Small public smoke tests; not the private TB4 grader."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "examples" / "demo.sqlite3"


class PublicSmoke(unittest.TestCase):
    def run_cli(self, cutoff: str):
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run([
                sys.executable, "-m", "temporal_cohort", "--db", str(DB),
                "--as-of", cutoff, "--out-dir", folder,
            ], env=env, text=True, capture_output=True, check=False)
            if result.returncode != 0:
                return result, None, None
            cohort = json.loads((Path(folder) / "cohort.json").read_text())
            evidence = json.loads((Path(folder) / "evidence.json").read_text())
            return result, cohort, evidence

    def test_cli_schema_and_all_subjects(self):
        proc, cohort, evidence = self.run_cli("2026-02-10T00:00:00Z")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(cohort["as_of"], evidence["as_of"])
        self.assertEqual([x["person_id"] for x in cohort["subjects"]],
                         [x["person_id"] for x in evidence["subjects"]])
        self.assertEqual(len(cohort["subjects"]), 10)

    def test_invalid_timestamp(self):
        proc, _, _ = self.run_cli("2026-02-10T00:00:00+00:00")
        self.assertEqual(proc.returncode, 2)

    def test_historical_cutoffs_change_results(self):
        earlier, a, _ = self.run_cli("2026-01-15T00:00:00Z")
        later, b, _ = self.run_cli("2026-02-10T00:00:00Z")
        self.assertEqual(earlier.returncode, later.returncode)
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
