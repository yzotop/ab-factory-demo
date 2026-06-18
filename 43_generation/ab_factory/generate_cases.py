#!/usr/bin/env python3
"""
AB Factory — Synthetic case generator.

Produces N internally-consistent A/B test cases that the decision agent
can classify correctly.  Deterministic via random.seed(42).

Distribution (of N cases):
  18%  clean uplift           → ship
  12%  guardrail breach       → do_not_ship
  10%  practically small      → do_not_ship
   8%  segment conflict       → investigate
   8%  long-term reversal     → do_not_ship  (blind)
   8%  novelty effect         → do_not_ship  (blind)
   7%  Simpson's paradox      → do_not_ship
   7%  multiple comparisons   → do_not_ship
   5%  underpowered           → investigate
   5%  sample ratio mismatch  → investigate
   5%  peeking                → do_not_ship
   4%  long-term value trap   → do_not_ship
   5%  marketplace interference → investigate
   5%  ratio metric stats     → investigate
   3%  post-treatment selection → do_not_ship
   4%  Twyman's law (implausible lift) → investigate
   4%  exposure dilution (ITT)       → investigate
   4%  seasonality / promo period    → investigate

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
TITLES_NOVELTY = [
    "New ad format launch",
    "Fresh creative rotation test",
    "Redesigned ad unit rollout",
    "First-time interstitial format",
    "Novel placement debut",
]
TITLES_SIMPSON = [
    "Mix-shift pricing test",
    "Aggregate floor adjustment",
    "Blended inventory experiment",
    "Pooled segment rollout",
]
TITLES_MULTCOMP = [
    "Multi-metric dashboard test",
    "Broad KPI sweep experiment",
    "Full-funnel metric scan",
    "Exploratory metric battery",
]
TITLES_UNDERPOWERED = [
    "Early-stage pilot test",
    "Small-cohort experiment",
    "Limited rollout check",
    "Low-traffic placement test",
]
TITLES_SRM = [
    "Assignment pipeline audit test",
    "User-level split integrity check",
    "Randomization QA experiment",
    "Bucket balance monitoring test",
]
TITLES_PEEKING = [
    "Early-stop revenue monitor",
    "Sequential readout pilot",
    "Day-3 significance checkpoint",
    "Interim KPI gate test",
]
TITLES_LONGTERM_VALUE = [
    "Engagement-first format test",
    "CTR-optimized layout rollout",
    "Session depth boost experiment",
    "Click surface expansion test",
]
TITLES_INTERFERENCE = [
    "Shared auction pool bid test",
    "Marketplace inventory split experiment",
    "Common budget allocation test",
    "Two-sided ad marketplace rollout",
]
TITLES_RATIO_METRIC = [
    "CTR ratio readout experiment",
    "Click-rate per-impression test",
    "Event-level CTR significance check",
    "Impression-normalized click test",
]
TITLES_POSTTREATMENT = [
    "Activated-user uplift study",
    "Clicker-only conversion test",
    "Engaged cohort outcome analysis",
    "Feature-adopter performance readout",
]
TITLES_TWYMAN = [
    "Revenue surge format test",
    "Breakthrough monetization rollout",
    "Step-change ad yield experiment",
    "Record uplift placement test",
]
TITLES_DILUTION = [
    "Checkout error recovery prompt",
    "Payment-failure retry banner",
    "Cart-abandon rescue widget",
    "Declined-card fallback offer",
]
TITLES_SEASONALITY = [
    "Holiday promo layout test",
    "Year-end peak format rollout",
    "Black Friday ad density experiment",
    "New Year campaign slot test",
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


def _srm_chi2_p(n_control: int, n_test: int) -> tuple[float, float]:
    """Chi-square (1 df) for 50/50 split vs observed counts."""
    n = n_control + n_test
    expected = n / 2
    chi2 = (n_control - expected) ** 2 / expected + (n_test - expected) ** 2 / expected
    # Wilson-Hilferty approx for p-value when chi2 > 0
    if chi2 <= 0:
        return 0.0, 1.0
    z = ((chi2 / 1) ** (1 / 3) - (1 - 2 / (9 * 1))) / math.sqrt(2 / (9 * 1))
    p = 0.5 * math.erfc(z / math.sqrt(2))
    return chi2, max(p, 1e-12)


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


def gen_novelty_effect(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_NOVELTY) + f" (v{idx})"
    start = _rand_date()
    horizon = 7
    end = start + timedelta(days=horizon)

    rev_eff = round(random.uniform(0.02, 0.05), 4)
    rev_pval = round(random.uniform(0.001, 0.02), 4)
    ctr_eff = round(random.uniform(0.01, 0.04), 4)
    ctr_pval = round(random.uniform(0.001, 0.04), 4)

    base = _build_base_metrics()
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
        "time": {"start_date": str(start), "end_date": str(end), "horizon_days": horizon},
        "primary_metric": {"name": "revenue", "direction": "up", "mde_relative": 0.01},
        "guardrails": [
            {"name": "ctr", "direction": "up", "max_drop_relative": 0.03},
            {"name": "dau", "direction": "neutral", "max_drop_relative": 0.02},
        ],
        "stats": {"method": "delta", "alpha": 0.05, "power_target": 0.8},
        "decision_framework": {
            "rule": "ship_if_primary_sig_and_guardrails_ok",
            "practical_threshold_relative": 0.005,
        },
        "notes": (
            "7-day window. Strong early signal — possible novelty effect, "
            "needs longer horizon to confirm sustainability."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "do_not_ship",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["novelty_effect"],
        "human_rationale": (
            f"Revenue +{rev_eff:.1%} significant, but 7-day window likely captures "
            f"novelty. No long-horizon data to confirm it sustains."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_simpson_paradox(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_SIMPSON) + f" (v{idx})"
    start = _rand_date()
    horizon = 14
    end = start + timedelta(days=horizon)
    segments = random.choice(SEGMENTS_POOL)

    overall_eff = round(random.uniform(0.015, 0.03), 4)
    overall_pval = round(random.uniform(0.001, 0.03), 4)
    seg1_eff = round(random.uniform(-0.04, -0.015), 4)
    seg1_pval = round(random.uniform(0.001, 0.04), 4)
    seg2_eff = round(random.uniform(-0.04, -0.015), 4)
    seg2_pval = round(random.uniform(0.001, 0.04), 4)
    ctr_eff = round(random.uniform(-0.01, 0.01), 4)
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
        "notes": f"Experiment #{idx}. Aggregate uplift masks negative segment effects (mix shift).",
    }

    truth = {
        "case_id": case_id, "expected_decision": "do_not_ship",
        "primary_effect_relative": overall_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["simpson_paradox"],
        "human_rationale": (
            f"Aggregate +{overall_eff:.1%} sig, but both segments negative "
            f"({seg1_eff:+.1%}, {seg2_eff:+.1%}) — Simpson's paradox from mix shift."
        ),
    }

    data = _csv_rows(case_id, base, test_all, overall_eff, overall_pval, ctr_eff, ctr_pval,
                      segments, seg_data)
    return contract, truth, data


def gen_multiple_comparisons(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_MULTCOMP) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    rev_eff = round(random.uniform(-0.003, 0.005), 4)
    rev_pval = round(random.uniform(0.10, 0.50), 3)
    ctr_eff = round(random.uniform(-0.01, 0.01), 4)
    ctr_pval = round(random.uniform(0.10, 0.90), 3)
    false_pos_metric = random.choice(["cpm", "fillrate", "shows"])
    false_pos_pval = round(random.uniform(0.02, 0.049), 3)

    base = _build_base_metrics()
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
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
        "notes": (
            f"8 secondary metrics tested; {false_pos_metric} significant at p={false_pos_pval} "
            f"(expected false positive under multiple comparisons). Primary revenue not significant."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "do_not_ship",
        "primary_effect_relative": rev_eff, "is_stat_sig": False,
        "guardrails_ok": True,
        "key_reasons": ["multiple_comparisons", "not_significant"],
        "human_rationale": (
            f"Primary not sig. One of 8 secondary metrics sig at p={false_pos_pval} "
            f"— expected false positive under multiple comparisons."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_underpowered(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_UNDERPOWERED) + f" (v{idx})"
    start = _rand_date()
    horizon = 7
    end = start + timedelta(days=horizon)

    n_users = random.randint(20_000, 60_000)
    rev_eff = round(random.uniform(-0.02, 0.03), 4)
    rev_pval = round(random.uniform(0.15, 0.70), 3)
    ctr_eff = round(random.uniform(-0.02, 0.02), 4)
    ctr_pval = round(random.uniform(0.20, 0.80), 3)

    base = _build_base_metrics()
    base["n_users"] = n_users
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
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
        "notes": (
            f"Pilot on small cohort (n≈{n_users:,}). Underpowered — cannot conclude."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": False,
        "guardrails_ok": True,
        "key_reasons": ["underpowered", "not_significant"],
        "human_rationale": (
            f"Point estimate {rev_eff:+.1%} but n too small, p={rev_pval}. "
            f"Wide CI — need more data, cannot decide."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_srm(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_SRM) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    total_users = random.randint(400_000, 700_000)
    ctrl_share = round(random.uniform(0.505, 0.515), 4)
    n_control = int(total_users * ctrl_share)
    n_test = total_users - n_control
    chi2, srm_p = _srm_chi2_p(n_control, n_test)

    rev_eff = round(random.uniform(0.02, 0.045), 4)
    rev_pval = round(random.uniform(0.001, 0.02), 4)
    ctr_eff = round(random.uniform(0.01, 0.03), 4)
    ctr_pval = round(random.uniform(0.01, 0.04), 4)

    base = _build_base_metrics()
    base["n_users"] = n_control
    test = _apply_effect(base, rev_eff, ctr_eff)
    test["n_users"] = n_test

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
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
        "randomization": {"target_split": [0.5, 0.5], "unit": "user"},
        "notes": (
            f"Target randomization 50/50 by user. Observed split: "
            f"control {n_control:,} ({ctrl_share:.1%}) vs test {n_test:,} "
            f"({1 - ctrl_share:.1%}). SRM chi-square={chi2:.2f}, p={srm_p:.2e}."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["srm"],
        "human_rationale": (
            f"Split declared 50/50 but observed {ctrl_share:.1%}/{1 - ctrl_share:.1%} "
            f"differs significantly (SRM p={srm_p:.2e}). Comparison invalid until cause "
            f"found — investigate the randomization before any ship/no-ship decision. "
            f"The feature itself is not judged here; the measurement is broken."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_peeking(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_PEEKING) + f" (v{idx})"
    start = _rand_date()
    planned_horizon = 14
    actual_horizon = 3
    end = start + timedelta(days=actual_horizon)

    rev_eff = round(random.uniform(0.025, 0.05), 4)
    rev_pval = round(random.uniform(0.005, 0.045), 4)
    ctr_eff = round(random.uniform(0.01, 0.03), 4)
    ctr_pval = round(random.uniform(0.02, 0.05), 4)

    base = _build_base_metrics()
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
        "time": {
            "start_date": str(start), "end_date": str(end),
            "horizon_days": actual_horizon, "planned_horizon_days": planned_horizon,
        },
        "primary_metric": {"name": "revenue", "direction": "up", "mde_relative": 0.01},
        "guardrails": [
            {"name": "ctr", "direction": "up", "max_drop_relative": 0.03},
        ],
        "stats": {"method": "delta", "alpha": 0.05, "power_target": 0.8},
        "decision_framework": {
            "rule": "ship_if_primary_sig_and_guardrails_ok",
            "practical_threshold_relative": 0.005,
        },
        "notes": (
            f"Planned {planned_horizon}-day experiment; stopped on day {actual_horizon} "
            f"when revenue first reached p<{rev_pval:.3f}. No sequential alpha "
            f"correction applied (no O'Brien-Fleming / alpha-spending)."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "do_not_ship",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["peeking"],
        "human_rationale": (
            f"Significant +{rev_eff:.1%} after early stop on day {actual_horizon}/{planned_horizon} "
            f"without multiplicity control — inflated false-positive risk. Do not ship."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_longterm_value(case_id: str, idx: int) -> tuple[dict, dict, str]:
    """Subtype A (~50%): retention visible and falling. Subtype B: LTV absent — proxy-only trap."""
    subtype_b = idx % 2 == 0
    title = random.choice(TITLES_LONGTERM_VALUE) + f" (v{idx})"
    start = _rand_date()

    ctr_eff = round(random.uniform(0.03, 0.06), 4)
    ctr_pval = round(random.uniform(0.001, 0.02), 4)

    base = _build_base_metrics()

    if subtype_b:
        horizon = 7
        end = start + timedelta(days=horizon)
        rev_eff = round(random.uniform(0.005, 0.02), 4)
        rev_pval = round(random.uniform(0.05, 0.20), 4)
        test = _apply_effect(base, rev_eff, ctr_eff)

        contract = {
            "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
            "variants": ["control", "test"],
            "time": {"start_date": str(start), "end_date": str(end), "horizon_days": horizon},
            "primary_metric": {"name": "ctr", "direction": "up", "mde_relative": 0.01},
            "guardrails": [
                {"name": "retention", "direction": "up", "max_drop_relative": 0.02},
                {"name": "ltv", "direction": "up", "max_drop_relative": 0.02},
            ],
            "stats": {"method": "delta", "alpha": 0.05, "power_target": 0.8},
            "decision_framework": {
                "rule": "ship_if_primary_sig_and_guardrails_ok",
                "practical_threshold_relative": 0.005,
            },
            "notes": (
                f"{horizon}-day CTR readout only. Strong short-term engagement signal. "
                f"D7 retention and LTV cohorts are not mature yet — not included in this export."
            ),
        }

        truth = {
            "case_id": case_id, "expected_decision": "do_not_ship",
            "primary_effect_relative": ctr_eff, "is_stat_sig": True,
            "guardrails_ok": None,
            "key_reasons": ["longterm_value"],
            "human_rationale": (
                f"CTR +{ctr_eff:.1%} on a {horizon}-day window, but no retention/LTV data "
                f"to judge long-term value — shipping on a proxy alone is unsafe. Do not ship."
            ),
        }
    else:
        horizon = random.choice([14, 21])
        end = start + timedelta(days=horizon)
        rev_eff = round(random.uniform(-0.04, -0.015), 4)
        rev_pval = round(random.uniform(0.02, 0.08), 4)
        ret_drop = round(random.uniform(0.03, 0.06), 4)
        ctrl_ret = round(random.uniform(0.44, 0.48), 4)
        test_ret = round(ctrl_ret * (1 - ret_drop), 4)
        test = _apply_effect(base, rev_eff, ctr_eff)

        contract = {
            "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
            "variants": ["control", "test"],
            "time": {"start_date": str(start), "end_date": str(end), "horizon_days": horizon},
            "primary_metric": {"name": "ctr", "direction": "up", "mde_relative": 0.01},
            "guardrails": [
                {"name": "retention", "direction": "up", "max_drop_relative": 0.02},
                {"name": "revenue", "direction": "up", "max_drop_relative": 0.02},
            ],
            "stats": {"method": "delta", "alpha": 0.05, "power_target": 0.8},
            "decision_framework": {
                "rule": "ship_if_primary_sig_and_guardrails_ok",
                "practical_threshold_relative": 0.005,
            },
            "notes": (
                f"Primary readout is short-term CTR (engagement proxy). Cohort panel: "
                f"D7 retention test {test_ret:.1%} vs control {ctrl_ret:.1%} "
                f"(−{ret_drop:.1%} relative, breaches 2% guardrail)."
            ),
        }

        truth = {
            "case_id": case_id, "expected_decision": "do_not_ship",
            "primary_effect_relative": ctr_eff, "is_stat_sig": True,
            "guardrails_ok": False,
            "key_reasons": ["longterm_value"],
            "human_rationale": (
                f"CTR +{ctr_eff:.1%} (sugar rush) but D7 retention −{ret_drop:.1%} and "
                f"revenue {rev_eff:+.1%} — short-term proxy ≠ long-term value. Do not ship."
            ),
        }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_interference(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_INTERFERENCE) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    baseline_drop = round(random.uniform(0.025, 0.05), 4)
    rev_eff = round(random.uniform(0.025, 0.045), 4)
    rev_pval = round(random.uniform(0.001, 0.02), 4)
    ctr_eff = round(random.uniform(0.01, 0.03), 4)
    ctr_pval = round(random.uniform(0.01, 0.04), 4)

    base = _build_base_metrics()
    historical_rev = base["revenue"]
    base["revenue"] = _round(historical_rev * (1 - baseline_drop))
    base["shows"] = int(base["shows"] * (1 - baseline_drop * 0.7))
    base["cpm"] = _round(base["cpm"] * (1 - baseline_drop * 0.5), 2)
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
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
        "notes": (
            f"Two-sided marketplace experiment: control and test draw from shared "
            f"marketplace inventory / common auction budget (not isolated arms). "
            f"Pre-period control baseline revenue ${historical_rev:,.0f}; in-experiment "
            f"control ${int(base['revenue']):,} ({-baseline_drop:.1%} vs baseline) — "
            f"control cannibalized as test captures shared demand."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["interference"],
        "human_rationale": (
            "Two-sided market with shared inventory — test cannibalizes control, "
            "measured uplift inflated. Need isolation (cluster/geo split) before "
            "deciding. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_ratio_metric(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_RATIO_METRIC) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    ctr_eff = round(random.uniform(0.03, 0.06), 4)
    ctr_pval = round(random.uniform(0.001, 0.015), 4)
    rev_eff = round(random.uniform(0.005, 0.02), 4)
    rev_pval = round(random.uniform(0.05, 0.25), 4)

    base = _build_base_metrics()
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
        "time": {"start_date": str(start), "end_date": str(end), "horizon_days": horizon},
        "primary_metric": {"name": "ctr", "direction": "up", "mde_relative": 0.01},
        "guardrails": [
            {"name": "revenue", "direction": "up", "max_drop_relative": 0.03},
        ],
        "stats": {"method": "naive_event_ttest", "alpha": 0.05, "power_target": 0.8},
        "decision_framework": {
            "rule": "ship_if_primary_sig_and_guardrails_ok",
            "practical_threshold_relative": 0.005,
        },
        "notes": (
            "Primary metric CTR = clicks / impressions (ratio metric). Randomization "
            "unit is user. Significance from naive t-test on per-event rows — not "
            "delta-method or user-level bootstrap; ratio variance understated."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": ctr_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["ratio_metric"],
        "human_rationale": (
            "Ratio metric with naive event-level t-test under user randomization — "
            "variance understated, significance unreliable. Need delta-method / "
            "user-level bootstrap. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_posttreatment(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_POSTTREATMENT) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    rev_eff = round(random.uniform(0.03, 0.055), 4)
    rev_pval = round(random.uniform(0.001, 0.02), 4)
    ctr_eff = round(random.uniform(0.02, 0.04), 4)
    ctr_pval = round(random.uniform(0.001, 0.03), 4)
    activation_rate = round(random.uniform(0.18, 0.32), 3)

    base = _build_base_metrics()
    base["n_users"] = int(base["n_users"] * activation_rate)
    base["revenue"] = _round(base["revenue"] * activation_rate)
    base["shows"] = int(base["shows"] * activation_rate)
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
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
        "notes": (
            f"Analysis restricted to users who activated / clicked the new surface "
            f"(post-treatment conditioning; ~{activation_rate:.0%} of assigned users). "
            f"Not intent-to-treat — selection on a post-randomization outcome."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "do_not_ship",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["posttreatment_selection"],
        "human_rationale": (
            "Segmentation on a post-treatment outcome breaks randomization — "
            "selection bias. Looks clean but invalid. Do not ship."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_twyman(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_TWYMAN) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    rev_eff = round(random.uniform(0.35, 0.45), 4)
    rev_pval = round(random.uniform(1e-6, 1e-4), 6)
    ctr_eff = round(random.uniform(0.08, 0.15), 4)
    ctr_pval = round(random.uniform(1e-5, 0.001), 6)

    base = _build_base_metrics()
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
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
        "notes": (
            f"Standard {horizon}-day revenue readout. Primary shows large significant "
            f"uplift (+{rev_eff:.0%}); no product change beyond the tested variant "
            f"was deployed during the window."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["twyman"],
        "human_rationale": (
            f"Effect implausibly large (+{rev_eff:.0%}) — Twyman's law: likely a "
            f"tracking/logging bug or data artifact, not a real lift. Verify "
            f"instrumentation before trusting. Investigate, do not ship on its face."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_dilution(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_DILUTION) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    trigger_rate = round(random.uniform(0.05, 0.10), 3)
    triggered_lift = round(random.uniform(0.12, 0.22), 4)
    rev_eff = round(triggered_lift * trigger_rate, 4)
    rev_pval = round(random.uniform(0.08, 0.35), 4)
    ctr_eff = round(random.uniform(-0.005, 0.008), 4)
    ctr_pval = round(random.uniform(0.15, 0.60), 4)

    base = _build_base_metrics()
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
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
        "notes": (
            f"Feature triggers only for users hitting the checkout error path "
            f"(~{trigger_rate:.0%} of assigned users). Analysis is intent-to-treat "
            f"over the full randomized population — non-triggered users contribute "
            f"zeros and dilute the measured effect."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": False,
        "guardrails_ok": True, "key_reasons": ["dilution"],
        "human_rationale": (
            f"Feature triggers for ~{trigger_rate:.0%} of users but measured over all — "
            f"effect diluted to non-significance (ITT {rev_eff:+.1%}, p={rev_pval}). "
            f"Absence of significance here is not absence of effect. Re-analyze on "
            f"triggered population. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_seasonality(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_SEASONALITY) + f" (v{idx})"
    year = random.choice([2024, 2025])
    if idx % 2 == 0:
        start = date(year, 12, random.randint(18, 22))
        end = date(year + 1, 1, random.randint(2, 5))
        period_label = "holiday peak (Dec–Jan)"
    else:
        start = date(year, 11, random.randint(20, 26))
        end = start + timedelta(days=random.randint(7, 10))
        period_label = "major promo week (Black Friday / Cyber Monday)"
    horizon = (end - start).days

    rev_eff = round(random.uniform(0.02, 0.045), 4)
    rev_pval = round(random.uniform(0.001, 0.025), 4)
    ctr_eff = round(random.uniform(0.01, 0.03), 4)
    ctr_pval = round(random.uniform(0.005, 0.04), 4)

    base = _build_base_metrics()
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
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
        "notes": (
            f"Test ran {start} to {end} during {period_label}. Elevated baseline "
            f"traffic and promo-driven demand — atypical vs normal operating periods."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["seasonality"],
        "human_rationale": (
            f"Effect +{rev_eff:.1%} measured during {period_label} — may not generalize "
            f"to normal periods. Flag and replicate off-peak. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


GENERATORS = [
    (0.17, "clean_uplift", gen_clean_uplift),
    (0.10, "guardrail_breach", gen_guardrail_breach),
    (0.08, "practically_small", gen_practically_small),
    (0.06, "segment_conflict", gen_segment_conflict),
    (0.06, "long_term_reversal", gen_long_term_reversal),
    (0.06, "novelty_effect", gen_novelty_effect),
    (0.05, "simpson_paradox", gen_simpson_paradox),
    (0.05, "multiple_comparisons", gen_multiple_comparisons),
    (0.03, "underpowered", gen_underpowered),
    (0.04, "srm", gen_srm),
    (0.04, "peeking", gen_peeking),
    (0.03, "longterm_value", gen_longterm_value),
    (0.04, "interference", gen_interference),
    (0.04, "ratio_metric", gen_ratio_metric),
    (0.03, "posttreatment_selection", gen_posttreatment),
    (0.04, "twyman", gen_twyman),
    (0.04, "dilution", gen_dilution),
    (0.04, "seasonality", gen_seasonality),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic A/B cases")
    parser.add_argument("--n", type=int, default=300, help="Number of cases (default 300)")
    parser.add_argument("--out", type=str, default=None, help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument("--types", nargs="+", default=None,
                        help="Generate only these trap labels (even split across --n)")
    args = parser.parse_args()

    random.seed(args.seed)
    out_dir = Path(args.out) if args.out else DEFAULT_OUT

    schedule: list[tuple[str, callable]] = []
    if args.types:
        wanted = set(args.types)
        selected = [(label, gen_fn) for _, label, gen_fn in GENERATORS if label in wanted]
        missing = wanted - {label for label, _ in selected}
        if missing:
            parser.error(f"Unknown --types: {sorted(missing)}")
        if not selected:
            parser.error("No generators matched --types")
        per_type = max(1, args.n // len(selected))
        for label, gen_fn in selected:
            for _ in range(per_type):
                schedule.append((label, gen_fn))
        while len(schedule) < args.n:
            schedule.append(selected[len(schedule) % len(selected)])
        schedule = schedule[:args.n]
        random.shuffle(schedule)
    else:
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
