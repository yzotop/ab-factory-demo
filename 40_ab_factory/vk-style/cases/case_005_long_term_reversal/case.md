# Case 005 — Pricing floor bump: short-term gain, long-term reversal

## Context

The pricing team raised the global bid floor by 20% to increase average CPM. The experiment
ran for 28 days to capture long-term advertiser behavior, since budget reallocation cycles
typically take 2–3 weeks.

## What changed

- **Test group**: bid floor = 1.20 × baseline.
- **Control group**: unchanged bid floor.
- Duration: 28 days, ~539K users per arm.

## Observed results — aggregated

| Metric | Control | Test | Δ relative | p-value |
|---|---|---|---|---|
| Revenue (RUB/day) | 3,200,000 | 3,206,400 | +0.2% | 0.350 |
| CPM | 168.42 | 168.76 | +0.2% | — |
| CTR | 4.35% | 4.30% | −1.1% | 0.38 |
| Fill rate | 87.0% | 86.2% | −0.9% | — |

## Week-over-week trend (from logs, not in data.csv)

| Period | Revenue Δ (test vs control) | Fill rate Δ |
|---|---|---|
| Week 1 (Jan 6–12) | **+2.3%** | −0.2% |
| Week 2 (Jan 13–19) | **+1.8%** | −0.5% |
| Week 3 (Jan 20–26) | **−0.8%** | −1.4% |
| Week 4 (Jan 27–Feb 2) | **−1.5%** | −2.1% |

## Decision question

The aggregated result is flat (+0.2%, not significant). But the weekly trend shows
a reversal: strong early gains that erode as advertisers adjust budgets downward in
response to the higher floor. Fill rate is trending down. Ship, or recognize the reversal?
