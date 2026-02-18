# data.csv Schema

Each case contains a `data.csv` with aggregated A/B test metrics per variant and segment.

## Columns

| Column | Type | Required | Description |
|---|---|---|---|
| `case_id` | string | yes | Matches contract `case_id` |
| `segment` | string | yes | `"all"` when not segmented; otherwise segment name |
| `variant` | string | yes | One of the contract's `variants` |
| `n_users` | int | yes | Sample size for this variant × segment |
| `revenue` | float | yes | Aggregated revenue (currency units, e.g. RUB/day total) |
| `cpm` | float | yes | Cost per mille impressions |
| `fillrate` | float | yes | Ad fill rate, range 0–1 |
| `ctr` | float | yes | Click-through rate, range 0–1 |
| `shows` | int | yes | Total ad impressions |
| `revenue_effect_relative` | float | no | Relative lift vs control — blank for control rows |
| `revenue_p_value` | float | no | p-value for revenue effect — blank for control rows |
| `ctr_effect_relative` | float | no | Relative lift vs control for CTR |
| `ctr_p_value` | float | no | p-value for CTR effect |

## Rules

- Every case has at least one `segment="all"` pair (control + test).
- Segmented cases additionally have rows for each segment × variant.
- Effect columns are populated only for non-control variants.
- Realistic ranges: CTR 0.03–0.08, fillrate 0.60–0.95, CPM 50–300, revenue 1M–5M.
