"""Stats agent — sanity checks on data.csv."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from trace import emit

AGENT = "stats"

REQUIRED_COLS = [
    "case_id", "segment", "variant", "n_users", "revenue", "cpm",
    "fillrate", "ctr", "shows",
]


def _load_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_csv(p: Path) -> tuple[list[str], list[dict]]:
    with open(p, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _safe_float(v: str) -> float | None:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def run(case_dir: Path, out_dir: Path, trace_path: Path, run_id: str) -> dict:
    contract = _load_json(case_dir / "contract.json")
    case_id = contract["case_id"]

    emit(trace_path, run_id=run_id, case_id=case_id, agent=AGENT,
         step="start", event="parsed", message="Running sanity checks")

    headers, rows = _load_csv(case_dir / "data.csv")
    checks: list[dict] = []

    # 1. Required columns
    missing_cols = [c for c in REQUIRED_COLS if c not in headers]
    checks.append({
        "check": "required_columns",
        "pass": len(missing_cols) == 0,
        "detail": f"missing: {missing_cols}" if missing_cols else "all present",
    })

    # 2. No empty rows
    empty_rows = [i for i, r in enumerate(rows) if not any(v.strip() for v in r.values())]
    checks.append({
        "check": "no_empty_rows",
        "pass": len(empty_rows) == 0,
        "detail": f"empty rows at indices: {empty_rows}" if empty_rows else "ok",
    })

    # 3. Variants present for each segment
    expected_variants = set(contract.get("variants", []))
    segments_in_data = {r["segment"] for r in rows}
    variant_issues: list[str] = []
    for seg in segments_in_data:
        seg_variants = {r["variant"] for r in rows if r["segment"] == seg}
        missing = expected_variants - seg_variants
        if missing:
            variant_issues.append(f"segment '{seg}' missing variants: {missing}")
    checks.append({
        "check": "variants_per_segment",
        "pass": len(variant_issues) == 0,
        "detail": "; ".join(variant_issues) if variant_issues else "ok",
    })

    # 4. p-value in [0,1]
    pval_issues: list[str] = []
    for col in headers:
        if "_p_value" in col:
            for i, r in enumerate(rows):
                v = _safe_float(r.get(col, ""))
                if v is not None and (v < 0 or v > 1):
                    pval_issues.append(f"row {i} {col}={v}")
    checks.append({
        "check": "p_values_in_range",
        "pass": len(pval_issues) == 0,
        "detail": "; ".join(pval_issues) if pval_issues else "ok",
    })

    # 5. Effect values reasonable (abs <= 0.50)
    effect_issues: list[str] = []
    for col in headers:
        if "_effect_relative" in col:
            for i, r in enumerate(rows):
                v = _safe_float(r.get(col, ""))
                if v is not None and abs(v) > 0.50:
                    effect_issues.append(f"row {i} {col}={v}")
    checks.append({
        "check": "effects_reasonable",
        "pass": len(effect_issues) == 0,
        "detail": "; ".join(effect_issues) if effect_issues else "ok",
    })

    all_pass = all(c["pass"] for c in checks)

    L: list[str] = []
    L.append(f"# Stats Checks — {case_id}")
    L.append("")
    L.append(f"Result: **{'ALL PASS' if all_pass else 'ISSUES FOUND'}**")
    L.append("")
    L.append("| Check | Pass | Detail |")
    L.append("|---|---|---|")
    for c in checks:
        icon = "yes" if c["pass"] else "NO"
        L.append(f"| {c['check']} | {icon} | {c['detail']} |")
    L.append("")

    out_path = out_dir / "stats_checks.md"
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")

    emit(trace_path, run_id=run_id, case_id=case_id, agent=AGENT,
         step="done", event="checks_done", message=f"{'PASS' if all_pass else 'FAIL'}",
         payload={"checks": len(checks), "all_pass": all_pass})

    return {"checks": checks, "all_pass": all_pass}
