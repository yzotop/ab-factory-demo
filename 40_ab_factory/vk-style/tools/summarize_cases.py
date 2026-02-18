#!/usr/bin/env python3
"""
Print a compact summary table of all A/B test cases.

No external dependencies — pure Python 3.10+.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CASES_DIR = SCRIPT_DIR.parent / "cases"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    case_dirs = sorted(d for d in CASES_DIR.iterdir() if d.is_dir() and d.name.startswith("case_"))
    if not case_dirs:
        print("No cases found.")
        sys.exit(0)

    rows: list[dict] = []
    for case_dir in case_dirs:
        contract_path = case_dir / "contract.json"
        truth_path = case_dir / "truth.json"

        contract = load_json(contract_path) if contract_path.exists() else {}
        truth = load_json(truth_path) if truth_path.exists() else {}

        rows.append({
            "case_id": contract.get("case_id", "?"),
            "title": contract.get("title", "?")[:52],
            "metric": contract.get("primary_metric", {}).get("name", "?"),
            "effect": f"{truth.get('primary_effect_relative', 0):+.1%}",
            "sig": "yes" if truth.get("is_stat_sig") else "no",
            "guard": "ok" if truth.get("guardrails_ok") else "FAIL",
            "decision": truth.get("expected_decision", "?"),
            "reasons": ", ".join(truth.get("key_reasons", [])),
        })

    # Print table
    hdr = (
        f"{'case_id':<10} {'title':<54} {'metric':<8} {'effect':>7} "
        f"{'sig':>4} {'guard':>5} {'decision':<15} {'reasons'}"
    )
    sep = (
        f"{'-'*9:<10} {'-'*53:<54} {'-'*7:<8} {'-'*6:>7} "
        f"{'-'*3:>4} {'-'*4:>5} {'-'*14:<15} {'-'*30}"
    )

    print()
    print("AB Factory — Case Summary")
    print("=" * 120)
    print(hdr)
    print(sep)
    for r in rows:
        print(
            f"{r['case_id']:<10} {r['title']:<54} {r['metric']:<8} {r['effect']:>7} "
            f"{r['sig']:>4} {r['guard']:>5} {r['decision']:<15} {r['reasons']}"
        )
    print()
    print(f"Total: {len(rows)} cases")


if __name__ == "__main__":
    main()
