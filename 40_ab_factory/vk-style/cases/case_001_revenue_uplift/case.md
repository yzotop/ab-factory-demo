# Case 001 — AutoCPM bid floor: clean revenue uplift

## Context

The ads monetization team raised the AutoCPM bid floor by 15% for all ad placements
across news and dzen feeds. The hypothesis: a higher floor filters out low-value bids,
increasing average CPM and total revenue without harming user engagement.

## What changed

- **Test group**: bid floor = 1.15 × baseline.
- **Control group**: unchanged bid floor.
- Duration: 14 days, 50/50 traffic split (~525K users per arm).

## Observed results

| Metric | Control | Test | Δ relative | p-value |
|---|---|---|---|---|
| Revenue (RUB/day) | 3,120,000 | 3,185,520 | **+2.1%** | 0.010 |
| CPM | 152.40 | 155.62 | +2.1% | — |
| CTR | 4.51% | 4.48% | −0.7% | 0.42 |
| Fill rate | 82.3% | 82.6% | +0.4% | — |

## Decision question

The primary metric (revenue) shows a statistically significant uplift that exceeds
the practical threshold. No guardrails degraded. Should we ship?
