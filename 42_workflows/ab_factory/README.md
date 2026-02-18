# AB Factory — Workflows

Orchestrator that runs deterministic agents on synthetic A/B test cases
from `40_ab_factory/vk-style/`.

## Quickstart

```bash
cd ~/projects/ai-lab/42_workflows/ab_factory

# Run all 5 cases
./run.sh

# Verify decisions match ground truth
python3 selfcheck.py
```

## What happens

1. The orchestrator discovers all case folders in `40_ab_factory/vk-style/cases/`
2. For each case, it generates a unique `run_id` and creates `runs/<run_id>/`
3. Four agents execute in sequence: **reader → stats → decision → viz**
4. Each agent writes artifacts to `runs/<run_id>/artifacts/`
5. All trace events are appended to `runs/<run_id>/traces.jsonl`
6. A `final_report.md` assembles all artifacts into one document

## Run directory structure

```
runs/
  20250216_143022_a1b2/
    traces.jsonl          # JSONL trace events
    final_report.md       # Combined report
    artifacts/
      reader_summary.md   # Headline facts
      stats_checks.md     # Sanity check results
      decision.json       # Machine-readable decision
      decision.md         # Human-readable decision
      viz.md              # Comparison tables
```

## Reading traces.jsonl

Each line is a JSON object:

```json
{"run_id":"20250216_143022_a1b2","ts":"2025-02-16T14:30:22.123456Z","case_id":"case_001","agent":"reader","step":"start","event":"case_loaded","severity":"info","message":"Loading case files","payload":{}}
{"run_id":"20250216_143022_a1b2","ts":"2025-02-16T14:30:22.234567Z","case_id":"case_001","agent":"decision","step":"done","event":"decision_made","severity":"info","message":"ship (primary_uplift)","payload":{"decision":"ship","reasons":["primary_uplift"]}}
{"run_id":"20250216_143022_a1b2","ts":"2025-02-16T14:30:22.345678Z","case_id":"case_001","agent":"workflow","step":"done","event":"workflow_done","severity":"info","message":"decision=ship","payload":{"decision":"ship","reasons":["primary_uplift"]}}
```

## CLI options

```bash
# Single case (by number or full name)
python3 run_case.py --case 001
python3 run_case.py --case case_004_segment_conflict

# All cases
python3 run_case.py --all

# Keep only 5 most recent runs
python3 run_case.py --all --keep-runs 5
```

## Adding a 6th case

1. Create a new folder in `40_ab_factory/vk-style/cases/case_006_<name>/`
2. Add `contract.json`, `truth.json`, `data.csv`, `case.md` per the contract spec
3. Run `cd 40_ab_factory/vk-style && ./run.sh` to validate
4. Run `cd 42_workflows/ab_factory && python3 selfcheck.py` to verify

## Dependencies

Python 3.10+ standard library only. No pip installs needed.
