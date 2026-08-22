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
   5%  peeking                → investigate
   4%  long-term value trap   → do_not_ship
   5%  marketplace interference → investigate
   5%  ratio metric stats     → investigate
   3%  post-treatment selection → do_not_ship
   4%  Twyman's law (implausible lift) → investigate
   4%  exposure dilution (ITT)       → investigate
   4%  seasonality / promo period    → investigate
   3%  unit mismatch (pseudoreplication) → investigate
   3%  control contamination (shareable)  → investigate
   3%  bot traffic inflation              → investigate
   3%  HARKing (post-hoc hypothesis)      → investigate
   3%  segment heterogeneity (no interaction) → investigate
   2%  winner's curse (best-of-N)        → investigate
   2%  CUPED not applied (underpowered)   → investigate
   2%  heavy-tail revenue distortion      → investigate
   2%  bad OEC (proxy up, goal down)      → do_not_ship
   2%  incomplete weekly cycle            → investigate
   2%  external shock mid-test           → investigate
   2%  narrow population generalization  → investigate
   2%  missing data / survivorship bias → investigate
   2%  event duplication (no dedup)     → investigate
   2%  logging schema mismatch          → investigate

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
# Пары сегментов — противопоставления, на которых строятся segment_conflict
# и simpson_paradox: площадка размещения, тип размещения, платформа.
# editorial/algorithmic — редакционная лента против алгоритмической; раньше
# здесь стояли названия реальных продуктов, что привязывало синтетический
# корпус к конкретной компании.
SEGMENTS_POOL = [["editorial", "algorithmic"], ["feed", "article"], ["mobile", "desktop"]]
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
TITLES_UNIT_RANDOMIZATION = [
    "Session-level revenue readout",
    "Per-event CTR significance test",
    "Session-grain metric experiment",
    "Event-level uplift analysis",
]
TITLES_CONTAMINATION = [
    "Shareable referral link promo",
    "Social invite reward banner",
    "Viral share-to-unlock offer",
    "Friend-referral ad credit test",
]
TITLES_BOTS = [
    "New placement traffic audit",
    "Format rollout quality check",
    "Inventory source monitoring test",
    "Demand-side traffic validation",
]
TITLES_HARKING = [
    "Premium cohort uplift readout",
    "High-value segment deep-dive",
    "Loyal-user monetization test",
    "Subscriber tier format experiment",
]
TITLES_HETEROGENEITY = [
    "Cross-device format rollout",
    "Mobile vs desktop ad density test",
    "Platform-specific layout experiment",
    "Surface-specific pricing test",
]
TITLES_WINNERS_CURSE = [
    "Multi-variant champion selection",
    "Best-of-batch format rollout",
    "Variant tournament winner deploy",
    "Top-performing creative selection",
]
HARKING_SEGMENTS = ["premium", "high_value", "loyal_subscriber"]
# Порядок значим: первым идёт сегмент с ростом. Он обязан быть меньшинством
# по выручке — средневзвешенное не может лежать вне сегментных значений.
HETEROGENEITY_SEGMENTS = ["desktop", "mobile"]
TITLES_CUPED = [
    "Pre-period covariate readout",
    "Baseline-adjusted revenue test",
    "Covariate-enriched pilot",
    "Matched pre-period experiment",
]
TITLES_HEAVY_TAILS = [
    "Whale-sensitive revenue test",
    "High-variance monetization pilot",
    "Top-spender revenue readout",
    "Skewed revenue distribution test",
]
TITLES_BAD_OEC = [
    "CTR-first layout optimization",
    "Click-surface expansion test",
    "Engagement proxy format rollout",
    "CTR-maximizing placement test",
]
TITLES_INCOMPLETE_CYCLES = [
    "Mid-week format pilot",
    "Weekday-only readout test",
    "Tue-start experiment window",
    "Business-day metrics check",
]
TITLES_EXTERNAL_SHOCK = [
    "In-flight promo overlap test",
    "Concurrent campaign experiment",
    "Mid-test marketing push readout",
    "Overlapping promo window test",
]
TITLES_NARROW_GENERALIZATION = [
    "Power-user cohort rollout",
    "Top-decile activity experiment",
    "Heavy-user monetization test",
    "High-engagement segment pilot",
]
TITLES_MISSING_DATA = [
    "Partial-coverage metrics readout",
    "Tracking-gap experiment review",
    "Incomplete event logging test",
    "Dropped-events analysis pilot",
]
TITLES_EVENT_DUPLICATION = [
    "Retry-heavy client conversion test",
    "No-dedup event counting experiment",
    "Client retry inflation pilot",
    "Raw event stream A/B readout",
]
TITLES_LOGGING_BUG = [
    "SDK v2 rollout experiment",
    "New logging schema pilot",
    "Instrumentation upgrade A/B test",
    "Client SDK migration readout",
]


def _rand_date(year: int = 2025) -> date:
    m = random.randint(1, 11)
    d = random.randint(1, 28)
    return date(year, m, d)


def _round(v: float, decimals: int = 6) -> float:
    return round(v, decimals)


def _metrics(n_users, revenue, shows, fillrate, ctr) -> dict:
    """Собрать строку метрик. cpm выводится ПОСЛЕДНИМ из уже округлённой
    выручки, поэтому определение revenue == shows * cpm / 1000 выполняется
    точно, а не приблизительно."""
    revenue = _round(revenue, 2)
    shows = int(shows)
    return {
        "n_users": int(n_users),
        "revenue": revenue,
        "cpm": _round(revenue * 1000 / shows, 2),
        "fillrate": fillrate,
        "ctr": ctr,
        "shows": shows,
    }


def _aggregate(parts: list[dict]) -> dict:
    """Строка all как сумма сегментов. Складываются уже округлённые числа,
    поэтому сегменты дают итог до копейки, а не до допуска."""
    n = sum(p["n_users"] for p in parts)
    revenue = _round(sum(p["revenue"] for p in parts), 2)
    shows = sum(p["shows"] for p in parts)
    return {
        "n_users": n,
        "revenue": revenue,
        "cpm": _round(revenue * 1000 / shows, 2),
        "fillrate": _round(sum(p["fillrate"] * p["n_users"] for p in parts) / n, 3),
        "ctr": _round(sum(p["ctr"] * p["n_users"] for p in parts) / n, 4),
        "shows": shows,
    }


def _build_base_metrics() -> dict[str, float]:
    """Метрики контрольной группы.

    Первичны shows и cpm, выручка выводится из них. Раньше все три
    разыгрывались независимо, и определение CPM не выполнялось
    в 629 кейсах из 660.
    """
    shows = random.randint(8_000_000, 30_000_000)
    cpm = round(random.uniform(50, 300), 2)
    return _metrics(
        n_users=random.randint(200_000, 800_000),
        revenue=shows * cpm / 1000,
        shows=shows,
        fillrate=round(random.uniform(0.60, 0.95), 3),
        ctr=round(random.uniform(0.03, 0.08), 4),
    )


def _apply_effect(base: dict, revenue_eff: float, ctr_eff: float,
                  n_users: int | None = None) -> dict:
    """Тестовая группа для кейсов без разбивки по сегментам.

    revenue_eff — эффект на выручку НА ПОЛЬЗОВАТЕЛЯ: единица рандомизации
    пользователь, значит праймари-метрика это ARPU. Раньше множитель
    применялся к суммарной выручке, а n_users при этом независимо дрожал
    на +-2000, и заявленный эффект расходился с фактическим в 100 кейсах.

    n_users — размер тест-арма, когда его задаёт сам механизм: в srm сплит
    перекошен намеренно. Раньше srm присваивал test["n_users"] уже ПОСЛЕ
    расчёта выручки, и заявленный эффект расходился с фактическим во всех
    18 кейсах механизма.

    Порядок вывода: n_users -> shows -> revenue -> cpm.
    """
    if n_users is None:
        n_users = base["n_users"] + random.randint(-2000, 2000)
    scale = n_users / base["n_users"]
    return _metrics(
        n_users=n_users,
        revenue=base["revenue"] * scale * (1 + revenue_eff),
        shows=round(base["shows"] * scale * random.uniform(0.995, 1.005)),
        fillrate=_round(base["fillrate"] * (1 + random.uniform(-0.005, 0.005)), 3),
        ctr=_round(base["ctr"] * (1 + ctr_eff), 4),
    )


def _solve_weight(overall_eff: float, eff1: float, eff2: float) -> float | None:
    """Доля ВЫРУЧКИ первого сегмента, при которой средневзвешенное сегментных
    эффектов равно общему.

    Решать надо именно вес: эффекты сегментов задают механизм и потому
    неприкосновенны, а вес не задаёт ничего и раньше брался с потолка.
    Отсюда же следует, что общий эффект обязан лежать МЕЖДУ сегментными, —
    спецификация heterogeneity этому не удовлетворяла и была невыполнима.

    None — решения в разумных границах нет, вызывающий перерозыгрывает.
    """
    if abs(eff1 - eff2) < 1e-9:
        return None
    w = (overall_eff - eff2) / (eff1 - eff2)
    return w if 0.03 <= w <= 0.92 else None


def _user_share(weight: float, rpu_ratio: float) -> float:
    """Доля ПОЛЬЗОВАТЕЛЕЙ первого сегмента при заданной доле выручки и
    заданном отношении выручки на пользователя между сегментами."""
    q = (weight / (1 - weight)) / rpu_ratio
    return q / (1 + q)


def _segmented_metrics(base: dict, specs: list[dict],
                       ctr_eff: float) -> tuple[dict, dict, list[dict]]:
    """Построить сегменты, а агрегат получить их сложением.

    Раньше было наоборот: агрегат разыгрывался сам по себе через
    _apply_effect, сегменты резались из base одинаковыми долями в обеих
    группах. Ни сумма сегментов не давала строку all, ни общий эффект
    не был средневзвешенным сегментных.

    specs — по словарю на сегмент:
        name      имя сегмента
        u_c, u_t  доли пользователей в контроле и в тесте, каждая сумма = 1.
                  Разные доли и есть сдвиг микса; в корректно рандомизованном
                  тесте они совпадают, и тогда парадокса Симпсона быть не может.
        rpu_rel   выручка на пользователя, ненормированная: значимо только
                  отношение между сегментами
        rev_eff   эффект внутри сегмента, на пользователя
    """
    n_control = base["n_users"]
    n_test = n_control + random.randint(-2000, 2000)
    rpu_all = base["revenue"] / n_control
    shows_per_user = base["shows"] / n_control
    norm = sum(s["u_c"] * s["rpu_rel"] for s in specs)

    segs = []
    for s in specs:
        rpu = rpu_all * s["rpu_rel"] / norm
        n_c = int(round(n_control * s["u_c"]))
        n_t = int(round(n_test * s["u_t"]))
        ctr_c = _round(base["ctr"] * random.uniform(0.90, 1.10), 4)
        fill_c = _round(base["fillrate"] * random.uniform(0.97, 1.03), 3)
        segs.append({
            "name": s["name"],
            "rev_eff": s["rev_eff"],
            "control": _metrics(
                n_c, rpu * n_c,
                round(shows_per_user * n_c * random.uniform(0.98, 1.02)),
                fill_c, ctr_c),
            "test": _metrics(
                n_t, rpu * (1 + s["rev_eff"]) * n_t,
                round(shows_per_user * n_t * random.uniform(0.98, 1.02)),
                _round(fill_c * (1 + random.uniform(-0.005, 0.005)), 3),
                _round(ctr_c * (1 + ctr_eff), 4)),
        })

    return (_aggregate([s["control"] for s in segs]),
            _aggregate([s["test"] for s in segs]),
            segs)


def _actual_effects(control: dict, test: dict) -> tuple[float, float]:
    """Эффекты, фактически лежащие в агрегате.

    В CSV и в truth.json пишем именно их, а не то, что задумывалось:
    иначе сводная строка снова разъедется с сегментами. Для механизмов
    без сдвига микса это то же число с точностью до округления;
    для simpson_paradox общий эффект и не может быть ничем иным.
    """
    rpu_c = control["revenue"] / control["n_users"]
    rpu_t = test["revenue"] / test["n_users"]
    return (round(rpu_t / rpu_c - 1, 4),
            round(test["ctr"] / control["ctr"] - 1, 4))


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

    # Эффекты сегментов — сам механизм: значимые и разного знака. Свободен
    # только вес, его и решаем, чтобы агрегат был их средневзвешенным.
    for _ in range(200):
        overall_eff = round(random.uniform(-0.005, 0.01), 4)
        seg1_eff = round(random.uniform(0.015, 0.05), 4)
        seg2_eff = round(random.uniform(-0.05, -0.01), 4)
        weight = _solve_weight(overall_eff, seg1_eff, seg2_eff)
        if weight is not None:
            break
    overall_pval = round(random.uniform(0.10, 0.50), 3)
    seg1_pval = round(random.uniform(0.001, 0.04), 4)
    seg2_pval = round(random.uniform(0.001, 0.04), 4)
    ctr_eff = round(random.uniform(-0.015, 0.005), 4)
    ctr_pval = round(random.uniform(0.10, 0.80), 3)

    base = _build_base_metrics()
    # Сегменты сопоставимы по деньгам на пользователя: ни один не премиальный.
    rpu_ratio = random.uniform(0.85, 1.20)
    share = _user_share(weight, rpu_ratio)
    base, test_all, segs = _segmented_metrics(base, [
        {"name": segments[0], "u_c": share, "u_t": share,
         "rpu_rel": rpu_ratio, "rev_eff": seg1_eff},
        {"name": segments[1], "u_c": 1 - share, "u_t": 1 - share,
         "rpu_rel": 1.0, "rev_eff": seg2_eff},
    ], ctr_eff)
    overall_eff, ctr_eff = _actual_effects(base, test_all)
    seg_data = [dict(s, rev_pval=p, ctr_eff=ctr_eff, ctr_pval=ctr_pval)
                for s, p in zip(segs, (seg1_pval, seg2_pval))]

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

    # Парадокс Симпсона существует только при сдвиге микса: если доли
    # сегментов в группах одинаковы, агрегат обязан лежать между сегментными
    # эффектами и положительным при двух отрицательных быть не может.
    # Поэтому свободный параметр здесь не вес, а доля сегмента в ТЕСТЕ,
    # и решается она из целевого агрегата.
    for _ in range(200):
        share_c = random.uniform(0.25, 0.40)      # доля богатого сегмента в контроле
        rpu_ratio = random.uniform(2.2, 3.5)      # во сколько раз он доходнее
        seg1_eff = round(random.uniform(-0.045, -0.030), 4)
        seg2_eff = round(random.uniform(-0.035, -0.020), 4)
        target = random.uniform(0.015, 0.030)     # каким должен выйти агрегат
        denom = rpu_ratio * (1 + seg1_eff) - (1 + seg2_eff)
        share_t = ((share_c * rpu_ratio + 1 - share_c) * (1 + target)
                   - (1 + seg2_eff)) / denom
        if 0.04 <= share_t - share_c <= 0.10 and 0.0 < share_t < 1.0:
            break
    overall_pval = round(random.uniform(0.001, 0.03), 4)
    seg1_pval = round(random.uniform(0.001, 0.04), 4)
    seg2_pval = round(random.uniform(0.001, 0.04), 4)
    ctr_eff = round(random.uniform(-0.01, 0.01), 4)
    ctr_pval = round(random.uniform(0.10, 0.80), 3)

    base = _build_base_metrics()
    base, test_all, segs = _segmented_metrics(base, [
        {"name": segments[0], "u_c": share_c, "u_t": share_t,
         "rpu_rel": rpu_ratio, "rev_eff": seg1_eff},
        {"name": segments[1], "u_c": 1 - share_c, "u_t": 1 - share_t,
         "rpu_rel": 1.0, "rev_eff": seg2_eff},
    ], ctr_eff)
    # Общий эффект не задаётся, а вычисляется: он и есть результат сдвига.
    overall_eff, ctr_eff = _actual_effects(base, test_all)
    seg_data = [dict(s, rev_pval=p, ctr_eff=ctr_eff, ctr_pval=ctr_pval)
                for s, p in zip(segs, (seg1_pval, seg2_pval))]

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
        "notes": (
            f"Experiment #{idx}. Rollout note: in the test arm the new placement "
            f"went live on {segments[0]} first, so that segment accounts for "
            f"{share_t:.0%} of test traffic against {share_c:.0%} in control. "
            f"Overall group sizes match the planned 50/50 split."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "do_not_ship",
        "primary_effect_relative": overall_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["simpson_paradox"],
        "human_rationale": (
            f"Aggregate {overall_eff:+.1%} sig, but both segments negative "
            f"({seg1_eff:+.1%}, {seg2_eff:+.1%}). The {segments[0]} share rose "
            f"{share_c:.0%} -> {share_t:.0%} between arms, and that segment earns "
            f"{rpu_ratio:.1f}x more per user — Simpson's paradox from mix shift."
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
    # Выручка в базе выведена из shows и cpm и от n_users не зависит,
    # поэтому подменить размер контрольной арм-группы здесь безопасно.
    base["n_users"] = n_control
    test = _apply_effect(base, rev_eff, ctr_eff, n_users=n_test)

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
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["peeking"],
        "human_rationale": (
            "Significant effect after early stop without sequential correction — "
            "false-positive risk inflated. The measurement is compromised but fixable: "
            "re-run with a sequential design / alpha-spending. Investigate, do not judge "
            "the feature on this data."
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


def gen_unit_randomization(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_UNIT_RANDOMIZATION) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)
    analysis_unit = random.choice(["session", "event"])

    rev_eff = round(random.uniform(0.015, 0.035), 4)
    rev_pval = round(random.uniform(0.002, 0.025), 4)
    ctr_eff = round(random.uniform(0.01, 0.025), 4)
    ctr_pval = round(random.uniform(0.005, 0.03), 4)
    sessions_per_user = round(random.uniform(8, 18), 1)

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
        "stats": {"method": "session_level_ttest", "alpha": 0.05, "power_target": 0.8},
        "decision_framework": {
            "rule": "ship_if_primary_sig_and_guardrails_ok",
            "practical_threshold_relative": 0.005,
        },
        "notes": (
            f"Randomization unit: user (50/50 at login). Analysis unit: {analysis_unit} "
            f"(~{sessions_per_user:.0f} {analysis_unit}s per user on average). Significance "
            f"from t-test at {analysis_unit} level — not clustered by randomization unit."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["unit_randomization"],
        "human_rationale": (
            f"Randomized by user but tested at {analysis_unit} level — pseudoreplication "
            f"understates variance, significance unreliable. Re-test at randomization "
            f"unit or use cluster-robust SE. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_contamination(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_CONTAMINATION) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    rev_eff = round(random.uniform(0.004, 0.008), 4)
    rev_pval = round(random.uniform(0.035, 0.095), 4)
    is_sig = rev_pval < 0.05
    ctr_eff = round(random.uniform(-0.003, 0.005), 4)
    ctr_pval = round(random.uniform(0.20, 0.55), 4)
    leak_rate = round(random.uniform(0.08, 0.18), 3)

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
            f"Feature is socially shareable — users can forward referral links / shared "
            f"account access to friends. Estimated ~{leak_rate:.0%} of control users may "
            f"receive partial exposure via leakage (contamination), diluting the contrast."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": is_sig,
        "guardrails_ok": True, "key_reasons": ["contamination"],
        "human_rationale": (
            f"Shareable feature — control likely partially exposed (contamination), "
            f"diluting the contrast. Small/null effect ({rev_eff:+.1%}, p={rev_pval}) may "
            f"be understated, not real. Assess leakage; cluster-randomize. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_bots(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_BOTS) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    bot_share = round(random.uniform(0.10, 0.15), 3)
    rev_eff = round(random.uniform(0.02, 0.04), 4)
    rev_pval = round(random.uniform(0.002, 0.02), 4)
    ctr_eff = round(random.uniform(0.015, 0.03), 4)
    ctr_pval = round(random.uniform(0.005, 0.025), 4)

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
            f"Test group traffic quality flag: ~{bot_share:.0%} of test sessions from "
            f"datacenter IPs / bot-like burst patterns (not seen in control). Metric "
            f"lift may be inflated by non-human traffic."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["bots"],
        "human_rationale": (
            f"Anomalous bot/datacenter traffic (~{bot_share:.0%}) in test group inflates "
            f"the metric. Filter and re-measure before trusting the lift. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_harking(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_HARKING) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)
    focus_seg = random.choice(HARKING_SEGMENTS)
    other_seg = "standard"

    # Агрегат почти нулевой при +9% в premium возможен только если premium
    # весит немного, а остальной трафик тянет вниз. Прежний розыгрыш давал
    # premium 35-45% пользователей, и вес выходил отрицательным в половине
    # случаев — то есть решения не существовало.
    for _ in range(200):
        overall_eff = round(random.uniform(-0.005, 0.008), 4)
        focus_eff = round(random.uniform(0.08, 0.10), 4)
        other_eff = round(overall_eff - random.uniform(0.004, 0.012), 4)
        weight = _solve_weight(overall_eff, focus_eff, other_eff)
        if weight is not None:
            break
    overall_pval = round(random.uniform(0.12, 0.45), 4)
    focus_pval = round(random.uniform(0.001, 0.02), 4)
    other_pval = round(random.uniform(0.25, 0.70), 4)
    ctr_eff = round(random.uniform(-0.005, 0.01), 4)
    ctr_pval = round(random.uniform(0.20, 0.60), 4)

    base = _build_base_metrics()
    # Premium платит больше — пользователей у него меньше, чем доля выручки.
    rpu_ratio = random.uniform(1.8, 3.0)
    share = _user_share(weight, rpu_ratio)
    base, test_all, segs = _segmented_metrics(base, [
        {"name": focus_seg, "u_c": share, "u_t": share,
         "rpu_rel": rpu_ratio, "rev_eff": focus_eff},
        {"name": other_seg, "u_c": 1 - share, "u_t": 1 - share,
         "rpu_rel": 1.0, "rev_eff": other_eff},
    ], ctr_eff)
    overall_eff, ctr_eff = _actual_effects(base, test_all)
    seg_data = [dict(s, rev_pval=p, ctr_eff=ctr_eff, ctr_pval=ctr_pval)
                for s, p in zip(segs, (focus_pval, other_pval))]

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
        "segments": [focus_seg, other_seg],
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
            f"No pre-registration on file. After the run, the {focus_seg} segment "
            f"showed a strong lift (+{focus_eff:.0%}) and is presented as the "
            f"leading finding — hypothesis was formed post-hoc from the data."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": overall_eff, "is_stat_sig": False,
        "guardrails_ok": True, "key_reasons": ["harking"],
        "human_rationale": (
            f"Hypothesis formed after seeing the data (HARKing) and presented as a priori. "
            f"The {focus_seg} segment was chosen post-hoc — significance not valid without "
            f"correction/replication. Confirm on fresh data. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test_all, overall_eff, overall_pval, ctr_eff, ctr_pval,
                      [focus_seg, other_seg], seg_data)
    return contract, truth, data


def gen_heterogeneity(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_HETEROGENEITY) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)
    segments = HETEROGENEITY_SEGMENTS

    # Прежняя спецификация была невыполнима: общий +0.6% при mobile +6.2%
    # и desktop +1.3% требует, чтобы средневзвешенное лежало ниже обоих
    # слагаемых. Теперь растёт desktop — меньшинство трафика с более высоким
    # ARPU, — а mobile стоит чуть ниже агрегата и тянет его к нулю.
    for _ in range(200):
        overall_eff = round(random.uniform(0.005, 0.012), 4)
        lift_eff = round(random.uniform(0.055, 0.07), 4)
        flat_eff = round(overall_eff - random.uniform(0.004, 0.014), 4)
        weight = _solve_weight(overall_eff, lift_eff, flat_eff)
        if weight is not None:
            break
    overall_pval = round(random.uniform(0.08, 0.25), 4)
    lift_pval = round(random.uniform(0.01, 0.04), 4)
    flat_pval = round(random.uniform(0.30, 0.65), 4)
    ctr_eff = round(random.uniform(-0.005, 0.01), 4)
    ctr_pval = round(random.uniform(0.20, 0.55), 4)

    base = _build_base_metrics()
    rpu_ratio = random.uniform(1.3, 2.2)
    share = _user_share(weight, rpu_ratio)
    base, test_all, segs = _segmented_metrics(base, [
        {"name": segments[0], "u_c": share, "u_t": share,
         "rpu_rel": rpu_ratio, "rev_eff": lift_eff},
        {"name": segments[1], "u_c": 1 - share, "u_t": 1 - share,
         "rpu_rel": 1.0, "rev_eff": flat_eff},
    ], ctr_eff)
    overall_eff, ctr_eff = _actual_effects(base, test_all)
    seg_data = [dict(s, rev_pval=p, ctr_eff=ctr_eff, ctr_pval=ctr_pval)
                for s, p in zip(segs, (lift_pval, flat_pval))]

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
        "notes": (
            f"Overall effect modest ({overall_eff:+.1%}). Segment readout: "
            f"{segments[0]} {lift_eff:+.1%} vs {segments[1]} {flat_eff:+.1%} — "
            f"team recommends rolling out on {segments[0]} only. No formal interaction "
            f"test; no multiplicity correction across segments."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": overall_eff, "is_stat_sig": overall_pval < 0.05,
        "guardrails_ok": True, "key_reasons": ["heterogeneity"],
        "human_rationale": (
            "Segment differences read as real without an interaction test — may be noise. "
            "Test interaction and correct for multiple segments before targeting. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test_all, overall_eff, overall_pval, ctr_eff, ctr_pval,
                      segments, seg_data)
    return contract, truth, data


def gen_winners_curse(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_WINNERS_CURSE) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    n_variants = random.choice([3, 4, 5, 6, 7])
    rev_eff = round(random.uniform(0.008, 0.015), 4)
    rev_pval = round(random.uniform(0.040, 0.050), 4)
    ctr_eff = round(random.uniform(0.005, 0.015), 4)
    ctr_pval = round(random.uniform(0.08, 0.20), 4)

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
            f"Champion variant selected as best of {n_variants} tested formats in the "
            f"same experiment window. Reported primary effect p={rev_pval:.3f} — "
            f"borderline significance after winner selection."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["winners_curse"],
        "human_rationale": (
            f"Borderline winner selected as best of {n_variants} variants — the estimate "
            f"is upward-biased (winner's curse). True effect likely smaller. Replicate "
            f"the winner before shipping. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_cuped_missing(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_CUPED) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    rev_eff = round(random.uniform(0.008, 0.018), 4)
    rev_pval = round(random.uniform(0.055, 0.095), 4)
    is_sig = rev_pval < 0.05
    ctr_eff = round(random.uniform(-0.005, 0.01), 4)
    ctr_pval = round(random.uniform(0.20, 0.55), 4)
    corr = round(random.uniform(0.55, 0.75), 2)

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
            f"Pre-period covariate data available (14-day baseline revenue per user, "
            f"ρ≈{corr} with in-period outcome) but CUPED variance reduction not applied — "
            f"analysis uses raw delta only. Point estimate {rev_eff:+.1%}, p={rev_pval}."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": is_sig,
        "guardrails_ok": True, "key_reasons": ["cuped_missing"],
        "human_rationale": (
            "Pre-period data available but CUPED not applied — variance reducible, "
            "test underpowered as-is. Apply CUPED and re-evaluate before concluding. "
            "Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_heavy_tails(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_HEAVY_TAILS) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    rev_eff = round(random.uniform(0.015, 0.028), 4)
    rev_pval = round(random.uniform(0.01, 0.035), 4)
    ctr_eff = round(random.uniform(-0.005, 0.01), 4)
    ctr_pval = round(random.uniform(0.15, 0.45), 4)
    top_share = round(random.uniform(0.004, 0.008), 4)
    mean_rev = round(random.uniform(8, 15), 1)
    max_rev = round(mean_rev * random.uniform(80, 150), 0)

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
            f"Per-user revenue highly skewed: mean ${mean_rev:.0f} vs max ${max_rev:.0f} "
            f"(top {top_share:.1%} spenders). Aggregate +{rev_eff:.1%} significant "
            f"(p={rev_pval}) but effect driven by a few extreme users — t-test on "
            f"means unreliable."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["heavy_tails"],
        "human_rationale": (
            f"Revenue effect driven by a few extreme spenders (top {top_share:.1%}) — "
            f"mean distorted by heavy tail, t-test unreliable. Use robust methods / "
            f"winsorize and re-check. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_bad_oec(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_BAD_OEC) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    ctr_eff = round(random.uniform(0.04, 0.06), 4)
    ctr_pval = round(random.uniform(0.001, 0.015), 4)
    rev_eff = round(random.uniform(-0.035, -0.018), 4)
    rev_pval = round(random.uniform(0.005, 0.025), 4)
    ret_drop = round(random.uniform(0.025, 0.045), 4)
    ctrl_ret = round(random.uniform(0.44, 0.48), 4)
    test_ret = round(ctrl_ret * (1 - ret_drop), 4)

    base = _build_base_metrics()
    test = _apply_effect(base, rev_eff, ctr_eff)

    contract = {
        "case_id": case_id, "title": title, "domain": "ads_monetization", "unit": "user",
        "variants": ["control", "test"],
        "time": {"start_date": str(start), "end_date": str(end), "horizon_days": horizon},
        "primary_metric": {"name": "ctr", "direction": "up", "mde_relative": 0.01},
        "guardrails": [
            {"name": "revenue", "direction": "up", "max_drop_relative": 0.02},
            {"name": "retention", "direction": "up", "max_drop_relative": 0.02},
        ],
        "stats": {"method": "delta", "alpha": 0.05, "power_target": 0.8},
        "decision_framework": {
            "rule": "ship_if_primary_sig_and_guardrails_ok",
            "practical_threshold_relative": 0.005,
        },
        "notes": (
            f"Experiment optimizing CTR (engagement proxy). Primary CTR +{ctr_eff:.0%} "
            f"significant. Business guardrails in export: revenue {rev_eff:+.1%} "
            f"(p={rev_pval}), D7 retention test {test_ret:.1%} vs control {ctrl_ret:.1%} "
            f"(−{ret_drop:.1%} relative)."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "do_not_ship",
        "primary_effect_relative": ctr_eff, "is_stat_sig": True,
        "guardrails_ok": False, "key_reasons": ["bad_oec"],
        "human_rationale": (
            f"Proxy (CTR) +{ctr_eff:.0%} but business guardrails down — revenue "
            f"{rev_eff:+.1%}, retention −{ret_drop:.1%}. Optimizing the wrong metric. "
            f"Clickbait pattern. Do not ship."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_incomplete_cycles(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_INCOMPLETE_CYCLES) + f" (v{idx})"
    year = random.choice([2024, 2025])
    start = date(year, random.randint(3, 11), random.randint(4, 25))
    while start.weekday() != 1:
        start += timedelta(days=1)
    end = start + timedelta(days=4)
    horizon = 5

    rev_eff = round(random.uniform(0.02, 0.04), 4)
    rev_pval = round(random.uniform(0.005, 0.03), 4)
    ctr_eff = round(random.uniform(0.01, 0.025), 4)
    ctr_pval = round(random.uniform(0.01, 0.04), 4)

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
            f"Test ran {start} to {end} (Tue–Sat, {horizon} days). Weekend not "
            f"included in the readout window."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["incomplete_cycles"],
        "human_rationale": (
            "Test ran only 5 weekday days — weekend not covered, weekly "
            "seasonality incomplete. Run full weekly cycles before deciding. "
            "Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_external_shock(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_EXTERNAL_SHOCK) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([10, 14])
    end = start + timedelta(days=horizon)
    shock_day = random.randint(3, min(6, horizon - 2))

    rev_eff = round(random.uniform(0.02, 0.045), 4)
    rev_pval = round(random.uniform(0.003, 0.025), 4)
    ctr_eff = round(random.uniform(0.01, 0.03), 4)
    ctr_pval = round(random.uniform(0.005, 0.03), 4)

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
            f"{horizon}-day experiment ({start} to {end}). A major marketing promo "
            f"launched on day {shock_day} of the test."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["external_shock"],
        "human_rationale": (
            "A major promo launched mid-test — confounds the result, measured effect "
            "may be from the promo, not the feature. Control for it (A/A segments) "
            "or re-run clean. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_narrow_generalization(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_NARROW_GENERALIZATION) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)
    cohort_pct = round(random.uniform(0.08, 0.12), 2)

    rev_eff = round(random.uniform(0.025, 0.045), 4)
    rev_pval = round(random.uniform(0.002, 0.02), 4)
    ctr_eff = round(random.uniform(0.01, 0.025), 4)
    ctr_pval = round(random.uniform(0.005, 0.03), 4)

    base = _build_base_metrics()
    base["n_users"] = int(base["n_users"] * cohort_pct)
    base["revenue"] = _round(base["revenue"] * cohort_pct)
    base["shows"] = int(base["shows"] * cohort_pct)
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
            f"Tested on power users only (top {cohort_pct:.0%} by activity). "
            f"Rollout plan is to all users."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["narrow_generalization"],
        "human_rationale": (
            "Effect measured on power users only but conclusion drawn for all users — "
            "does not generalize. Limit claim to tested population or test broadly. "
            "Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_missing_data(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_MISSING_DATA) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)
    missing_pct = round(random.uniform(0.16, 0.20), 2)

    rev_eff = round(random.uniform(0.025, 0.045), 4)
    rev_pval = round(random.uniform(0.003, 0.025), 4)
    ctr_eff = round(random.uniform(0.01, 0.025), 4)
    ctr_pval = round(random.uniform(0.005, 0.03), 4)

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
            f"~{missing_pct:.0%} of test-arm events missing metric values (tracking gap), "
            f"excluded from analysis."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["missing_data"],
        "human_rationale": (
            f"~{missing_pct:.0%} of test events missing and dropped — if missingness "
            f"correlates with treatment, the surviving sample is biased. Check "
            f"missingness mechanism before trusting the effect. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_event_duplication(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_EVENT_DUPLICATION) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)

    rev_eff = round(random.uniform(0.03, 0.05), 4)
    rev_pval = round(random.uniform(0.002, 0.02), 4)
    ctr_eff = round(random.uniform(0.01, 0.03), 4)
    ctr_pval = round(random.uniform(0.005, 0.025), 4)

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
            "Event dedup not applied; client retries may double-count conversions "
            "in the test arm."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["event_duplication"],
        "human_rationale": (
            "Deduplication not applied — retries may inflate conversions in test. "
            "Re-measure on deduplicated events before deciding. Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


def gen_logging_bug(case_id: str, idx: int) -> tuple[dict, dict, str]:
    title = random.choice(TITLES_LOGGING_BUG) + f" (v{idx})"
    start = _rand_date()
    horizon = random.choice([14, 21])
    end = start + timedelta(days=horizon)
    test_ver = random.choice([2, 3])

    rev_eff = round(random.uniform(0.025, 0.05), 4)
    rev_pval = round(random.uniform(0.002, 0.02), 4)
    ctr_eff = round(random.uniform(0.01, 0.025), 4)
    ctr_pval = round(random.uniform(0.005, 0.03), 4)

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
            f"Test arm shipped new SDK; metric logging schema changed "
            f"(v{test_ver} in test vs v1 in control) mid-experiment."
        ),
    }

    truth = {
        "case_id": case_id, "expected_decision": "investigate",
        "primary_effect_relative": rev_eff, "is_stat_sig": True,
        "guardrails_ok": True, "key_reasons": ["logging_bug"],
        "human_rationale": (
            f"Test and control use different logging schemas (v{test_ver} vs v1) — "
            f"metric not comparable across arms. Align instrumentation and re-measure. "
            f"Investigate."
        ),
    }

    data = _csv_rows(case_id, base, test, rev_eff, rev_pval, ctr_eff, ctr_pval)
    return contract, truth, data


GENERATORS = [
    (0.001, "clean_uplift", gen_clean_uplift),
    (0.071, "guardrail_breach", gen_guardrail_breach),
    (0.061, "practically_small", gen_practically_small),
    (0.05, "segment_conflict", gen_segment_conflict),
    (0.05, "long_term_reversal", gen_long_term_reversal),
    (0.05, "novelty_effect", gen_novelty_effect),
    (0.04, "simpson_paradox", gen_simpson_paradox),
    (0.04, "multiple_comparisons", gen_multiple_comparisons),
    (0.025, "underpowered", gen_underpowered),
    (0.028, "srm", gen_srm),
    (0.028, "peeking", gen_peeking),
    (0.025, "longterm_value", gen_longterm_value),
    (0.028, "interference", gen_interference),
    (0.028, "ratio_metric", gen_ratio_metric),
    (0.025, "posttreatment_selection", gen_posttreatment),
    (0.028, "twyman", gen_twyman),
    (0.028, "dilution", gen_dilution),
    (0.028, "seasonality", gen_seasonality),
    (0.028, "unit_randomization", gen_unit_randomization),
    (0.028, "contamination", gen_contamination),
    (0.028, "bots", gen_bots),
    (0.028, "harking", gen_harking),
    (0.028, "heterogeneity", gen_heterogeneity),
    (0.025, "winners_curse", gen_winners_curse),
    (0.025, "cuped_missing", gen_cuped_missing),
    (0.025, "heavy_tails", gen_heavy_tails),
    (0.025, "bad_oec", gen_bad_oec),
    (0.020, "incomplete_cycles", gen_incomplete_cycles),
    (0.020, "external_shock", gen_external_shock),
    (0.020, "narrow_generalization", gen_narrow_generalization),
    (0.022, "missing_data", gen_missing_data),
    (0.022, "event_duplication", gen_event_duplication),
    (0.022, "logging_bug", gen_logging_bug),
]


# Состав учебного корпуса cases_auto. Раньше нигде не был записан: корпус
# лежал в репозитории, а команды, которой его собрали, не существовало —
# README при этом обещал воспроизводимость. Числа сняты с опубликованного
# корпуса, порядок совпадает с GENERATORS.
PROFILES: dict[str, list[tuple[str, int]]] = {
    "auto": [
        ("clean_uplift", 30),   # пишет key_reasons ["primary_uplift"]
        ("guardrail_breach", 20),
        ("practically_small", 20),
        ("segment_conflict", 15),
        ("long_term_reversal", 15),
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic A/B cases")
    parser.add_argument("--n", type=int, default=300, help="Number of cases (default 300)")
    parser.add_argument("--out", type=str, default=None, help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument("--types", nargs="+", default=None,
                        help="Generate only these trap labels (even split across --n)")
    parser.add_argument("--profile", choices=sorted(PROFILES), default=None,
                        help="Named mechanism mix; 'auto' reproduces cases_auto")
    args = parser.parse_args()
    if args.profile and args.types:
        parser.error("--profile and --types are mutually exclusive")

    random.seed(args.seed)
    out_dir = Path(args.out) if args.out else DEFAULT_OUT

    schedule: list[tuple[str, callable]] = []
    if args.profile:
        by_label = {label: fn for _, label, fn in GENERATORS}
        for label, count in PROFILES[args.profile]:
            for _ in range(count):
                schedule.append((label, by_label[label]))
        random.shuffle(schedule)
    elif args.types:
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
    trap_labels: dict[str, str] = {}
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
        trap_labels[case_id] = label

    # Точная метка механизма на каждый кейс. build_corpus_index умеет выводить
    # тип из truth-причин, но различает только пять исходных сценариев и
    # сваливает остальные 497 кейсов в "other" — фильтр по механизму на сайте
    # по нему не построить. Раньше файл собирался разовым скриптом и терялся
    # при любой пересборке корпуса; теперь его пишет генератор.
    with open(out_dir / "_trap_labels.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(trap_labels, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # По расписанию, а не по --n: с --profile их число задаёт профиль,
    # и обход по args.n падал на несуществующем кейсе.
    print(f"Generated {len(schedule)} cases → {out_dir}")
    print()
    for label, count in sorted(type_counts.items()):
        print(f"  {label:<22} {count:>4}")
    print()
    decisions = {"ship": 0, "do_not_ship": 0, "investigate": 0}
    for i in range(len(schedule)):
        case_dir = out_dir / f"case_{i+1:03d}"
        with open(case_dir / "truth.json", "r", encoding="utf-8") as f:
            d = json.load(f)["expected_decision"]
        decisions[d] = decisions.get(d, 0) + 1
    for d, c in sorted(decisions.items()):
        print(f"  {d:<15} {c:>4}")


if __name__ == "__main__":
    main()
