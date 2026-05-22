# How to read buy decision outputs

## Buy Decision Card

The Buy Decision Card is the first-pass summary for buy-decision clarity.

- `final_action` is the official action.
- `market_raw_action` is the market-only signal.
- `risk_adjusted_action` includes market risk and blocker effects.
- `buy_readiness_score` explains closeness to a candidate zone.
- `primary_blocker` explains why the action is not stronger.
- `unlock_conditions` explain what to watch next.

## Important limits

`buy_readiness_score` is explanatory only.

`unlock_conditions` are not automatic buy conditions.

`buy_candidate` is not a buy instruction.

`fx_soft_cap`, DD guards, and regime-aware FX policies remain diagnostic-only / hold unless explicitly adopted in a future release.
