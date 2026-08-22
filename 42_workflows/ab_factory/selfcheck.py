#!/usr/bin/env python3
"""
AB Factory — Self-check.

Runs all cases and verifies that agent decisions match truth.json.
Supports both manual cases (cases/) and generated cases (cases_auto/).

Usage:
  python3 selfcheck.py                     # manual cases only
  python3 selfcheck.py --auto              # cases_auto only
  python3 selfcheck.py --root /path/to/dir # custom directory
  python3 selfcheck.py --invariants        # только согласованность данных

Про --invariants: обычный self-check проверяет ТОЛЬКО совпадение вердикта
агента с эталоном. Внутренняя согласованность данных не проверялась вообще —
корпус мог быть каким угодно внутри, лишь бы агент выдал ожидаемую метку.
Именно поэтому дефект в 638 кейсах из 660 дожил до публикации.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AI_LAB = SCRIPT_DIR.parent.parent
AGENTS_DIR = AI_LAB / "41_agents" / "ab_factory"

sys.path.insert(0, str(AGENTS_DIR))

from run_case import discover_cases, run_one_case, make_run_id  # noqa: E402

sys.path.insert(0, str(SCRIPT_DIR))


# ---------------------------------------------------------------------------
# Инварианты данных
# ---------------------------------------------------------------------------

# Допуски. Сегменты и CPM — с запасом на округление при записи CSV;
# эффект — жёстче, потому что 0.5 п.п. это уже содержательное расхождение.
TOL_SEGMENTS_PCT = 0.5
TOL_CPM_PCT = 5.0
TOL_EFFECT_ABS = 0.005


def _num(row: dict, col: str):
    try:
        return float(row[col])
    except (KeyError, ValueError, TypeError):
        return None


def check_invariants(case_dir: Path) -> list[str]:
    """Вернуть список нарушений для одного кейса. Пусто — кейс согласован."""
    with open(case_dir / "data.csv", "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return ["data.csv пуст"]

    problems: list[str] = []

    def pick(seg: str, var: str) -> dict | None:
        return next((r for r in rows
                     if r.get("segment") == seg and r.get("variant") == var), None)

    metrics = sorted({c[:-len("_effect_relative")] for c in rows[0]
                      if c.endswith("_effect_relative")})

    # 1. Сумма сегментов равна строке all.
    segs = {r["segment"] for r in rows} - {"all"}
    if segs:
        for var in ("control", "test"):
            agg = pick("all", var)
            if not agg:
                continue
            for col in ("revenue", "n_users"):
                a = _num(agg, col)
                parts = [_num(r, col) for r in rows
                         if r.get("segment") != "all" and r.get("variant") == var]
                if a is None or not a or any(p is None for p in parts):
                    continue
                diff = abs(a - sum(parts)) / a * 100
                if diff > TOL_SEGMENTS_PCT:
                    problems.append(
                        f"сегменты не дают итог: {col}/{var} "
                        f"{a:,.0f} против {sum(parts):,.0f} ({diff:.1f}%)")

    # 2. Заявленный эффект равен фактическому изменению среднего на пользователя.
    for m in metrics:
        c, tst = pick("all", "control"), pick("all", "test")
        if not c or not tst:
            continue
        claimed = _num(tst, f"{m}_effect_relative")
        if claimed is None:
            continue
        cn, tn = _num(c, "n_users"), _num(tst, "n_users")
        cv, tv = _num(c, m), _num(tst, m)
        if None in (cn, tn, cv, tv) or not cn or not tn or not cv:
            continue
        # Метрики-доли (ctr, fillrate) уже средние — их на юзеров не делят.
        per_user = m not in ("ctr", "fillrate", "cpm")
        cm = cv / cn if per_user else cv
        tm = tv / tn if per_user else tv
        if not cm:
            continue
        actual = (tm - cm) / cm
        if abs(claimed - actual) > TOL_EFFECT_ABS:
            problems.append(
                f"эффект {m}: заявлен {claimed*100:+.2f}%, "
                f"по данным {actual*100:+.2f}%")

    # 3. CPM по определению: выручка на тысячу показов.
    for r in rows:
        rev, cpm, shows = _num(r, "revenue"), _num(r, "cpm"), _num(r, "shows")
        if None in (rev, cpm, shows) or not rev:
            continue
        implied = shows * cpm / 1000
        diff = abs(implied - rev) / rev * 100
        if diff > TOL_CPM_PCT:
            problems.append(
                f"CPM не сходится ({r.get('segment')}/{r.get('variant')}): "
                f"выручка {rev:,.0f}, из shows×cpm {implied:,.0f} ({diff:.0f}%)")

    return problems


def run_invariants(cases: list[Path], label: str) -> int:
    """Прогнать инварианты. Вернуть число несогласованных кейсов."""
    by_check = {"сегменты": set(), "эффект": set(), "CPM": set()}
    broken: dict[str, list[str]] = {}

    for case_dir in cases:
        problems = check_invariants(case_dir)
        if not problems:
            continue
        broken[case_dir.name] = problems
        for p in problems:
            if p.startswith("сегменты"):
                by_check["сегменты"].add(case_dir.name)
            elif p.startswith("эффект"):
                by_check["эффект"].add(case_dir.name)
            elif p.startswith("CPM"):
                by_check["CPM"].add(case_dir.name)

    total = len(cases)
    print(f"Инварианты данных [{label}]: {total} кейсов")
    print()
    print(f"  {'проверка':<12}{'битых':>8}")
    print(f"  {'-'*11:<12}{'-'*7:>8}")
    for name, ids in by_check.items():
        print(f"  {name:<12}{len(ids):>8}")
    print(f"  {'-'*11:<12}{'-'*7:>8}")
    print(f"  {'объединение':<12}{len(broken):>8}")
    print(f"  {'чистых':<12}{total - len(broken):>8}")
    print()

    if broken:
        print("  первые нарушения:")
        for cid in sorted(broken)[:3]:
            print(f"    {cid}:")
            for p in broken[cid][:2]:
                print(f"      · {p}")
        print()
    return len(broken)


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
    parser.add_argument("--invariants", action="store_true",
                        help="Проверить только внутреннюю согласованность данных, "
                             "без прогона агента")
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

    if args.invariants:
        bad = run_invariants(cases, label)
        if bad:
            print(f"НЕСОГЛАСОВАНЫ: {bad} из {len(cases)}.")
            sys.exit(1)
        print(f"Все {len(cases)} кейсов согласованы.")
        return

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
