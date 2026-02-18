#!/usr/bin/env python3
"""
Validate all A/B test cases against contract and truth schemas.

Checks:
  1. Required files exist (contract.json, truth.json, data.csv, case.md)
  2. contract.json has required fields and valid types
  3. truth.json has required fields and valid types
  4. data.csv has required columns and rows for all variants/segments

No external dependencies — pure Python 3.10+.
"""

from __future__ import annotations

import csv
import json
import sys
from io import StringIO
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CASES_DIR = SCRIPT_DIR.parent / "cases"
SCHEMA_DIR = SCRIPT_DIR.parent / "schema"

REQUIRED_FILES = ["contract.json", "truth.json", "data.csv", "case.md"]

CONTRACT_REQUIRED = [
    "case_id", "title", "domain", "unit", "variants",
    "time", "primary_metric", "guardrails", "stats", "decision_framework",
]
TRUTH_REQUIRED = [
    "case_id", "expected_decision", "primary_effect_relative",
    "is_stat_sig", "guardrails_ok", "key_reasons", "human_rationale",
]
DATA_REQUIRED_COLS = [
    "case_id", "segment", "variant", "n_users", "revenue", "cpm",
    "fillrate", "ctr", "shows",
]
VALID_DECISIONS = {"ship", "do_not_ship", "iterate", "investigate"}
VALID_METRICS = {"revenue", "cpm", "fillrate", "ctr", "shows"}
VALID_DIRECTIONS = {"up", "down"}
VALID_REASONS = {
    "primary_uplift", "guardrail_violation", "segment_conflict",
    "long_term_reversal", "practically_small", "not_significant",
    "overall_positive",
}


class ValidationError:
    def __init__(self, case: str, file: str, message: str):
        self.case = case
        self.file = file
        self.message = message

    def __str__(self) -> str:
        return f"  [{self.case}] {self.file}: {self.message}"


def validate_contract(case_dir: Path, case_name: str) -> list[ValidationError]:
    errors: list[ValidationError] = []
    path = case_dir / "contract.json"

    try:
        with open(path, "r", encoding="utf-8") as f:
            c = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(ValidationError(case_name, "contract.json", f"Invalid JSON: {e}"))
        return errors

    for field in CONTRACT_REQUIRED:
        if field not in c:
            errors.append(ValidationError(case_name, "contract.json", f"Missing required field: {field}"))

    if "case_id" in c and not isinstance(c["case_id"], str):
        errors.append(ValidationError(case_name, "contract.json", "case_id must be string"))

    if "variants" in c:
        if not isinstance(c["variants"], list) or len(c["variants"]) < 2:
            errors.append(ValidationError(case_name, "contract.json", "variants must be list with ≥2 items"))

    if "primary_metric" in c:
        pm = c["primary_metric"]
        if pm.get("name") not in VALID_METRICS:
            errors.append(ValidationError(case_name, "contract.json", f"primary_metric.name must be one of {VALID_METRICS}"))
        if pm.get("direction") not in VALID_DIRECTIONS:
            errors.append(ValidationError(case_name, "contract.json", f"primary_metric.direction must be 'up' or 'down'"))
        if not isinstance(pm.get("mde_relative"), (int, float)):
            errors.append(ValidationError(case_name, "contract.json", "primary_metric.mde_relative must be numeric"))

    if "time" in c:
        t = c["time"]
        for tf in ["start_date", "end_date", "horizon_days"]:
            if tf not in t:
                errors.append(ValidationError(case_name, "contract.json", f"time.{tf} missing"))

    if "stats" in c:
        s = c["stats"]
        if not isinstance(s.get("alpha"), (int, float)):
            errors.append(ValidationError(case_name, "contract.json", "stats.alpha must be numeric"))

    if "decision_framework" in c:
        df = c["decision_framework"]
        if "rule" not in df:
            errors.append(ValidationError(case_name, "contract.json", "decision_framework.rule missing"))
        if not isinstance(df.get("practical_threshold_relative"), (int, float)):
            errors.append(ValidationError(case_name, "contract.json", "decision_framework.practical_threshold_relative must be numeric"))

    return errors


def validate_truth(case_dir: Path, case_name: str) -> list[ValidationError]:
    errors: list[ValidationError] = []
    path = case_dir / "truth.json"

    try:
        with open(path, "r", encoding="utf-8") as f:
            t = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(ValidationError(case_name, "truth.json", f"Invalid JSON: {e}"))
        return errors

    for field in TRUTH_REQUIRED:
        if field not in t:
            errors.append(ValidationError(case_name, "truth.json", f"Missing required field: {field}"))

    if t.get("expected_decision") not in VALID_DECISIONS:
        errors.append(ValidationError(case_name, "truth.json", f"expected_decision must be one of {VALID_DECISIONS}"))

    if not isinstance(t.get("is_stat_sig"), bool):
        errors.append(ValidationError(case_name, "truth.json", "is_stat_sig must be boolean"))

    if not isinstance(t.get("guardrails_ok"), bool):
        errors.append(ValidationError(case_name, "truth.json", "guardrails_ok must be boolean"))

    if isinstance(t.get("key_reasons"), list):
        for r in t["key_reasons"]:
            if r not in VALID_REASONS:
                errors.append(ValidationError(case_name, "truth.json", f"Unknown key_reason: '{r}'"))
    else:
        errors.append(ValidationError(case_name, "truth.json", "key_reasons must be array"))

    return errors


def validate_data(case_dir: Path, case_name: str) -> list[ValidationError]:
    errors: list[ValidationError] = []
    data_path = case_dir / "data.csv"
    contract_path = case_dir / "contract.json"

    try:
        with open(data_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            headers = reader.fieldnames or []
    except Exception as e:
        errors.append(ValidationError(case_name, "data.csv", f"Cannot read CSV: {e}"))
        return errors

    for col in DATA_REQUIRED_COLS:
        if col not in headers:
            errors.append(ValidationError(case_name, "data.csv", f"Missing required column: {col}"))

    if not rows:
        errors.append(ValidationError(case_name, "data.csv", "No data rows"))
        return errors

    try:
        with open(contract_path, "r", encoding="utf-8") as f:
            contract = json.load(f)
    except Exception:
        return errors

    expected_variants = set(contract.get("variants", []))
    actual_variants = {r.get("variant") for r in rows}
    missing_variants = expected_variants - actual_variants
    if missing_variants:
        errors.append(ValidationError(case_name, "data.csv", f"Missing variants in data: {missing_variants}"))

    segments = contract.get("segments")
    if segments:
        expected_segs = set(segments) | {"all"}
        actual_segs = {r.get("segment") for r in rows}
        missing_segs = expected_segs - actual_segs
        if missing_segs:
            errors.append(ValidationError(case_name, "data.csv", f"Missing segments in data: {missing_segs}"))

    case_id = contract.get("case_id", "")
    for i, row in enumerate(rows):
        if row.get("case_id") != case_id:
            errors.append(ValidationError(case_name, "data.csv", f"Row {i+1}: case_id mismatch (expected '{case_id}')"))
            break

    return errors


def validate_case(case_dir: Path) -> list[ValidationError]:
    case_name = case_dir.name
    errors: list[ValidationError] = []

    for fname in REQUIRED_FILES:
        if not (case_dir / fname).exists():
            errors.append(ValidationError(case_name, fname, "File missing"))

    if (case_dir / "contract.json").exists():
        errors.extend(validate_contract(case_dir, case_name))
    if (case_dir / "truth.json").exists():
        errors.extend(validate_truth(case_dir, case_name))
    if (case_dir / "data.csv").exists() and (case_dir / "contract.json").exists():
        errors.extend(validate_data(case_dir, case_name))

    # Cross-check: case_id in contract == case_id in truth
    try:
        with open(case_dir / "contract.json", "r", encoding="utf-8") as f:
            cid_contract = json.load(f).get("case_id")
        with open(case_dir / "truth.json", "r", encoding="utf-8") as f:
            cid_truth = json.load(f).get("case_id")
        if cid_contract and cid_truth and cid_contract != cid_truth:
            errors.append(ValidationError(case_name, "cross-check", f"case_id mismatch: contract={cid_contract}, truth={cid_truth}"))
    except Exception:
        pass

    return errors


def main() -> None:
    if not CASES_DIR.exists():
        print(f"ERROR: cases directory not found: {CASES_DIR}")
        sys.exit(1)

    case_dirs = sorted(d for d in CASES_DIR.iterdir() if d.is_dir() and d.name.startswith("case_"))
    if not case_dirs:
        print("WARNING: no case directories found.")
        sys.exit(0)

    total_errors = 0
    total_cases = 0

    print(f"Validating {len(case_dirs)} cases...")
    print()

    for case_dir in case_dirs:
        total_cases += 1
        errors = validate_case(case_dir)

        if errors:
            print(f"  FAIL  {case_dir.name} ({len(errors)} error{'s' if len(errors) != 1 else ''})")
            for e in errors:
                print(f"        {e}")
            total_errors += len(errors)
        else:
            print(f"  OK    {case_dir.name}")

    print()
    if total_errors == 0:
        print(f"All {total_cases} cases passed validation.")
    else:
        print(f"{total_errors} error(s) in {total_cases} cases.")
        sys.exit(1)


if __name__ == "__main__":
    main()
