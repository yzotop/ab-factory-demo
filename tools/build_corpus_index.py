#!/usr/bin/env python3
"""
Build the public corpus JSON index from 100 generated cases + workflow decisions.

Reads:
  40_ab_factory/vk-style/cases_auto/case_NNN/  (contract.json, truth.json, data.csv)
  42_workflows/ab_factory/runs/*/artifacts/decision.json

Produces:
  docs/data/corpus_100.json   — compact per-case array
  docs/data/corpus_stats.json — aggregate statistics

No external dependencies.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
CASES_AUTO = REPO / "40_ab_factory" / "vk-style" / "cases_auto"
RUNS_DIR = REPO / "42_workflows" / "ab_factory" / "runs"
OUT_DIR = REPO / "docs" / "data"

EXPECTED_COUNT = 100


def _safe_float(val: str | None) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _infer_type(reasons: list[str]) -> str:
    """Infer scenario type from truth reasons."""
    rs = set(reasons)
    if "long_term_reversal" in rs:
        return "long_term_reversal"
    if "segment_conflict" in rs:
        return "segment_conflict"
    if any(r.startswith("guardrail_violation") for r in rs):
        return "guardrail_breach"
    if "practically_small" in rs:
        return "practically_small"
    if "primary_uplift" in rs:
        return "clean_uplift"
    return "other"


def _load_decisions() -> dict[str, dict]:
    """Scan runs/ for the latest decision.json per case_id."""
    decisions: dict[str, tuple[str, dict]] = {}
    if not RUNS_DIR.exists():
        return {}
    for run_dir in sorted(RUNS_DIR.iterdir()):
        dj = run_dir / "artifacts" / "decision.json"
        if not dj.exists():
            continue
        try:
            with open(dj, "r", encoding="utf-8") as f:
                d = json.load(f)
            cid = d.get("case_id", "")
            if cid and (cid not in decisions or run_dir.name > decisions[cid][0]):
                decisions[cid] = (run_dir.name, d)
        except (json.JSONDecodeError, KeyError):
            continue
    return {cid: data for cid, (_, data) in decisions.items()}


def _parse_csv(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _aggregates_from_csv(csv_path: Path) -> dict:
    rows = _parse_csv(csv_path)
    agg: dict = {}
    for row in rows:
        if row.get("segment") == "all" and row.get("variant") == "control":
            n = _safe_float(row.get("n_users"))
            rev = _safe_float(row.get("revenue"))
            if n and rev:
                agg["control_mean"] = round(rev / n, 6)
        elif row.get("segment") == "all" and row.get("variant") == "test":
            n = _safe_float(row.get("n_users"))
            rev = _safe_float(row.get("revenue"))
            if n and rev:
                agg["test_mean"] = round(rev / n, 6)
            agg["p_value"] = _safe_float(row.get("revenue_p_value"))
            ctr_eff = _safe_float(row.get("ctr_effect_relative"))
            if ctr_eff is not None:
                agg["guardrail_ctr_delta"] = round(ctr_eff * 100, 2)
    return agg


def build_corpus() -> list[dict]:
    if not CASES_AUTO.exists():
        print(
            f"ERROR: {CASES_AUTO} not found.\n"
            "Run: ./43_generation/ab_factory/run.sh --n 100\n"
            "Then: cd 42_workflows/ab_factory && python3 run_case.py --all "
            "--root ../../40_ab_factory/vk-style/cases_auto",
            file=sys.stderr,
        )
        sys.exit(1)

    case_dirs = sorted(
        d for d in CASES_AUTO.iterdir()
        if d.is_dir() and (d / "contract.json").exists()
    )
    if len(case_dirs) < EXPECTED_COUNT:
        print(
            f"WARN: found {len(case_dirs)} cases, expected {EXPECTED_COUNT}.",
            file=sys.stderr,
        )

    decisions = _load_decisions()
    cases: list[dict] = []

    for case_dir in case_dirs:
        with open(case_dir / "contract.json", "r", encoding="utf-8") as f:
            contract = json.load(f)
        with open(case_dir / "truth.json", "r", encoding="utf-8") as f:
            truth = json.load(f)

        cid = contract["case_id"]
        dj = decisions.get(cid, {})
        signals = dj.get("signals", {})

        csv_path = case_dir / "data.csv"
        csv_agg = _aggregates_from_csv(csv_path) if csv_path.exists() else {}

        effect = truth.get("primary_effect_relative")
        uplift_pct = round(effect * 100, 2) if effect is not None else None

        p_value = signals.get("p_value") or csv_agg.get("p_value")

        ctr_delta = signals.get("guardrails", {}).get("ctr")
        if ctr_delta is None:
            ctr_delta = csv_agg.get("guardrail_ctr_delta")

        seg_conflict = signals.get("segment_conflict", False)
        reversal = signals.get("long_term_reversal", False)
        if not seg_conflict:
            seg_conflict = "segment_conflict" in truth.get("key_reasons", [])
        if not reversal:
            reversal = "long_term_reversal" in truth.get("key_reasons", [])

        reasons = dj.get("reasons", truth.get("key_reasons", []))
        decision = dj.get("decision", truth.get("expected_decision", ""))
        confidence = dj.get("confidence")

        time_info = contract.get("time", {})
        duration_days = time_info.get("horizon_days")

        cases.append({
            "case_id": cid,
            "title": contract.get("title", ""),
            "type": _infer_type(truth.get("key_reasons", [])),
            "metric": contract.get("primary_metric", {}).get("name", ""),
            "uplift_pct": uplift_pct,
            "p_value": p_value,
            "decision": decision,
            "confidence": round(confidence, 4) if confidence is not None else None,
            "reasons": reasons,
            "guardrail_ctr_delta": ctr_delta,
            "segment_conflict": seg_conflict,
            "long_term_reversal": reversal,
            "control_mean": csv_agg.get("control_mean"),
            "test_mean": csv_agg.get("test_mean"),
            "segments_present": bool(contract.get("segments")),
            "duration_days": duration_days,
            "policy_version": dj.get("policy", {}).get("policy_version", ""),
        })

    return cases


def build_stats(cases: list[dict]) -> dict:
    total = len(cases)
    decision_counts = Counter(c["decision"] for c in cases)
    reason_counts: Counter = Counter()
    metric_counts = Counter(c["metric"] for c in cases)

    conf_sums: dict[str, list[float]] = {}
    uplifts: list[float] = []

    for c in cases:
        for r in c["reasons"]:
            reason_counts[r] += 1
        d = c["decision"]
        if c["confidence"] is not None:
            conf_sums.setdefault(d, []).append(c["confidence"])
        if c["uplift_pct"] is not None:
            uplifts.append(c["uplift_pct"])

    avg_conf: dict[str, float] = {}
    for d, vals in conf_sums.items():
        avg_conf[d] = round(sum(vals) / len(vals), 4) if vals else 0

    return {
        "total": total,
        "decision_counts": dict(decision_counts.most_common()),
        "reason_counts": dict(reason_counts.most_common(20)),
        "metric_counts": dict(metric_counts.most_common()),
        "avg_confidence_by_decision": avg_conf,
        "uplift_min": round(min(uplifts), 2) if uplifts else None,
        "uplift_max": round(max(uplifts), 2) if uplifts else None,
        "uplift_avg": round(sum(uplifts) / len(uplifts), 2) if uplifts else None,
        "guardrail_breach_count": sum(
            1 for c in cases
            if any(r.startswith("guardrail_violation") for r in c["reasons"])
        ),
        "segment_conflict_count": sum(1 for c in cases if c["segment_conflict"]),
        "reversal_count": sum(1 for c in cases if c["long_term_reversal"]),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cases = build_corpus()
    with open(OUT_DIR / "corpus_100.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"  docs/data/corpus_100.json     {len(cases)} cases")

    stats = build_stats(cases)
    with open(OUT_DIR / "corpus_stats.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"  docs/data/corpus_stats.json   {stats['total']} total, "
          f"{stats['decision_counts']}")

    print(f"\nDone. Output: {OUT_DIR}")

    index_jsonl = RUNS_DIR / "index.jsonl"
    if index_jsonl.exists():
        print("\nReplay data available. To build replay exports run:")
        print("  python3 tools/build_replays_index.py")


if __name__ == "__main__":
    main()
