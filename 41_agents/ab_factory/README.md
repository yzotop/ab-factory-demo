# AB Factory — Agents

Deterministic agents that analyse synthetic A/B test cases from `40_ab_factory/vk-style/`.
No external dependencies — pure Python 3.10+ stdlib.

## Agent inventory

| Agent | Input | Output artifact | What it does |
|---|---|---|---|
| `reader_agent` | contract.json, truth.json, data.csv | `reader_summary.md` | Headline facts extraction |
| `stats_agent` | data.csv, contract.json | `stats_checks.md` | Sanity checks on data |
| `decision_agent` | contract.json, data.csv | `decision.json`, `decision.md` | Apply decision framework |
| `viz_agent` | contract.json, data.csv | `viz.md` | Metric comparison tables |

## Interface

Every agent exposes a single function:

```python
def run(case_dir: Path, out_dir: Path, trace_path: Path, run_id: str) -> dict
```

- `case_dir` — path to a case folder (contains contract.json, data.csv, etc.)
- `out_dir` — path to `runs/<run_id>/artifacts/`
- `trace_path` — path to `runs/<run_id>/traces.jsonl`
- `run_id` — unique run identifier
- Returns a dict with agent-specific results

## Traces

Each agent emits JSONL trace events via `trace.emit()`:
- `step=start` at the beginning
- `step=done` + `event=artifact_written` on success
- `step=error` on failure

See `trace_schema.json` for the full event schema.
