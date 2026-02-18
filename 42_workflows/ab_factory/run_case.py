#!/usr/bin/env python3
"""
AB Factory — Workflow orchestrator.

Runs reader → stats → decision → viz agents on one or all cases,
producing artifacts and JSONL traces per run.

Usage:
  python3 run_case.py --case 001
  python3 run_case.py --case case_004_segment_conflict
  python3 run_case.py --all
  python3 run_case.py --all --keep-runs 5
  python3 run_case.py --all --policy /path/to/policy.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AI_LAB = SCRIPT_DIR.parent.parent
AGENTS_DIR = AI_LAB / "41_agents" / "ab_factory"
RUNS_DIR = SCRIPT_DIR / "runs"

sys.path.insert(0, str(AGENTS_DIR))

import reader_agent  # noqa: E402
import stats_agent   # noqa: E402
import decision_agent  # noqa: E402
import viz_agent  # noqa: E402
from trace import emit  # noqa: E402

AGENTS = [
    ("reader", reader_agent),
    ("stats", stats_agent),
    ("decision", decision_agent),
    ("viz", viz_agent),
]


def discover_cases(root: Path) -> list[Path]:
    """Find case dirs. Supports root/cases/ layout or root/ directly containing case_* dirs."""
    cases_dir = root / "cases"
    if cases_dir.exists() and cases_dir.is_dir():
        search = cases_dir
    elif any(d.is_dir() and (d / "contract.json").exists() for d in root.iterdir()):
        search = root
    else:
        return []
    return sorted(
        d for d in search.iterdir()
        if d.is_dir() and (d / "contract.json").exists()
    )


def resolve_case(root: Path, spec: str) -> Path | None:
    cases = discover_cases(root)
    for c in cases:
        if c.name == spec:
            return c
        if spec.isdigit() and f"case_{spec.zfill(3)}" in c.name:
            return c
        if spec.startswith("case_") and c.name.startswith(spec):
            return c
    return None


def make_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rnd = f"{random.randint(0, 0xFFFF):04x}"
    return f"{ts}_{rnd}"


def assemble_report(artifacts_dir: Path, case_id: str, policy_ref: str = "") -> str:
    L: list[str] = []
    L.append(f"# Final Report — {case_id}")
    if policy_ref:
        L.append(f"\n> Policy: {policy_ref}")
    L.append("")

    for fname in ["decision.md", "reader_summary.md", "stats_checks.md", "viz.md"]:
        p = artifacts_dir / fname
        if p.exists():
            content = p.read_text(encoding="utf-8").strip()
            L.append(content)
            L.append("")
            L.append("---")
            L.append("")

    return "\n".join(L)


def _build_timeline(trace_path: Path, run_dir: Path) -> None:
    """Read traces.jsonl and produce a grouped timeline.md."""
    if not trace_path.exists():
        return
    events: list[dict] = []
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not events:
        return

    events.sort(key=lambda e: e.get("ts", ""))
    first_ts = events[0].get("ts", "")
    last_ts = events[-1].get("ts", "")

    by_agent: dict[str, list[dict]] = {}
    for ev in events:
        a = ev.get("agent", "unknown")
        by_agent.setdefault(a, []).append(ev)

    L: list[str] = []
    L.append("# Timeline")
    L.append("")

    agent_order = ["workflow", "reader", "stats", "decision", "viz"]
    for agent in agent_order:
        if agent not in by_agent:
            continue
        aevents = by_agent[agent]
        L.append(f"## {agent}")
        L.append("")
        for ev in aevents:
            step = ev.get("step", "")
            event = ev.get("event", "")
            msg = ev.get("message", "")
            ts = ev.get("ts", "")[-12:]
            L.append(f"- **{step}** ({event}) — {msg}  `{ts}`")
        if len(aevents) >= 2:
            t0 = aevents[0].get("ts", "")
            t1 = aevents[-1].get("ts", "")
            try:
                from datetime import datetime as _dt
                d0 = _dt.fromisoformat(t0.replace("Z", "+00:00"))
                d1 = _dt.fromisoformat(t1.replace("Z", "+00:00"))
                ms = int((d1 - d0).total_seconds() * 1000)
                L.append(f"- *duration: {ms}ms*")
            except Exception:
                pass
        L.append("")

    if first_ts and last_ts:
        try:
            from datetime import datetime as _dt
            d0 = _dt.fromisoformat(first_ts.replace("Z", "+00:00"))
            d1 = _dt.fromisoformat(last_ts.replace("Z", "+00:00"))
            total_ms = int((d1 - d0).total_seconds() * 1000)
            L.append(f"**Total duration: {total_ms}ms**")
        except Exception:
            pass
    L.append("")

    with open(run_dir / "timeline.md", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def _append_index(run_id: str, case_id: str, decision: str,
                  reasons: list[str], duration_ms: int,
                  confidence: float | None = None,
                  policy_version: str = "") -> None:
    """Append a line to the global runs/index.jsonl."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    index_path = RUNS_DIR / "index.jsonl"
    record: dict = {
        "run_id": run_id,
        "case_id": case_id,
        "decision": decision,
        "reasons": reasons,
        "duration_ms": duration_ms,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    if confidence is not None:
        record["confidence"] = confidence
    if policy_version:
        record["policy_version"] = policy_version
    with open(index_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_one_case(
    case_dir: Path,
    factory_root: Path,
    run_id: str,
    quiet: bool = False,
    policy_path: Path | None = None,
) -> dict:
    with open(case_dir / "contract.json", "r", encoding="utf-8") as f:
        case_id = json.load(f)["case_id"]

    run_dir = RUNS_DIR / run_id
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "traces.jsonl"

    t_start = time.monotonic()

    emit(trace_path, run_id=run_id, case_id=case_id, agent="workflow",
         step="start", event="workflow_start",
         message=f"Running {case_id} from {case_dir.name}")

    agent_kwargs: dict[str, dict] = {}
    if policy_path:
        agent_kwargs["decision"] = {"policy_path": policy_path}

    results: dict[str, dict] = {}
    for agent_name, agent_mod in AGENTS:
        try:
            extra = agent_kwargs.get(agent_name, {})
            result = agent_mod.run(case_dir, artifacts_dir, trace_path, run_id, **extra)
            results[agent_name] = result
        except Exception as e:
            emit(trace_path, run_id=run_id, case_id=case_id, agent=agent_name,
                 step="error", event="workflow_error", severity="error",
                 message=str(e))
            raise

    decision_result = results.get("decision", {})
    decision = decision_result.get("decision", "?")
    reasons = decision_result.get("reasons", [])
    confidence = decision_result.get("confidence")
    policy_info = decision_result.get("policy", {})
    policy_ref = (f"{policy_info.get('policy_id', '')} "
                  f"v{policy_info.get('policy_version', '')}").strip()

    report_text = assemble_report(artifacts_dir, case_id, policy_ref)
    report_path = run_dir / "final_report.md"
    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report_text)

    emit(trace_path, run_id=run_id, case_id=case_id, agent="workflow",
         step="done", event="workflow_done",
         message=f"decision={decision}",
         payload={"decision": decision, "reasons": reasons,
                  "confidence": confidence})

    duration_ms = int((time.monotonic() - t_start) * 1000)

    _build_timeline(trace_path, run_dir)
    _append_index(run_id, case_id, decision, reasons, duration_ms,
                  confidence=confidence,
                  policy_version=policy_info.get("policy_version", ""))

    if not quiet:
        conf_str = f"  conf={confidence:.2f}" if confidence is not None else ""
        print(f"  {case_id:<10}  {decision:<15}  [{', '.join(reasons)}]{conf_str}")
        print(f"             report: {report_path}")

    return {
        "case_id": case_id,
        "case_dir": str(case_dir),
        "run_id": run_id,
        "decision": decision,
        "reasons": reasons,
        "confidence": confidence,
        "report_path": str(report_path),
    }


def cleanup_old_runs(keep: int) -> None:
    if not RUNS_DIR.exists():
        return
    run_dirs = sorted(RUNS_DIR.iterdir(), reverse=True)
    for d in run_dirs[keep:]:
        if d.is_dir():
            shutil.rmtree(d)


def main() -> None:
    parser = argparse.ArgumentParser(description="AB Factory workflow runner")
    parser.add_argument("--root", type=str, default=None,
                        help="Path to factory root (default: 40_ab_factory/vk-style)")
    parser.add_argument("--case", type=str, default=None,
                        help="Case name or number (e.g. 001 or case_004_segment_conflict)")
    parser.add_argument("--all", action="store_true", help="Run all cases")
    parser.add_argument("--keep-runs", type=int, default=None,
                        help="Keep only N most recent runs")
    parser.add_argument("--policy", type=str, default=None,
                        help="Path to policy.json (default: 41_agents/ab_factory/policy.json)")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    args = parser.parse_args()

    root = Path(args.root) if args.root else AI_LAB / "40_ab_factory" / "vk-style"
    if not root.exists():
        print(f"ERROR: factory root not found: {root}", file=sys.stderr)
        sys.exit(1)

    policy_path: Path | None = None
    if args.policy:
        policy_path = Path(args.policy).resolve()
    else:
        default_policy = AGENTS_DIR / "policy.json"
        if default_policy.exists():
            policy_path = default_policy

    if args.keep_runs is not None:
        cleanup_old_runs(args.keep_runs)

    if args.all:
        cases = discover_cases(root)
        if not cases:
            print("No cases found.")
            sys.exit(1)
        print(f"Running {len(cases)} cases...")
        print()
        print(f"  {'case_id':<10}  {'decision':<15}  reasons")
        print(f"  {'-'*9:<10}  {'-'*14:<15}  {'-'*40}")
        t0 = time.monotonic()
        all_results: list[dict] = []
        for case_dir in cases:
            run_id = make_run_id()
            result = run_one_case(case_dir, root, run_id,
                                  quiet=args.quiet, policy_path=policy_path)
            all_results.append(result)
        elapsed = time.monotonic() - t0
        print()
        print(f"Done. {len(cases)} cases in {elapsed:.2f}s. Runs: {RUNS_DIR}")
    elif args.case:
        case_dir = resolve_case(root, args.case)
        if not case_dir:
            print(f"ERROR: case not found: {args.case}", file=sys.stderr)
            sys.exit(1)
        run_id = make_run_id()
        print(f"Running {case_dir.name} (run_id={run_id})...")
        print()
        run_one_case(case_dir, root, run_id, quiet=args.quiet, policy_path=policy_path)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
