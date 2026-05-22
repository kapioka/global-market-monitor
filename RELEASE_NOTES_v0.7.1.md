# Release Notes v0.7.1

## Added

- benchmark price JSON support
- benchmark_return / excess_return calculation
- risk line trigger_path
- threshold replay trigger_path_diff
- threshold replay runtime diagnostics and timeout JSON
- proposed threshold dirty prevention
- action layers:
  - market_raw_action
  - risk_adjusted_action
  - final_action
- buy_candidate action label
- buy_window diagnostics
- buy_window case study
- FX downgrade diagnostics
- buy_candidate near-miss diagnostics
- fx_soft_cap diagnostic action
- fx_soft_cap watchlist
- historical price backfill
- historical feature builder
- fx_soft_cap historical replay
- conditional fx_soft_cap replay
- DD guard analysis
- missed_good analysis
- long-range guard replay
- market_regime_classifier
- regime-aware FX policy replay

## Changed

- Improved threshold_historical_replay runtime behavior.
- Normal and sample runs no longer dirty `risk_line_thresholds_proposed.json`.
- Generated proposed threshold snapshots are kept in reports/cache outputs, not active threshold files.
- Reports now include concise diagnostics for:
  - まず見る要約
  - Buy Window Diagnostics
  - FX diagnostics
  - Regime-aware FX diagnostics

## Decision

- fx_soft_cap remains diagnostic_only / hold.
- conditional fx_soft_cap remains hold.
- DD guard remains hold.
- regime-aware FX candidates remain hold.
- No diagnostic candidate affects final_action.
- final_action remains based on active thresholds and reliability_policy.
- TimesFM was evaluated but not included in v0.7.1 because signal quality was not useful and false supportive risk was too high.

## Known Limitations

- FX soft-cap candidates still lack enough 13w/26w excess return improvement for adoption.
- Some candidates break in 2022-style rate shock regimes.
- Historical backfill depends on yfinance data availability and ticker history.
- buy_candidate is not a buy instruction.
- Generated reports/cache are not source-controlled.
