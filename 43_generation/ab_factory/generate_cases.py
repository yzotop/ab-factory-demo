#!/usr/bin/env python3
"""
AB Factory — Synthetic case generator.

Produces N internally-consistent A/B test cases that the decision agent
can classify correctly.  Deterministic via random.seed(42).

Distribution (of N cases):
  30%  clean uplift      → ship
  20%  guardrail breach  → do_not_ship
  20%  practically small → do_not_ship
  15%  segment conflict  → investigate
  15%  long-term reversal → do_not_ship

Usage:
  python3 generate_cases.py --n 300
  python3 generate_cases.py --n 50 --out ./my_cases
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AI_LAB = SCRIPT_DIR.parent.parent
DEFAULT_OUT = AI_LAB / "40_ab_factory" / "vk-style" / "cases_auto"

METRICS = ["revenue", "cpm", "fillrate", "ctr", "shows"]
SEGMENTS_POOL = [["news", "dzen"], ["feed", "article"], ["mobile", "desktop"]]
TITLES_SHIP = [
    "Bid floor optimization",
    "Ad slot refresh rate increase",
    "Native ad format rollout",
    "Waterfall priority reorder",
    "CPM floor auto-adjustment",
    "Inventory fill rate improvement",
    "New banner placement test",
    "RTB timeout reduction",
]
TITLES_GUARDRAIL = [
    "Aggressive ad pressure increase",
    "High-frequency interstitial test",
    "Below-fold ad density boost",
    "Scroll-triggered fullscreen ads",
    "Auto-play video ad insertion",
]
TITLES_SMALL = [
    "Lazy-load trigger offset tweak",
    "Ad container padding change",
    "Request batching micro-optimization",
    "CSS render path adjustment",
    "Prefetch timing shift",
]
TITLES_SEGMENT = [
    "Fullscreen format cross-surface test",
    "Premium placement in mixed feeds",
    "Segment-specific pricing experiment",
    "Cross-platform ad density test",
]
TITLES_REVERSAL = [
    "Pricing floor long-run test",
    "Demand-side budget frontloading check",
    "Floor raise 28-day holdout",
    "Advertiser supply adjustment test",
]


def _rand_date(year: int = 2025) -> date:
    m = random.randint(1, 11)
    d = random.randint(1, 28)
    return date(year, m, d)


def _round(v: float, decimals: int = 6) -> float:
    return round(v, decimals)


def _build_base_metrics() -> dict[str, float]:
    return {
        "n_users": random.randint(200_000, 800_000),
        "revenue": random.randint(1_000_000, 5_000_000),
        "cpm": round(random.uniform(50, 300), 2),
        "fillrate": round(random.uniform(0.60, 0.95), 3),
        "ctr": round(random.uniform(0.03, 0.08), 4),
        "shows": random.randint(8_000_000, 30_000_000),
    }


def _apply_effect(base: dict, revenue_eff: float, ctr_eff: float) -> dict:
    test = dict(base)
    test["n_users"] = base["n_users"] + random.randint(-2000, 2000)
    test["revenue"] = _round(base["revenue"] * (1 + revenue_eff))
    test["cpm"] = _round(base["cpm"] * (1 + revenue_eff), 2)
    test["fillrate"] = _round(base["fillrate"] * (1 + random.uniform(-0.005, 0.005)), 3)
    test["ctr"] = _round(base["ctr"] * (1 + ctr_eff), 4)
    test["shows"] = base["shows"] + random.randint(-50000, 50000)
    return test


def _csv_rows(
    case_id: str,
    control: dict,
    test: dict,
    rev_eff: float,
    rev_pval: float,
    ctr_eff: float,
    ctr_pval: float,
    segments: list[str] | None = None,
    seg_data: list[dict] | None = None,
) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    hdr = [
        "case_id", "segment", "variant", "n_users", "revenue", "cpm",
        "fillrate", "ctr", "shows",
        "revenue_effect_relative", "revenue_p_value",
        "ctr_effect_relative", "ctr_p_value",
    ]
    w.writerow(hdr)

    def _row(seg: str, var: str, m: dict, eff_r=None, pv_r=None, eff_c=None, pv_c=None):
        w.writerow([
            case_id, seg, var,
            int(m["n_users"]), _round(m["revenue"]), m["cpm"],
            m["fillrate"], m["ctr"], int(m["shows"]),
            _round(eff_r, 4) if eff_r is not None else "",
            _round(pv_r, 6) if pv_r is not None else "",
            _round(eff_c, 4) if eff_c is not None else "",
            _round(pv_c, 6) if pv_c is not None else "",
        ])

    _row("all", "control", control)
    _row("all", "test", test, rev_eff, rev_pval, ctr_eff, ctr_pval)

    if segments and seg_data:
        for seg, sd in zip(segments, seg_data):
            _row(seg, "control", sd["control"])
            _row(seg, "test", sd["test"],
                 sd["rev_eff"], sd["rev_pval"], sd["ctr_eff"], sd["ctr_pval"])

    return buf.getvalue()


# ---- Case type generators ----

def gen_clean_uplift(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_SHIP) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([7, 14])
    end = start + timedelta(days=horizon)

    pm_name = random.choice(["revenue", "cpm", "ctr"])
    mde = round(random.uniform(0.005, 0.02), 3)
    practical = round(random.uniform(0.003, mde - 0.001), 3)
    rev_eff = round(random.uniform(max(practical + 0.002, 0.01), 0.05), 4)
    rev_pval = round(random.uniform(0.001, 0.04), 4)
    ctr_eff = round(random.uniform(-0.02, 0.02), 4)
    ctr_pval = round(random.uniform(0.10, 0.90), 3)

    base = _build_base_metrics()
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
        "time": {"start_date": str(start), "end_date": str(end), "horizon_days": horizon},
        "primary_metric": {"name": "revenue", "direction": "up", "mde_relative": mde},
        "guardrails": [
            {"name": "ctr", "direction": "up", "max_drop_relative": 0.03},
            {"name": "dau", "direction": "neutral", "max_drop_relative": 0.02},
        ],
        "stats": {"method": "delta", "alpha": 0.05, "power_target": 0.8},
        "decision_framework": {
            "rule": "ship_if_primary_sig_and_guardrails_ok",
            "practical_threshold_relative": practical,
        },
        "notes": f"Standard experiment #{idx}. Clean uplift expected.",
    }

    truth = {
        "case_id": case_id, "expected_decision": "ship",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["primary_uplift"],
        "human_rationale": f"Revenue +{rev_eff:.1%}, p={rev_pval}, above practical threshold. Guardrails OK.",
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_guardrail_breach(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_GUARDRAIL) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([7, 14])
    end = start + timedelta(days=horizon)

    rev_eff = round(random.uniform(0.008, 0.03), 4)
    rev_pval = round(random.uniform(0.001, 0.04), 4)
    max_drop = 0.03
    ctr_drop = round(random.uniform(max_drop + 0.005, max_drop + 0.04), 4)
    ctr_eff = -ctr_drop
    ctr_pval = round(random.uniform(0.001, 0.04), 4)
    practical = round(random.uniform(0.003, 0.008), 3)

    base = _build_base_metrics()
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
        "time": {"start_date": str(start), "end_date": str(end), "horizon_days": horizon},
        "primary_metric": {"name": "revenue", "direction": "up", "mde_relative": 0.01},
        "guardrails": [
            {"name": "ctr", "direction": "up", "max_drop_relative": max_drop},
            {"name": "dau", "direction": "neutral", "max_drop_relative": 0.02},
        ],
        "stats": {"method": "delta", "alpha": 0.05, "power_target": 0.8},
        "decision_framework": {
            "rule": "ship_if_primary_sig_and_guardrails_ok",
            "practical_threshold_relative": practical,
        },
        "notes": f"Experiment #{idx}. Expected engagement trade-off.",
    }

    truth = {
        "case_id": case_id, "expected_decision": "do_not_ship",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": False,
        "key_reasons": ["primary_uplift", "guardrail_violation"],
        "human_rationale": f"Revenue +{rev_eff:.1%} but CTR dropped {ctr_eff:.1%}, breaching {max_drop:.0%} guardrail.",
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_practically_small(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_SMALL) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21, 28])
    end = start + timedelta(days=horizon)

    practical = round(random.uniform(0.005, 0.01), 3)
    rev_eff = round(random.uniform(0.001, practical - 0.001), 4)
    rev_pval = round(random.uniform(0.0001, 0.01), 5)
    ctr_eff = round(random.uniform(-0.01, 0.01), 4)
    ctr_pval = round(random.uniform(0.10, 0.90), 3)

    base = _build_base_metrics()
    base["n_users"] = random.randint(1_000_000, 3_000_000)
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
        "time": {"start_date": str(start), "end_date": str(end), "horizon_days": horizon},
        "primary_metric": {"name": "revenue", "direction": "up", "mde_relative": 0.005},
        "guardrails": [
            {"name": "ctr", "direction": "up", "max_drop_relative": 0.03},
        ],
        "stats": {"method": "delta", "alpha": 0.05, "power_target": 0.8},
        "decision_framework": {
            "rule": "ship_if_primary_sig_and_guardrails_ok",
            "practical_threshold_relative": practical,
        },
        "notes": f"High-power experiment #{idx}. Large sample makes tiny effects significant.",
    }

    truth = {
        "case_id": case_id, "expected_decision": "do_not_ship",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["practically_small"],
        "human_rationale": f"Revenue +{rev_eff:.2%}, significant but below practical threshold {practical:.1%}.",
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_segment_conflict(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_SEGMENT) + f" (v{idx})"
    start = _rand_date()
    horizon = 14
    end = start + timedelta(days=horizon)
    segments = random.choice(SEGMENTS_POOL)

    overall_eff = round(random.uniform(-0.005, 0.01), 4)
    overall_pval = round(random.uniform(0.10, 0.50), 3)
    seg1_eff = round(random.uniform(0.015, 0.05), 4)
    seg1_pval = round(random.uniform(0.001, 0.04), 4)
    seg2_eff = round(random.uniform(-0.05, -0.01), 4)
    seg2_pval = round(random.uniform(0.001, 0.04), 4)
    ctr_eff = round(random.uniform(-0.015, 0.005), 4)
    ctr_pval = round(random.uniform(0.10, 0.80), 3)

    base = _build_base_metrics()
    test_all = _apply_effect(base, overall_eff, ctr_eff)

    frac1 = round(random.uniform(0.45, 0.65), 2)
    frac2 = round(1.0 - frac1, 2)

    def _split(m: dict, frac: float) -> dict:
        return {
            "n_users": int(m["n_users"] * frac),
            "revenue": _round(m["revenue"] * frac),
            "cpm": m["cpm"],
            "fillrate": m["fillrate"],
            "ctr": m["ctr"],
            "shows": int(m["shows"] * frac),
        }

    seg_data = []
    for seg, frac, s_eff, s_pval in [
        (segments[0], frac1, seg1_eff, seg1_pval),
        (segments[1], frac2, seg2_eff, seg2_pval),
    ]:
        sc = _split(base, frac)
        st = _apply_effect(sc, s_eff, ctr_eff)
        seg_data.append({
            "control": sc, "test": st,
            "rev_eff": s_eff, "rev_pval": s_pval,
            "ctr_eff": ctr_eff, "ctr_pval": ctr_pval,
        })

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
        "segments": segments,
        "time": {"start_date": str(start), "end_date": str(end), "horizon_days": horizon},
        "primary_metric": {"name": "revenue", "direction": "up", "mde_relative": 0.01},
        "guardrails": [
            {"name": "ctr", "direction": "up", "max_drop_relative": 0.03},
        ],
        "stats": {"method": "delta", "alpha": 0.05, "power_target": 0.8},
        "decision_framework": {
            "rule": "ship_if_primary_sig_and_guardrails_ok",
            "practical_threshold_relative": 0.005,
        },
        "notes": f"Experiment #{idx}. Cross-segment test.",
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": overall_eff, "is_stat_sig": False,
        "guardrails_ok": True,
        "key_reasons": ["segment_conflict", "not_significant"],
        "human_rationale": f"Overall {overall_eff:+.1%} not sig. {segments[0]} {seg1_eff:+.1%} vs {segments[1]} {seg2_eff:+.1%}.",
    }

    data = _csv_rows(case_id, base, test_all, overall_eff, overall_pval, ctr_eff, ctr_pval,
                      segments, seg_data)
    return contract, truth, data


def gen_long_term_reversal(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_REVERSAL) + f" (v{idx})"
    start = _rand_date()
    horizon = 28
    end = start + timedelta(days=horizon)

    overall_eff = round(random.uniform(-0.005, 0.008), 4)
    overall_pval = round(random.uniform(0.10, 0.60), 3)
    ctr_eff = round(random.uniform(-0.02, 0.005), 4)
    ctr_pval = round(random.uniform(0.10, 0.80), 3)

    base = _build_base_metrics()
    test = _apply_effect(base, overall_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
        "time": {"start_date": str(start), "end_date": str(end), "horizon_days": horizon},
        "primary_metric": {"name": "revenue", "direction": "up", "mde_relative": 0.01},
        "guardrails": [
            {"name": "ctr", "direction": "up", "max_drop_relative": 0.03},
            {"name": "fillrate", "direction": "up", "max_drop_relative": 0.05},
        ],
        "stats": {"method": "delta", "alpha": 0.05, "power_target": 0.8},
        "decision_framework": {
            "rule": "ship_if_primary_sig_and_guardrails_ok",
            "practical_threshold_relative": 0.005,
        },
        "notes": f"28-day holdout #{idx}. Week-over-week analysis reveals trend reversal after week 2.",
    }

    truth = {
        "case_id": case_id, "expected_decision": "do_not_ship",
        "primary_effect_relative": overall_eff, "is_stat_sig": False,
        "guardrails_ok": True,
        "key_reasons": ["long_term_reversal", "not_significant"],
        "human_rationale": f"Aggregated {overall_eff:+.2%} not sig. Weekly trend shows early gain then reversal.",
    }

    data = _csv_rows(case_id, base, test, overall_eff, overall_pval, ctr_eff, ctr_pval)
    return contract, truth, data


GENERATORS = [
    (0.30, "clean_uplift", gen_clean_uplift),
    (0.20, "guardrail_breach", gen_guardrail_breach),
    (0.20, "practically_small", gen_practically_small),
    (0.15, "segment_conflict", gen_segment_conflict),
    (0.15, "long_term_reversal", gen_long_term_reversal),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic A/B cases")
    parser.add_argument("--n", type=int, default=300, help="Number of cases (default 300)")
    parser.add_argument("--out", type=str, default=None, help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    args = parser.parse_args()

    random.seed(args.seed)
    out_dir = Path(args.out) if args.out else DEFAULT_OUT

    schedule: list[tuple[str, callable]] = []
    for frac, label, gen_fn in GENERATORS:
        count = round(args.n * frac)
        for _ in range(count):
            schedule.append((label, gen_fn))
    while len(schedule) < args.n:
        schedule.append(("clean_uplift", gen_clean_uplift))
    schedule = schedule[:args.n]
    random.shuffle(schedule)

    out_dir.mkdir(parents=True, exist_ok=True)

    type_counts: dict[str, int] = {}
    for i, (label, gen_fn) in enumerate(schedule):
        num = i + 1
        case_id = f"case_{num:03d}"
        case_dir = out_dir / f"case_{num:03d}"
        case_dir.mkdir(parents=True, exist_ok=True)

        contract, truth, data = gen_fn(case_id, num)

        with open(case_dir / "contract.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(contract, f, ensure_ascii=False, indent=2)
            f.write("\n")
        with open(case_dir / "truth.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(truth, f, ensure_ascii=False, indent=2)
            f.write("\n")
        with open(case_dir / "data.csv", "w", encoding="utf-8", newline="\n") as f:
            f.write(data)

        type_counts[label] = type_counts.get(label, 0) + 1

    print(f"Generated {args.n} cases → {out_dir}")
    print()
    for label, count in sorted(type_counts.items()):
        print(f"  {label:<22} {count:>4}")
    print()
    decisions = {"ship": 0, "do_not_ship": 0, "investigate": 0}
    for i in range(args.n):
        case_dir = out_dir / f"case_{i+1:03d}"
        with open(case_dir / "truth.json", "r", encoding="utf-8") as f:
            d = json.load(f)["expected_decision"]
        decisions[d] = decisions.get(d, 0) + 1
    for d, c in sorted(decisions.items()):
        print(f"  {d:<15} {c:>4}")


if __name__ == "__main__":
    main()
