"""Reader agent — loads case files and extracts headline facts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from trace import emit

AGENT = "reader"


def _load_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_csv(p: Path) -> list[dict]:
    with open(p, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _safe_float(v: str) -> float | None:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def run(case_dir: Path, out_dir: Path, trace_path: Path, run_id: str) -> dict:
    contract = _load_json(case_dir / "contract.json")
    case_id = contract["case_id"]

    emit(trace_path, run_id=run_id, case_id=case_id, agent=AGENT,
         step="start", event="case_loaded", message="Loading case files")

    truth = _load_json(case_dir / "truth.json")
    rows = _load_csv(case_dir / "data.csv")

    pm = contract["primary_metric"]
    time = contract["time"]
    variants = contract["variants"]
    segments = contract.get("segments", [])

    test_all = [r for r in rows if r["variant"] != "control" and r["segment"] == "all"]
    control_all = [r for r in rows if r["variant"] == "control" and r["segment"] == "all"]

    n_users_total = sum(int(r.get("n_users", 0)) for r in rows if r["segment"] == "all")

    effect_col = f"{pm['name']}_effect_relative"
    pval_col = f"{pm['name']}_p_value"
    effect_val = _safe_float(test_all[0].get(effect_col, "")) if test_all else None
    pval = _safe_float(test_all[0].get(pval_col, "")) if test_all else None

    facts = {
        "case_id": case_id,
        "title": contract["title"],
        "primary_metric": pm["name"],
        "direction": pm["direction"],
        "mde_relative": pm["mde_relative"],
        "period": f"{time['start_date']} → {time['end_date']} ({time['horizon_days']}d)",
        "variants": variants,
        "segments": segments if segments else ["(none)"],
        "n_users_total": n_users_total,
        "effect_headline": f"{effect_val:+.1%}" if effect_val is not None else "N/A",
        "p_value": pval,
        "expected_decision": truth["expected_decision"],
    }

    L: list[str] = []
    L.append(f"# Reader Summary — {case_id}")
    L.append("")
    L.append(f"**{contract['title']}**")
    L.append("")
    L.append("| Field | Value |")
    L.append("|---|---|")
    L.append(f"| Primary metric | {pm['name']} ({pm['direction']}) |")
    L.append(f"| MDE | {pm['mde_relative']:.1%} |")
    L.append(f"| Period | {facts['period']} |")
    L.append(f"| Variants | {', '.join(variants)} |")
    L.append(f"| Segments | {', '.join(facts['segments'])} |")
    L.append(f"| Total users | {n_users_total:,} |")
    L.append(f"| Effect (headline) | {facts['effect_headline']} |")
    L.append(f"| p-value | {pval} |")
    L.append(f"| Guardrails | {len(contract['guardrails'])} defined |")
    L.append("")

    out_path = out_dir / "reader_summary.md"
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")

    emit(trace_path, run_id=run_id, case_id=case_id, agent=AGENT,
         step="done", event="artifact_written", message=str(out_path),
         payload={"effect": facts["effect_headline"], "p_value": pval})

    return facts
