# AB Factory — Synthetic Case Generator

Generates N deterministic A/B test cases for agent evaluation.
Output follows the same `contract.json` + `truth.json` + `data.csv` schema
as the manual cases in `40_ab_factory/vk-style/cases/`.

## Distribution

| Type | Share | Expected decision |
|---|---|---|
| Clean uplift | 30% | ship |
| Guardrail breach | 20% | do_not_ship |
| Practically small | 20% | do_not_ship |
| Segment conflict | 15% | investigate |
| Long-term reversal | 15% | do_not_ship |

## How it works

Each generator produces a contract, truth, and data.csv that are internally
consistent with the decision agent's logic:

- **Clean uplift**: significant effect above practical threshold, guardrails OK
- **Guardrail breach**: significant revenue gain but CTR drop exceeds max_drop_relative
- **Practically small**: significant effect below practical_threshold_relative
- **Segment conflict**: opposite significant effects across segments
- **Long-term reversal**: non-significant aggregate + "reversal" in contract notes

All randomness is seeded (`--seed 42` default) for reproducibility.

## Usage

```bash
cd ~/projects/ai-lab/43_generation/ab_factory

# Default: 300 cases
./run.sh

# Custom count
./run.sh --n 50

# Custom output directory
./run.sh --n 100 --out /tmp/test_cases
```

Output goes to `40_ab_factory/vk-style/cases_auto/` by default.

## Dependencies

Python 3.10+ standard library only.
