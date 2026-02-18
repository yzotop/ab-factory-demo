"""Viz agent — generate markdown comparison tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from trace import emit

AGENT = "viz"


def _load_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_csv(p: Path) -> list[dict]:
    with open(p, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _fmt(val: str, is_pct: bool = False) -> str:
    try:
        v = float(val)
        if is_pct:
            return f"{v:.2%}"
        if v > 10000:
            return f"{v:,.0f}"
        return f"{v:,.2f}"
    except (ValueError, TypeError):
        return val or "—"


def run(case_dir: Path, out_dir: Path, trace_path: Path, run_id: str) -> dict:
    contract = _load_json(case_dir / "contract.json")
    case_id = contract["case_id"]

    emit(trace_path, run_id=run_id, case_id=case_id, agent=AGENT,
         step="start", event="parsed", message="Building comparison tables")

    rows = _load_csv(case_dir / "data.csv")
    pm_name = contract["primary_metric"]["name"]
    guardrail_names = [g["name"] for g in contract.get("guardrails", [])]

    metrics = [pm_name]
    for g in guardrail_names:
        if g not in metrics and g in rows[0]:
            metrics.append(g)
    for m in ["revenue", "cpm", "fillrate", "ctr", "shows"]:
        if m not in metrics:
            metrics.append(m)

    segments_in_data = sorted({r["segment"] for r in rows})

    L: list[str] = []
    L.append(f"# Metric Comparison — {case_id}")
    L.append("")

    for seg in segments_in_data:
        seg_rows = [r for r in rows if r["segment"] == seg]
        if not seg_rows:
            continue

        label = f"Segment: {seg}" if seg != "all" else "Overall"
        L.append(f"## {label}")
        L.append("")

        header_parts = ["Metric"]
        for r in seg_rows:
            header_parts.append(r["variant"])
        if len(seg_rows) > 1:
            header_parts.append("Δ relative")
            header_parts.append("p-value")
        L.append("| " + " | ".join(header_parts) + " |")
        L.append("|" + "|".join(["---"] * len(header_parts)) + "|")

        control = [r for r in seg_rows if r["variant"] == "control"]
        tests = [r for r in seg_rows if r["variant"] != "control"]

        for metric in metrics:
            if metric not in seg_rows[0]:
                continue
            is_pct = metric in ("fillrate", "ctr")
            row_parts = [f"**{metric}**" if metric == pm_name else metric]
            for r in seg_rows:
                row_parts.append(_fmt(r.get(metric, ""), is_pct))
            if tests:
                eff = tests[0].get(f"{metric}_effect_relative", "")
                pv = tests[0].get(f"{metric}_p_value", "")
                if eff:
                    try:
                        row_parts.append(f"{float(eff):+.1%}")
                    except ValueError:
                        row_parts.append(eff)
                else:
                    row_parts.append("—")
                row_parts.append(pv if pv else "—")
            L.append("| " + " | ".join(row_parts) + " |")

        L.append("")

    out_path = out_dir / "viz.md"
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")

    emit(trace_path, run_id=run_id, case_id=case_id, agent=AGENT,
         step="done", event="artifact_written", message=str(out_path),
         payload={"segments": len(segments_in_data), "metrics": len(metrics)})

    return {"segments": segments_in_data, "metrics": metrics}
