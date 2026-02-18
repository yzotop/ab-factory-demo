# AB Factory — VK-Style Synthetic Cases

Deterministic, reproducible A/B test cases for evaluating analyst agents.
Each case is a self-contained folder with a contract, data, narrative, and ground truth.

## Structure

```
40_ab_factory/vk-style/
├── schema/
│   ├── contract.schema.json   # JSON Schema for contract.json
│   ├── truth.schema.json      # JSON Schema for truth.json
│   └── data.schema.md         # CSV column spec
├── cases/
│   ├── case_001_revenue_uplift/
│   │   ├── contract.json      # What the agent gets as input
│   │   ├── case.md            # Human-readable story
│   │   ├── data.csv           # Aggregated metrics
│   │   └── truth.json         # Expected decision + rationale
│   ├── case_002_revenue_up_ctr_down/
│   ├── case_003_stat_sig_no_practical/
│   ├── case_004_segment_conflict/
│   └── case_005_long_term_reversal/
├── tools/
│   ├── validate_cases.py      # Structural validation
│   └── summarize_cases.py     # Quick table of all cases
├── run.sh                     # Validate + summarize
└── README.md
```

## Golden set (5 cases)

| Case | Scenario | Decision | Why |
|---|---|---|---|
| 001 | Clean revenue uplift | **ship** | +2.1%, p=0.01, guardrails ok |
| 002 | Revenue up, CTR down | **do_not_ship** | CTR −4% breaches 3% guardrail |
| 003 | Stat sig, practically tiny | **do_not_ship** | +0.3% < 0.5% practical threshold |
| 004 | Segment conflict | **investigate** | news +3% vs dzen −2%, Simpson's paradox |
| 005 | Long-term reversal | **do_not_ship** | Week 1–2 +2%, week 3–4 −1.5% |

## Contract v1 fields

Each `contract.json` contains:

- `case_id` — unique identifier (e.g. `case_001`)
- `title` — short description
- `domain` — always `ads_monetization` for now
- `unit` — randomization unit (`user` or `request`)
- `variants` — list of variant names
- `segments` — optional segment list
- `time` — `start_date`, `end_date`, `horizon_days`
- `primary_metric` — `name`, `direction`, `mde_relative`
- `guardrails` — list of `{name, direction, max_drop_relative}`
- `stats` — `method`, `alpha`, `power_target`
- `decision_framework` — `rule`, `practical_threshold_relative`
- `notes` — free text

## How to run

```bash
cd ~/projects/ai-lab/40_ab_factory/vk-style
./run.sh
```

This validates all cases and prints a summary table.

## Adding a new case

1. Create a folder: `cases/case_NNN_short_name/`
2. Add four files: `contract.json`, `truth.json`, `data.csv`, `case.md`
3. Follow the schemas in `schema/`
4. Run `./run.sh` to validate

## For agents

An agent receives `contract.json` + `data.csv` (and optionally `case.md`) as input.
It must produce a decision: `ship`, `do_not_ship`, `iterate`, or `investigate`.
Evaluate against `truth.json`.

## Dependencies

Python 3.10+ standard library only. No pip installs needed.
