# AB Factory — Casebook

Five golden A/B test cases, each evaluated by a deterministic agent pipeline
with policy-driven decisions and confidence scoring.

---

## Summary

| Case | Title | Decision | Confidence | Key reason |
|---|---|---|---|---|
| 001 | AutoCPM bid floor: clean revenue uplift | **ship** | 0.65 | primary_uplift |
| 002 | Revenue up but CTR down | **do_not_ship** | 0.23 | guardrail_violation |
| 003 | Stat-sig but practically tiny | **do_not_ship** | 0.20 | practically_small |
| 004 | Segment conflict (news vs dzen) | **investigate** | 0.27 | segment_conflict |
| 005 | Long-term trend reversal | **do_not_ship** | 0.04 | long_term_reversal |

---

## Case 001 — Clean Revenue Uplift

**Decision: SHIP** (confidence: 0.65)

AutoCPM bid floor raised by 15% in test group. Revenue lifted +2.1% with
p=0.01, well above the practical threshold of 0.5%. All guardrails (CTR, DAU,
session length) held within acceptable bounds.

- Primary metric: revenue +2.1%
- p-value: 0.01 (significant)
- Guardrails: all OK
- Confidence factors: +1.2 (strong uplift), −0.6 (evidence sparse)

---

## Case 002 — Revenue Up, CTR Down

**Decision: DO NOT SHIP** (confidence: 0.23)

Revenue increased +1.3% (p=0.02), but CTR dropped −4.0% — breaching the
−3.0% hard guardrail. The revenue gain does not justify the engagement loss.

- Primary metric: revenue +1.3%
- Guardrail breach: CTR −4.0% (threshold: −3.0%)
- Confidence factors: +1.2 (uplift), −1.8 (hard guardrail), −0.6 (sparse)

---

## Case 003 — Statistically Significant but Practically Tiny

**Decision: DO NOT SHIP** (confidence: 0.20)

With a very large sample (2M+ users), a +0.3% revenue effect is statistically
significant (p=0.0001) but falls below the 0.5% practical threshold. The effect
is real but too small to warrant the complexity of shipping.

- Primary metric: revenue +0.3%
- Practical threshold: 0.5% (not met)
- Confidence factors: −0.8 (small uplift), −0.6 (sparse)

---

## Case 004 — Segment Conflict

**Decision: INVESTIGATE** (confidence: 0.27)

News segment shows revenue +3.0% (p=0.01), but Dzen segment shows −2.0%
(p=0.02). Overall aggregate is +0.5% (p=0.20, not significant). The conflicting
segment effects require deeper investigation before any rollout decision.

- Segment news: +3.0% (significant)
- Segment dzen: −2.0% (significant)
- Overall: +0.5% (not significant)
- Confidence factors: −0.7 (not sig), −0.9 (conflict), −0.6 (sparse)

---

## Case 005 — Long-Term Reversal

**Decision: DO NOT SHIP** (confidence: 0.04)

Short-term results showed a +2% revenue uplift in weeks 1–2, but a 28-day
holdout revealed a −1.5% reversal in weeks 3–4. The aggregate effect is not
significant. Long-term user behavior patterns negate the initial gains.

- Short-term: +2.0%
- Long-term: −1.5% reversal
- Overall: not significant
- Confidence factors: −0.7 (not sig), −1.0 (reversal), −0.6 (sparse)

---

## Policy

All decisions made under **ab_factory_policy v1.0.0**:
- Significance: α = 0.05
- Practical threshold: 0.5%
- Guardrails: CTR (−3.0%, hard), Retention (−2.0%, hard)
- Segment conflict threshold: 2.0% gap
- Confidence model: linear score → sigmoid
