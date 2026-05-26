# v0.8.15 Buy Readiness Score Recalibration

## Purpose

`buy_readiness_score` is an explanatory display score. It does not set
`final_action`, thresholds, risk labels, or investment instructions.

The actual generated report reviewed for this change had:

- `market_raw_action = watch`
- `risk_adjusted_action = watch`
- `final_action = watch`
- `risk_lines.stage_key = normal`
- high data reliability
- `recovery_evidence = building`
- caution-level blocker assessment

The score nevertheless rendered as `1 / 100`.

## Cause Before Recalibration

| Component | Before |
| --- | ---: |
| Base plus watch/normal/high/building positive context | +52 |
| `rates_warning` classified as `rate_shock/high` | -25 |
| `fx_risk/caution` charged a category-fixed penalty | -18 |
| score below buy threshold | -8 |
| Displayed total | 1 |

This represented caution as near-total rejection even though the decision
layers remained `watch`.

## Changed Boundary

- A rate-related warning flag remains in the explanatory `rate_shock` family,
  but is assigned `caution` severity instead of being treated like a true
  high-severity rate shock.
- Stress penalties now reflect blocker severity for `rate_shock`,
  `credit_stress`, `risk_line`, and `fx_risk`.
- `score_shortfall` remains visible as an explanation but uses a small penalty,
  because a below-buy score is already represented by `market_raw_action =
  watch`.
- `data_quality` and `sample_only` continue to cap the explanatory score at
  `10`, even when other context is positive.

## Unchanged Boundary

- No changes to `final_action`, `market_raw_action`, or
  `risk_adjusted_action` logic.
- No threshold JSON, threshold decision, reliability policy, buy-window,
  buy-candidate, or risk-label changes.
- No report layout, CI, script, scanner, or dependency changes.

## Representative Scores

| Scenario | Before | After | Intended interpretation |
| --- | ---: | ---: | --- |
| Watch, normal risk, high reliability, building recovery, caution rate/FX warnings, near threshold | 1 | 31 | Monitor; conditions are incomplete but not rejected |
| Same positive context with only score shortfall | 44 | 49 | Watch; near threshold without major blocker |
| True high rate shock plus high credit stress | low | 0-15 | Strong blockers remain low |
| Sample fallback or hard data-quality cap | low | 0-10 | Data limitations remain low |

## Rate Warning and True Shock

`rates_warning` is a caution signal in the explanatory breakdown. A rate flag
without warning semantics remains high severity. This avoids describing
ordinary caution as a strong shock while retaining strong-stress behavior.

## Score Shortfall

The below-buy-threshold condition is preserved in the explanation. Its score
effect is reduced because the action layer already encodes that the buy
threshold was not reached.

## Remaining Work

The existing beginner-facing wording for blocker labels is unchanged in this
release. Any wording revision should be assessed separately from score
calibration.
