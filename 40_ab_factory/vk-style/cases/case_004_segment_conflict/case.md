# Case 004 — Fullscreen ad format: segment conflict (editorial vs algorithmic)

## Context

A fullscreen interstitial ad was introduced before article content loads. The format
was deployed uniformly across editorial and algorithmic surfaces. Prior research suggested
editorial users have higher ad tolerance than algorithmic users.

## What changed

- **Test group**: fullscreen interstitial shown once per session before first article.
- **Control group**: no interstitial.
- Duration: 14 days, ~500K users per arm, split across editorial (~310K) and algorithmic (~190K).

## Observed results

### Overall

| Metric | Control | Test | Δ relative | p-value |
|---|---|---|---|---|
| Revenue | 3,000,000 | 3,015,000 | +0.5% | 0.200 |
| CTR | 4.70% | 4.65% | −1.1% | 0.35 |

### By segment

| Segment | Revenue Δ | p-value | CTR Δ | p-value |
|---|---|---|---|---|
| **editorial** | **+3.0%** | 0.010 | −1.0% | 0.40 |
| **algorithmic** | **−2.0%** | 0.020 | −1.7% | 0.28 |

## Decision question

The overall effect is not significant (+0.5%, p=0.20). But segments diverge sharply:
editorial benefits while algorithmic is harmed. Shipping universally would hurt algorithmic.
Should we ship for editorial only, iterate, or investigate further?
