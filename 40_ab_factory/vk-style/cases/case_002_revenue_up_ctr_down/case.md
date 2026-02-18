# Case 002 — Aggressive ad pressure: revenue up, CTR guardrail violated

## Context

The team increased ad frequency in the article scroll placement by 30%: one additional
ad slot injected every 3 screens instead of every 4. The goal was to capture incremental
impressions and raise revenue.

## What changed

- **Test group**: ad frequency = 1 slot per 3 screens (was 1 per 4).
- **Control group**: unchanged (1 per 4 screens).
- Duration: 14 days, ~511K users per arm.

## Observed results

| Metric | Control | Test | Δ relative | p-value |
|---|---|---|---|---|
| Revenue (RUB/day) | 2,840,000 | 2,876,920 | **+1.3%** | 0.020 |
| CPM | 142.00 | 143.85 | +1.3% | — |
| CTR | 5.20% | 4.99% | **−4.0%** | 0.010 |
| Fill rate | 78.1% | 78.4% | +0.4% | — |

## Decision question

Revenue is up and statistically significant. However, CTR dropped 4.0% — past the
guardrail threshold of 3%. More impressions at lower quality may erode advertiser trust.
Should we ship, iterate with a smaller pressure increase, or reject?
