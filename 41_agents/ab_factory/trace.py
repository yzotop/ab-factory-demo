"""Trace utility — emit structured JSONL events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def emit(
    trace_path: str | Path,
    *,
    run_id: str,
    case_id: str,
    agent: str,
    step: str,
    event: str,
    severity: str = "info",
    message: str = "",
    payload: dict | None = None,
) -> None:
    record = {
        "run_id": run_id,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "case_id": case_id,
        "agent": agent,
        "step": step,
        "event": event,
        "severity": severity,
        "message": message,
        "payload": payload or {},
    }
    with open(trace_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
