#!/usr/bin/env python3
"""
Build compact JSON indexes for the GitHub Pages site.

Reads golden cases + policy and produces:
  docs/data/cases.json          — array of case summaries with aggregates
  docs/data/policy.json         — slimmed policy for display
  docs/data/sample_traces.json  — demo trace events
  docs/data/cases/case_NNN.csv  — per-case data files (copied from source)

No external dependencies.
"""

from __future__ import annotations

import csv
import json
import math
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
CASES_DIR = REPO / "40_ab_factory" / "vk-style" / "cases"
POLICY_PATH = REPO / "41_agents" / "ab_factory" / "policy.json"
OUT_DIR = REPO / "docs" / "data"
CSV_OUT_DIR = OUT_DIR / "cases"

CONFIDENCE_MAP = {
    "case_001": 0.65,
    "case_002": 0.23,
    "case_003": 0.20,
    "case_004": 0.27,
    "case_005": 0.04,
}


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _parse_csv(path: Path) -> list[dict]:
    """Parse a CSV file into a list of dicts. Stdlib only."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _safe_float(val: str | None) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _build_aggregates(csv_path: Path, truth: dict) -> dict:
    """Compute display-ready aggregates from a case's data.csv + truth.json."""
    rows = _parse_csv(csv_path)

    agg: dict = {
        "n_control": None,
        "n_test": None,
        "control_mean": None,
        "test_mean": None,
        "uplift_pct": truth.get("primary_effect_relative"),
        "p_value": None,
        "primary_metric": "revenue",
        "guardrails": {},
        "segments": {},
        "long_term_reversal": "long_term_reversal" in truth.get("key_reasons", []),
    }
    if agg["uplift_pct"] is not None:
        agg["uplift_pct"] = round(agg["uplift_pct"] * 100, 2)

    control_all = None
    test_all = None
    segment_rows: dict[str, dict] = {}

    for row in rows:
        seg = row.get("segment", "all")
        variant = row.get("variant", "")
        n = _safe_float(row.get("n_users"))
        rev = _safe_float(row.get("revenue"))

        if seg == "all" and variant == "control":
            control_all = row
            if n and rev:
                agg["n_control"] = int(n)
                agg["control_mean"] = round(rev / n, 4)

        elif seg == "all" and variant == "test":
            test_all = row
            if n and rev:
                agg["n_test"] = int(n)
                agg["test_mean"] = round(rev / n, 4)
            p = _safe_float(row.get("revenue_p_value"))
            if p is not None:
                agg["p_value"] = p

            ctr_eff = _safe_float(row.get("ctr_effect_relative"))
            ctr_p = _safe_float(row.get("ctr_p_value"))
            if ctr_eff is not None:
                agg["guardrails"]["ctr"] = {
                    "change_pct": round(ctr_eff * 100, 2),
                    "p_value": ctr_p,
                }

        elif seg != "all" and variant == "test":
            seg_eff = _safe_float(row.get("revenue_effect_relative"))
            seg_p = _safe_float(row.get("revenue_p_value"))
            segment_rows[seg] = {
                "uplift_pct": round(seg_eff * 100, 2) if seg_eff is not None else None,
                "p_value": seg_p,
            }

    if segment_rows:
        agg["segments"] = segment_rows

    return agg


def _copy_csv(case_dir: Path, case_id: str) -> str | None:
    """Copy data.csv to docs/data/cases/<case_id>.csv. Returns relative URL."""
    src = case_dir / "data.csv"
    if not src.exists():
        return None
    CSV_OUT_DIR.mkdir(parents=True, exist_ok=True)
    dst = CSV_OUT_DIR / f"{case_id}.csv"
    shutil.copy2(src, dst)
    return f"data/cases/{case_id}.csv"


def build_cases() -> list[dict]:
    cases: list[dict] = []
    if not CASES_DIR.exists():
        print(f"WARN: {CASES_DIR} not found", file=sys.stderr)
        return cases

    for case_dir in sorted(CASES_DIR.iterdir()):
        contract_path = case_dir / "contract.json"
        truth_path = case_dir / "truth.json"
        if not contract_path.exists() or not truth_path.exists():
            continue

        with open(contract_path, "r", encoding="utf-8") as f:
            contract = json.load(f)
        with open(truth_path, "r", encoding="utf-8") as f:
            truth = json.load(f)

        cid = contract["case_id"]
        effect = truth.get("primary_effect_relative")
        effect_pct = round(effect * 100, 2) if effect is not None else None

        csv_url = _copy_csv(case_dir, cid)

        aggregates = {}
        csv_src = case_dir / "data.csv"
        if csv_src.exists():
            aggregates = _build_aggregates(csv_src, truth)

        cases.append({
            "case_id": cid,
            "title": contract.get("title", ""),
            "primary_metric": contract.get("primary_metric", {}).get("name", ""),
            "effect_pct": effect_pct,
            "is_stat_sig": truth.get("is_stat_sig", False),
            "guardrails_ok": truth.get("guardrails_ok", True),
            "decision": truth.get("expected_decision", ""),
            "reasons": truth.get("key_reasons", []),
            "confidence": CONFIDENCE_MAP.get(cid, 0.5),
            "summary": truth.get("human_rationale", ""),
            "domain": contract.get("domain", ""),
            "horizon_days": contract.get("time", {}).get("horizon_days"),
            "variants": contract.get("variants", []),
            "segments": contract.get("segments", []),
            "notes": contract.get("notes", ""),
            "guardrails": contract.get("guardrails", []),
            "practical_threshold_pct": round(
                contract.get("decision_framework", {}).get(
                    "practical_threshold_relative", 0.005) * 100, 2),
            "csv_url": csv_url,
            "aggregates": aggregates,
        })

    return cases


def build_policy() -> dict:
    if not POLICY_PATH.exists():
        return {}
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        full = json.load(f)
    return {
        "policy_id": full.get("policy_id", ""),
        "policy_version": full.get("policy_version", ""),
        "primary_metric": full.get("primary_metric", {}),
        "significance": full.get("significance", {}),
        "guardrails": full.get("guardrails", []),
        "segments": full.get("segments", {}),
        "long_term": full.get("long_term", {}),
        "confidence_model": {
            "type": full.get("confidence_model", {}).get("type", ""),
            "weights": full.get("confidence_model", {}).get("weights", {}),
        },
    }


def build_sample_traces() -> list[dict]:
    """Build a small synthetic trace set for the 5 golden cases."""
    traces: list[dict] = []
    cases_meta = [
        ("case_001", "ship", 0.65, ["primary_uplift"]),
        ("case_002", "do_not_ship", 0.23, ["primary_uplift", "guardrail_violation:ctr"]),
        ("case_003", "do_not_ship", 0.20, ["practically_small"]),
        ("case_004", "investigate", 0.27, ["segment_conflict", "not_significant"]),
        ("case_005", "do_not_ship", 0.04, ["long_term_reversal", "not_significant"]),
    ]
    agents_steps = [
        ("reader", "case_loaded", "Loading case files", 0),
        ("reader", "artifact_written", "reader_summary.md", 1),
        ("stats", "parsed", "Running sanity checks", 2),
        ("stats", "checks_done", "PASS", 4),
        ("decision", "policy_loaded", "Policy ab_factory_policy v1.0.0", 5),
        ("decision", "decision_made", None, 7),
        ("viz", "parsed", "Building comparison tables", 8),
        ("viz", "artifact_written", "viz.md", 10),
    ]

    for case_id, decision, conf, reasons in cases_meta:
        run_id = f"demo_{case_id}"
        for agent, event, msg, offset_ms in agents_steps:
            actual_msg = msg
            if event == "decision_made":
                actual_msg = f"{decision} (confidence={conf:.2f}, {', '.join(reasons)})"
            traces.append({
                "run_id": run_id,
                "case_id": case_id,
                "agent": agent,
                "event": event,
                "message": actual_msg,
                "offset_ms": offset_ms,
                "decision": decision if event == "decision_made" else None,
                "confidence": conf if event == "decision_made" else None,
            })
    return traces


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CSV_OUT_DIR.mkdir(parents=True, exist_ok=True)

    cases = build_cases()
    with open(OUT_DIR / "cases.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"  docs/data/cases.json          {len(cases)} cases")

    policy = build_policy()
    with open(OUT_DIR / "policy.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(policy, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"  docs/data/policy.json         policy v{policy.get('policy_version', '?')}")

    traces = build_sample_traces()
    with open(OUT_DIR / "sample_traces.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(traces, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"  docs/data/sample_traces.json  {len(traces)} events")

    csv_count = len(list(CSV_OUT_DIR.glob("*.csv")))
    print(f"  docs/data/cases/*.csv         {csv_count} files")

    print(f"\nDone. Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
