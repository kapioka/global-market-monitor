# Release Notes v0.7.2

## Added

- Buy Decision Card
- `buy_readiness_score`
- `buy_blocker_breakdown`
- next review conditions / `unlock_conditions`
- `buy_decision_audit` JSON / Markdown report

## Changed

- The report now shows the buy-decision path near the top:
  - final action
  - market raw action
  - risk-adjusted action
  - buy readiness score
  - primary blocker
  - next review conditions
- Sample-only and sample fallback contexts now show clearer safety wording.
- `buy_readiness_score` now includes explicit caveats so it is not read as probability, expected return, or investment success rate.
- Next review conditions are described as review items, not automatic buy conditions.
- Documentation now points users to `final_action` as the official action.

## Decision

- `final_action` remains controlled by active thresholds and `reliability_policy`.
- `buy_readiness_score` does not affect `final_action`.
- Next review conditions / `unlock_conditions` do not trigger buy actions.
- `fx_soft_cap` remains diagnostic-only / hold.
- Conditional, DD-guard, and regime-aware FX candidates remain diagnostic-only / hold.
- TimesFM remains excluded from normal functionality.

## Acceptance

- Sample-only/current report shows:
  - `final_action: wait`
  - `buy_readiness_score: 0 / 100`
  - `primary_blocker: data_quality`
  - sample-only safety note
- The 2026-05-07 raw `buy_window` downgrade remains traceable as `buy_window -> watch -> watch` with FX blockers.
- No history case had `final_action in {wait, watch}` with `buy_readiness_score >= 70` during acceptance review.
- `project/reports/buy_decision_audit.md` starts with a concise summary and includes score caveats and next review conditions.

## Known Limitations

- `buy_readiness_score` is explanatory, not probability.
- Buy Decision Card does not provide investment advice.
- `buy_candidate` is not a buy instruction.
- Next review conditions are not automatic buy conditions.
- Historical diagnostics depend on generated reports/cache that are not source-controlled.
