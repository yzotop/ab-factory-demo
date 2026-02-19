# AB Factory Demo

Live demo: https://yzotop.github.io/ab-factory-demo/

A deterministic, stdlib-only agent system for evaluating A/B test decisions.

Four agents (reader → stats → decision → viz) process synthetic A/B test cases
through a policy-driven decision framework with confidence scoring.
No pip dependencies — runs on any machine with Python 3.10+ and bash.

## What's inside

```
40_ab_factory/   Schemas, validation tools, synthetic case output
41_agents/       4 deterministic agents + policy.json + trace protocol
42_workflows/    Orchestrator, run index, timeline, selfcheck
43_generation/   Synthetic case generator (seeded, 5 scenario types)
docs/            GitHub Pages site
tools/           Corpus and replay index builders
```

## Quickstart

```bash
# 1. Generate 100 synthetic cases
./43_generation/ab_factory/run.sh --n 100

# 2. Run agents on all synthetic cases
cd 42_workflows/ab_factory
python3 run_case.py --all --root ../../40_ab_factory/vk-style/cases_auto

# 3. Verify 100% accuracy
python3 selfcheck.py --auto

# 4. Build public corpus index
cd ../..
python3 tools/build_corpus_index.py

# 5. Build case replays (agent timelines + artifacts)
python3 tools/build_replays_index.py

# 6. Preview locally
cd docs && python3 -m http.server 8000
```

### Generate at scale

```bash
# 300 cases
./43_generation/ab_factory/run.sh --n 300

# Custom seed for different distributions
./43_generation/ab_factory/run.sh --n 100 --seed 123
```

## Case distribution (synthetic)

| Scenario | Share | Expected decision |
|---|---|---|
| Clean uplift | 30% | ship |
| Guardrail breach | 20% | do_not_ship |
| Practically small effect | 20% | do_not_ship |
| Segment conflict | 15% | investigate |
| Long-term reversal | 15% | do_not_ship |

## Decision + Confidence

Each case produces a `decision.json` with:
- **decision**: ship / do_not_ship / investigate
- **confidence**: sigmoid-based score (0.01–0.99)
- **reasons**: machine-readable tags
- **signals**: primary uplift, p-value, guardrails, segments, reversal
- **policy reference**: version-tracked organizational policy

## Run artifacts

Each run creates `runs/<run_id>/`:
- `final_report.md` — assembled decision + reader + stats + viz
- `decision.json` — structured output with confidence
- `traces.jsonl` — full agent trace log
- `timeline.md` — grouped agent timeline

Global `runs/index.jsonl` — append-only decision log across all runs.

## GitHub Pages site

The `docs/` folder contains a static site for GitHub Pages.

To enable Pages: **repo Settings → Pages → Source: Deploy from branch → Branch: main, folder: /docs**.

Pages include:
- **Landing** — hero + feature cards
- **Corpus Explorer** — browse 100 synthetic cases with filtering, sorting, per-case charts, and agent replay viewer
- **Decision Engine** — interactive stop-rule pipeline walkthrough on any corpus case
- **Trace Viewer** — swim-lane timeline of the agent pipeline per case

### Rebuild public data

```bash
python3 tools/build_corpus_index.py
python3 tools/build_replays_index.py
cd docs && python3 -m http.server 8000
```

## Requirements

- macOS / Linux
- Python 3.10+
- bash
- No pip dependencies

## License

Internal demo — not for redistribution.
