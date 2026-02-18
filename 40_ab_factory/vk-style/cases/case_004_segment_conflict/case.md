# Case 004 — Fullscreen ad format: segment conflict (news vs dzen)

## Context

A fullscreen interstitial ad was introduced before article content loads. The format
was deployed uniformly across news and dzen surfaces. Prior research suggested
news users have higher ad tolerance than dzen users.

## What changed

- **Test group**: fullscreen interstitial shown once per session before first article.
- **Control group**: no interstitial.
- Duration: 14 days, ~500K users per arm, split across news (~310K) and dzen (~190K).

## Observed results

### Overall

| Metric | Control | Test | Δ relative | p-value |
|---|---|---|---|---|
| Revenue | 3,000,000 | 3,015,000 | +0.5% | 0.200 |
| CTR | 4.70% | 4.65% | −1.1% | 0.35 |

### By segment

| Segment | Revenue Δ | p-value | CTR Δ | p-value |
|---|---|---|---|---|
| **news** | **+3.0%** | 0.010 | −1.0% | 0.40 |
| **dzen** | **−2.0%** | 0.020 | −1.7% | 0.28 |

## Decision question

The overall effect is not significant (+0.5%, p=0.20). But segments diverge sharply:
news benefits while dzen is harmed. Shipping universally would hurt dzen.
Should we ship for news only, iterate, or investigate further?
