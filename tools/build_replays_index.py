#!/usr/bin/env python3
"""
Export compact case replays from local workflow runs for GitHub Pages.

Reads:
  42_workflows/ab_factory/runs/index.jsonl
  42_workflows/ab_factory/runs/<run_id>/traces.jsonl
  42_workflows/ab_factory/runs/<run_id>/artifacts/*

Produces:
  docs/data/replays/case_001.json ... case_100.json
  docs/data/replays/index.json

No external dependencies.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
RUNS_DIR = REPO / "42_workflows" / "ab_factory" / "runs"
INDEX_PATH = RUNS_DIR / "index.jsonl"
OUT_DIR = REPO / "docs" / "data" / "replays"

MAX_ARTIFACT_LINES = 120


def _latest_runs() -> dict[str, dict]:
    """Read index.jsonl and return the latest entry per case_id."""
    if not INDEX_PATH.exists():
        return {}
    latest: dict[str, dict] = {}
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = rec.get("case_id", "")
            ts = rec.get("timestamp", "")
            if cid and (cid not in latest or ts > latest[cid].get("timestamp", "")):
                latest[cid] = rec
    return latest


def _load_traces(run_dir: Path) -> list[dict]:
    """Parse traces.jsonl into compact timeline events with relative ms."""
    trace_path = run_dir / "traces.jsonl"
    if not trace_path.exists():
        return []
    events: list[dict] = []
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(ev)

    if not events:
        return []

    events.sort(key=lambda e: e.get("ts", ""))
    t0_str = events[0].get("ts", "")
    try:
        t0 = datetime.fromisoformat(t0_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        t0 = None

    timeline: list[dict] = []
    for ev in events:
        t_ms = 0
        if t0:
            try:
                t = datetime.fromisoformat(ev.get("ts", "").replace("Z", "+00:00"))
                t_ms = max(0, int((t - t0).total_seconds() * 1000))
            except (ValueError, TypeError):
                pass
        msg = ev.get("message", "")
        if len(msg) > 200:
            msg = msg[:200] + "…"
        timeline.append({
            "t_ms": t_ms,
            "agent": ev.get("agent", ""),
            "step": ev.get("step", ""),
            "event_type": ev.get("event", ""),
            "message": msg,
        })
    return timeline


def _read_artifact(path: Path) -> str | None:
    """Read a text artifact, truncated to MAX_ARTIFACT_LINES."""
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    text = "\n".join(lines[:MAX_ARTIFACT_LINES])
    if len(lines) > MAX_ARTIFACT_LINES:
        text += f"\n\n… ({len(lines) - MAX_ARTIFACT_LINES} more lines)"
    return text


def _read_json_artifact(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def build_replays() -> list[dict]:
    if not INDEX_PATH.exists():
        print(
            "ERROR: runs/index.jsonl not found.\n"
            "Run the workflow first:\n"
            "  cd 42_workflows/ab_factory\n"
            "  python3 run_case.py --all --root ../../40_ab_factory/vk-style/cases_auto",
            file=sys.stderr,
        )
        sys.exit(1)

    latest = _latest_runs()
    if not latest:
        print("ERROR: no runs found in index.jsonl.", file=sys.stderr)
        sys.exit(1)

    replays: list[dict] = []
    index_entries: list[dict] = []

    for cid in sorted(latest.keys()):
        rec = latest[cid]
        run_id = rec["run_id"]
        run_dir = RUNS_DIR / run_id

        if not run_dir.exists():
            print(f"  WARN: run dir missing for {cid} ({run_id})", file=sys.stderr)
            continue

        arts = run_dir / "artifacts"
        timeline = _load_traces(run_dir)

        replay: dict = {
            "case_id": cid,
            "run_id": run_id,
            "decision": rec.get("decision", ""),
            "confidence": rec.get("confidence"),
            "reasons": rec.get("reasons", []),
            "policy_version": rec.get("policy_version", ""),
            "duration_ms": rec.get("duration_ms", 0),
            "timeline": timeline,
            "artifacts": {
                "reader_summary": _read_artifact(arts / "reader_summary.md"),
                "stats_checks": _read_artifact(arts / "stats_checks.md"),
                "decision_md": _read_artifact(arts / "decision.md"),
                "viz": _read_artifact(arts / "viz.md"),
                "decision_json": _read_json_artifact(arts / "decision.json"),
            },
        }

        out_path = OUT_DIR / f"{cid}.json"
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(replay, f, ensure_ascii=False, indent=2)
            f.write("\n")

        replays.append(replay)
        index_entries.append({
            "case_id": cid,
            "run_id": run_id,
            "url": f"data/replays/{cid}.json",
        })

    return index_entries


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    index_entries = build_replays()
    with open(OUT_DIR / "index.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(index_entries, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"  docs/data/replays/index.json  {len(index_entries)} entries")
    print(f"  docs/data/replays/case_*.json {len(index_entries)} files")
    total_kb = sum(
        p.stat().st_size for p in OUT_DIR.glob("*.json")
    ) / 1024
    print(f"  total size: {total_kb:.0f} KB")
    print(f"\nDone. Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
