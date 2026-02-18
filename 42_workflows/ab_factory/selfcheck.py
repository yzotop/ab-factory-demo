#!/usr/bin/env python3
"""
AB Factory — Self-check.

Runs all cases and verifies that agent decisions match truth.json.
Supports both manual cases (cases/) and generated cases (cases_auto/).

Usage:
  python3 selfcheck.py                     # manual cases only
  python3 selfcheck.py --auto              # cases_auto only
  python3 selfcheck.py --root /path/to/dir # custom directory
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AI_LAB = SCRIPT_DIR.parent.parent
AGENTS_DIR = AI_LAB / "41_agents" / "ab_factory"

sys.path.insert(0, str(AGENTS_DIR))

from run_case import discover_cases, run_one_case, make_run_id  # noqa: E402

sys.path.insert(0, str(SCRIPT_DIR))


def check_cases(cases: list[Path], root: Path, label: str) -> tuple[int, int]:
    total = len(cases)
    passed = 0

    print(f"Self-check [{label}]: {total} cases")
    print()
    print(f"  {'case_id':<10}  {'agent':<15}  {'truth':<15}  {'match'}")
    print(f"  {'-'*9:<10}  {'-'*14:<15}  {'-'*14:<15}  {'-'*6}")

    for case_dir in cases:
        with open(case_dir / "truth.json", "r", encoding="utf-8") as f:
            truth = json.load(f)

        expected = truth["expected_decision"]
        run_id = make_run_id()
        result = run_one_case(case_dir, root, run_id, quiet=True)
        actual = result["decision"]

        match = actual == expected
        icon = "PASS" if match else "FAIL"
        if match:
            passed += 1

        print(f"  {truth['case_id']:<10}  {actual:<15}  {expected:<15}  {icon}")

    return passed, total


def main() -> None:
    parser = argparse.ArgumentParser(description="AB Factory self-check")
    parser.add_argument("--auto", action="store_true", help="Check cases_auto instead of cases")
    parser.add_argument("--root", type=str, default=None, help="Custom root directory for cases")
    args = parser.parse_args()

    if args.root:
        root = Path(args.root)
        label = root.name
    elif args.auto:
        root = AI_LAB / "40_ab_factory" / "vk-style" / "cases_auto"
        label = "cases_auto"
    else:
        root = AI_LAB / "40_ab_factory" / "vk-style"
        label = "manual"

    if not root.exists():
        print(f"ERROR: {root} not found.", file=sys.stderr)
        sys.exit(1)

    cases = discover_cases(root)
    if not cases:
        print("No cases found.")
        sys.exit(1)

    passed, total = check_cases(cases, root, label)

    print()
    print(f"  total_cases:  {total}")
    print(f"  pass:         {passed}")
    print(f"  fail:         {total - passed}")
    print(f"  accuracy:     {passed / total * 100:.1f}%")
    print()

    if passed == total:
        print(f"All {total} cases PASS.")
    else:
        print(f"FAILURES: {total - passed} of {total}.")
        sys.exit(1)


if __name__ == "__main__":
    main()
