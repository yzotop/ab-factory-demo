"""
Decision agent — policy-driven decision framework with confidence scoring.

Decision priority (from policy):
  1. Guardrails (hard stop)     → do_not_ship
  2. Long-term reversal         → do_not_ship
  3. Segment conflict           → investigate
  4. Practical threshold        → do_not_ship
  5. Significance check         → do_not_ship / investigate
  6. Default (all clear + sig)  → ship
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from trace import emit

AGENT = "decision"

REVERSAL_KEYWORDS = ["reversal", "revers", "trend change"]


def _load_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_csv(p: Path) -> list[dict]:
    with open(p, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _sf(v: str) -> float | None:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _load_policy(policy_path: Path | None) -> dict:
    if policy_path is not None:
        p = Path(policy_path)
        if p.exists():
            return _load_json(p)
    default = Path(__file__).resolve().parent / "policy.json"
    if default.exists():
        return _load_json(default)
    return {}


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------

def _extract_signals(contract: dict, rows: list[dict], policy: dict) -> dict:
    """Extract all decision-relevant signals from contract + data + policy."""

    pm = contract.get("primary_metric", {})
    pm_name = pm.get("name", policy.get("primary_metric", {}).get("name", "revenue"))

    effect_col = f"{pm_name}_effect_relative"
    pval_col = f"{pm_name}_p_value"

    test_all = [r for r in rows if r.get("variant") != "control" and r.get("segment") == "all"]
    control_all = [r for r in rows if r.get("variant") == "control" and r.get("segment") == "all"]

    effect_rel = _sf(test_all[0].get(effect_col, "")) if test_all else None
    pval = _sf(test_all[0].get(pval_col, "")) if test_all else None
    uplift_pct = effect_rel * 100 if effect_rel is not None else None

    alpha = contract.get("stats", {}).get("alpha",
                policy.get("significance", {}).get("alpha", 0.05))
    is_sig = pval is not None and pval <= alpha

    # --- Guardrails ---
    guardrail_deltas: dict[str, float | None] = {}
    hard_violations: list[str] = []
    soft_violations: list[str] = []

    policy_guard_metrics: set[str] = set()
    for pg in policy.get("guardrails", []):
        metric = pg["metric"]
        policy_guard_metrics.add(metric)
        threshold_pct = pg.get("threshold_pct", 0)
        severity = pg.get("severity", "hard")

        eff = _sf(test_all[0].get(f"{metric}_effect_relative", "")) if test_all else None
        if eff is None and control_all and test_all:
            cv = _sf(control_all[0].get(metric, ""))
            tv = _sf(test_all[0].get(metric, ""))
            if cv is not None and tv is not None and cv != 0:
                eff = (tv - cv) / cv

        delta_pct = eff * 100 if eff is not None else None
        guardrail_deltas[metric] = delta_pct

        if delta_pct is not None and delta_pct <= threshold_pct:
            if severity == "hard":
                hard_violations.append(f"guardrail_violation:{metric}")
            else:
                soft_violations.append(f"guardrail_soft_violation:{metric}")

    # Contract-specific guardrails not covered by policy
    for g in contract.get("guardrails", []):
        gname = g["name"]
        if gname in policy_guard_metrics:
            continue
        direction = g.get("direction", "up")
        max_drop = g.get("max_drop_relative")
        max_rise = g.get("max_rise_relative")

        eff = _sf(test_all[0].get(f"{gname}_effect_relative", "")) if test_all else None
        if eff is None and control_all and test_all:
            cv = _sf(control_all[0].get(gname, ""))
            tv = _sf(test_all[0].get(gname, ""))
            if cv is not None and tv is not None and cv != 0:
                eff = (tv - cv) / cv

        guardrail_deltas[gname] = eff * 100 if eff is not None else None

        if eff is None:
            continue
        violated = False
        if direction in ("up", "neutral") and max_drop is not None:
            if eff < 0 and abs(eff) > max_drop:
                violated = True
        if direction == "down" and max_rise is not None:
            if eff > 0 and eff > max_rise:
                violated = True
        if violated:
            hard_violations.append(f"guardrail_violation:{gname}")

    # --- Segment conflict ---
    segments = contract.get("segments", [])
    segment_conflict = False
    if segments and len(segments) >= 2 and policy.get("segments", {}).get("enabled", True):
        min_gap = policy.get("segments", {}).get("min_abs_pct_gap_for_conflict", 2.0)
        seg_uplifts: list[tuple[str, float, float]] = []
        for seg in segments:
            seg_test = [r for r in rows
                        if r.get("segment") == seg and r.get("variant") != "control"]
            if not seg_test:
                continue
            eff = _sf(seg_test[0].get(effect_col, ""))
            pv = _sf(seg_test[0].get(pval_col, ""))
            if eff is not None and pv is not None:
                seg_uplifts.append((seg, eff * 100, pv))

        if len(seg_uplifts) >= 2:
            vals = [u for _, u, _ in seg_uplifts]
            gap = max(vals) - min(vals)
            has_sig_pos = any(u > 0 and p < alpha for _, u, p in seg_uplifts)
            has_sig_neg = any(u < 0 and p < alpha for _, u, p in seg_uplifts)
            segment_conflict = (gap >= min_gap and has_sig_pos and has_sig_neg)

    # --- Long-term reversal ---
    long_term_reversal = False
    if policy.get("long_term", {}).get("enabled", True):
        notes = contract.get("notes", "").lower()
        long_term_reversal = any(kw in notes for kw in REVERSAL_KEYWORDS)

    return {
        "primary_metric": pm_name,
        "primary_uplift_pct": uplift_pct,
        "effect_relative": effect_rel,
        "p_value": pval,
        "is_significant": is_sig,
        "alpha": alpha,
        "guardrails": guardrail_deltas,
        "guardrail_hard_violated": len(hard_violations) > 0,
        "guardrail_soft_violated": len(soft_violations) > 0,
        "hard_violations": hard_violations,
        "soft_violations": soft_violations,
        "segment_conflict": segment_conflict,
        "long_term_reversal": long_term_reversal,
        "has_segment_data": len(segments) >= 2,
        "has_long_term_data": long_term_reversal,
    }


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------

def _make_decision(
    signals: dict,
    contract: dict,
    policy: dict,
) -> tuple[str, list[str]]:
    """Apply decision steps in priority order. Returns (decision, reasons)."""

    # Effective practical threshold: max(contract, policy) — policy is the floor
    contract_practical_rel = (
        contract.get("decision_framework", {}).get("practical_threshold_relative"))
    policy_practical_pct = policy.get("primary_metric", {}).get(
        "practical_threshold_pct", 0.5)

    if contract_practical_rel is not None:
        practical_pct = max(contract_practical_rel * 100, policy_practical_pct)
    else:
        practical_pct = policy_practical_pct

    uplift_pct = signals["primary_uplift_pct"]
    above_practical = (uplift_pct is not None and abs(uplift_pct) >= practical_pct)

    # Step 1: Guardrails (hard stop)
    if signals["guardrail_hard_violated"]:
        reasons = list(signals["hard_violations"])
        if signals["is_significant"] and above_practical:
            reasons.insert(0, "primary_uplift")
        return "do_not_ship", reasons

    # Step 2: Long-term reversal
    if signals["long_term_reversal"]:
        reasons = ["long_term_reversal"]
        if not signals["is_significant"]:
            reasons.append("not_significant")
        action = policy.get("long_term", {}).get("reversal_action", "do_not_ship")
        return action, reasons

    # Step 3: Segment conflict
    if signals["segment_conflict"]:
        reasons = ["segment_conflict"]
        if not signals["is_significant"]:
            reasons.append("not_significant")
        action = policy.get("segments", {}).get("conflict_action", "investigate")
        return action, reasons

    # Step 4: Practical threshold
    if signals["is_significant"] and not above_practical:
        return "do_not_ship", ["practically_small"]

    # Step 5: Significance
    sig_policy = policy.get("significance", {})
    if sig_policy.get("require_significance_for_ship", True) and not signals["is_significant"]:
        if sig_policy.get("allow_investigate_if_not_significant", True):
            return "investigate", ["not_significant"]
        return "do_not_ship", ["not_significant"]

    # Step 6: Default — significant + above practical → ship
    if signals["is_significant"] and above_practical:
        return "ship", ["primary_uplift"]

    return "investigate", ["insufficient_evidence"]


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _compute_confidence(
    signals: dict,
    policy: dict,
) -> tuple[float, dict]:
    """Compute confidence via linear_score_sigmoid model."""

    cm = policy.get("confidence_model", {})
    base = cm.get("base", 0.0)
    weights = cm.get("weights", {})
    policy_practical = policy.get("primary_metric", {}).get("practical_threshold_pct", 0.5)
    alpha = policy.get("significance", {}).get("alpha", 0.05)

    factors: list[dict] = []
    score = base
    uplift = signals.get("primary_uplift_pct")

    def _add(name: str) -> None:
        nonlocal score
        w = weights.get(name, 0.0)
        factors.append({"name": name, "weight": w})
        score += w

    if uplift is not None and abs(uplift) >= policy_practical:
        _add("primary_uplift_strong")
    if uplift is not None and abs(uplift) < policy_practical:
        _add("primary_uplift_small")

    pval = signals.get("p_value")
    if pval is None or pval > alpha:
        _add("not_significant")

    if signals.get("guardrail_hard_violated"):
        _add("guardrail_hard_violation")
    if signals.get("guardrail_soft_violated"):
        _add("guardrail_soft_violation")
    if signals.get("segment_conflict"):
        _add("segment_conflict")
    if signals.get("long_term_reversal"):
        _add("long_term_reversal")

    # evidence_sparse: any expected data missing
    missing: list[str] = []
    if uplift is None:
        missing.append("primary_uplift_pct")
    if pval is None:
        missing.append("p_value")
    for pg in policy.get("guardrails", []):
        if signals.get("guardrails", {}).get(pg["metric"]) is None:
            missing.append(f"guardrail:{pg['metric']}")
    if policy.get("segments", {}).get("enabled") and not signals.get("has_segment_data"):
        missing.append("segments")
    if policy.get("long_term", {}).get("enabled") and not signals.get("has_long_term_data"):
        missing.append("long_term")

    if missing:
        _add("evidence_sparse")

    raw = _sigmoid(score)
    confidence = max(0.01, min(0.99, round(raw, 4)))

    return confidence, {
        "score": round(score, 4),
        "factors": factors,
        "missing_evidence": missing,
    }


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------

def run(
    case_dir: Path,
    out_dir: Path,
    trace_path: Path,
    run_id: str,
    *,
    policy_path: Path | None = None,
) -> dict:
    policy = _load_policy(policy_path)
    contract = _load_json(case_dir / "contract.json")
    case_id = contract["case_id"]

    emit(trace_path, run_id=run_id, case_id=case_id, agent=AGENT,
         step="start", event="policy_loaded",
         message=f"Policy {policy.get('policy_id','?')} v{policy.get('policy_version','?')}",
         payload={
             "policy_id": policy.get("policy_id", ""),
             "policy_version": policy.get("policy_version", ""),
         })

    rows = _load_csv(case_dir / "data.csv")

    signals = _extract_signals(contract, rows, policy)
    decision, reasons = _make_decision(signals, contract, policy)
    confidence, conf_explain = _compute_confidence(signals, policy)

    # Segment summary (for reporting)
    pm_name = signals["primary_metric"]
    effect_col = f"{pm_name}_effect_relative"
    pval_col = f"{pm_name}_p_value"
    alpha = signals["alpha"]

    segments_summary: dict[str, dict] = {}
    for seg in contract.get("segments", []):
        seg_test = [r for r in rows
                    if r.get("segment") == seg and r.get("variant") != "control"]
        if seg_test:
            se = _sf(seg_test[0].get(effect_col, ""))
            sp = _sf(seg_test[0].get(pval_col, ""))
            segments_summary[seg] = {
                "effect": se,
                "p_value": sp,
                "significant": sp is not None and sp < alpha,
            }

    result = {
        "case_id": case_id,
        "decision": decision,
        "confidence": confidence,
        "reasons": reasons,
        "policy": {
            "policy_id": policy.get("policy_id", ""),
            "policy_version": policy.get("policy_version", ""),
        },
        "signals": {
            "primary_metric": signals["primary_metric"],
            "primary_uplift_pct": signals["primary_uplift_pct"],
            "p_value": signals["p_value"],
            "is_significant": signals["is_significant"],
            "guardrails": signals["guardrails"],
            "segment_conflict": signals["segment_conflict"],
            "long_term_reversal": signals["long_term_reversal"],
        },
        "confidence_explain": conf_explain,
        "segments_summary": segments_summary,
    }

    # Write decision.json
    json_path = out_dir / "decision.json"
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Write decision.md
    practical_pct = policy.get("primary_metric", {}).get("practical_threshold_pct", 0.5)
    contract_prac = contract.get("decision_framework", {}).get("practical_threshold_relative")
    if contract_prac is not None:
        effective_prac = max(contract_prac * 100, practical_pct)
    else:
        effective_prac = practical_pct

    L: list[str] = []
    L.append(f"# Decision — {case_id}")
    L.append("")
    L.append(f"## Verdict: **{decision.upper().replace('_', ' ')}**")
    L.append(f"Confidence: **{confidence:.2f}**")
    L.append("")
    L.append(f"Reasons: {', '.join(reasons)}")
    L.append("")
    L.append(f"Policy: {policy.get('policy_id', '?')} v{policy.get('policy_version', '?')}")
    L.append("")
    L.append("## Key signals")
    L.append("")
    up = signals["primary_uplift_pct"]
    L.append(f"- Primary metric: {signals['primary_metric']}")
    L.append(f"- Uplift: {up:+.2f}%" if up is not None else "- Uplift: N/A")
    L.append(f"- p-value: {signals['p_value']}")
    L.append(f"- Significant: {'yes' if signals['is_significant'] else 'no'} (alpha={alpha})")
    L.append(f"- Above practical threshold ({effective_prac:.1f}%): {'yes' if up is not None and abs(up) >= effective_prac else 'no'}")
    L.append(f"- Guardrails: {'HARD VIOLATION' if signals['guardrail_hard_violated'] else ('soft warning' if signals['guardrail_soft_violated'] else 'all ok')}")
    for v in signals.get("hard_violations", []):
        L.append(f"  - {v}")
    L.append(f"- Segment conflict: {'yes' if signals['segment_conflict'] else 'no'}")
    L.append(f"- Long-term reversal: {'yes' if signals['long_term_reversal'] else 'no'}")
    L.append("")

    if segments_summary:
        L.append("## Segments")
        L.append("")
        L.append("| Segment | Effect | p-value | Significant |")
        L.append("|---|---|---|---|")
        for seg, info in segments_summary.items():
            eff_str = f"{info['effect']:+.1%}" if info["effect"] is not None else "—"
            L.append(f"| {seg} | {eff_str} | {info['p_value']} | {'yes' if info['significant'] else 'no'} |")
        L.append("")

    L.append("## Confidence")
    L.append("")
    L.append(f"Score: {conf_explain['score']} → sigmoid → **{confidence:.4f}**")
    L.append("")
    if conf_explain["factors"]:
        L.append("| Factor | Weight |")
        L.append("|---|---|")
        for f in conf_explain["factors"]:
            L.append(f"| {f['name']} | {f['weight']:+.1f} |")
        L.append("")
    if conf_explain.get("missing_evidence"):
        L.append(f"Missing evidence: {', '.join(conf_explain['missing_evidence'])}")
        L.append("")

    md_path = out_dir / "decision.md"
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")

    emit(trace_path, run_id=run_id, case_id=case_id, agent=AGENT,
         step="done", event="decision_made",
         message=f"{decision} (confidence={confidence:.2f}, {', '.join(reasons)})",
         payload={
             "decision": decision,
             "confidence": confidence,
             "reasons": reasons,
             "policy_id": policy.get("policy_id", ""),
             "policy_version": policy.get("policy_version", ""),
         })

    return result
