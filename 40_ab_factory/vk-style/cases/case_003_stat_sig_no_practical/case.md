# Case 003 — Lazy-load tweak: stat sig but below practical threshold

## Context

A frontend optimization changed the lazy-load trigger point for ad slots from 200px
to 150px below the viewport. The hypothesis: earlier ad rendering increases viewable
impressions and marginally boosts revenue.

## What changed

- **Test group**: lazy-load trigger at 150px below viewport.
- **Control group**: trigger at 200px (default).
- Duration: 28 days, ~2M users per arm (very high power).

## Observed results

| Metric | Control | Test | Δ relative | p-value |
|---|---|---|---|---|
| Revenue (RUB/day) | 4,500,000 | 4,513,500 | **+0.3%** | 0.0001 |
| CPM | 180.00 | 180.54 | +0.3% | — |
| CTR | 4.12% | 4.11% | −0.2% | 0.78 |
| Fill rate | 85.2% | 85.3% | +0.1% | — |

## Decision question

The effect is statistically significant (p < 0.001) thanks to the large sample,
but at +0.3% it falls below the practical threshold of 0.5%. All guardrails are fine.
Is this worth shipping, or is the effect too small to justify the maintenance cost?
