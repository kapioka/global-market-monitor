# v0.8.18-v0.8.21 Multi-Asset Candidate Fast Track

## Purpose

This fast track adds a display-only foundation for asset-class candidate review. The report can now show equities, gold, bonds, and cash wait as separate roles instead of treating every asset as the same kind of buy candidate.

## Why gold and bonds are not mixed into buy readiness

`buy_readiness_score` explains how many existing buy-decision conditions are aligned for the current market decision. Gold and bonds can serve different roles from equities:

- Equities: growth exposure candidate.
- Gold: defensive or diversification candidate during unstable markets.
- Bonds: rate-sensitive or risk-off confirmation candidate.
- Cash wait: a valid option while conditions are incomplete.

Mixing these into one score would imply a common readiness scale across assets with different risk drivers. This release keeps the new section explanatory and does not affect `final_action`, thresholds, reliability policy, or buy readiness calculation.

## Existing data inventory

Configured asset-class tickers include:

- Equities: `SPY`, `ACWI`.
- Gold: `GLD`; inflation monitor can also expose `GC=F`.
- Bonds: `AGG`, `TIP`; credit monitor can expose `HYG` and `LQD`.
- Cash wait: synthetic display row, no market ticker required.

The runtime candidate builder also reads the existing acquisition log. When a ticker is unavailable, the report still renders the row with `source_data_available=false` instead of failing report generation.

## Display policy

The report section is titled `資産クラス別の確認候補` and shows:

- asset class label
- symbol
- display name
- role
- status
- source data availability
- reason
- caution

The section is display-only. It carries explicit flags:

- `affects_final_action: False`
- `affects_buy_readiness_score: False`

## Non-advice wording

The report includes this caution:

> これは買い推奨ではなく、現在の市場状態を資産クラス別に整理したものです。外貨建て資産は為替の影響を受けます。

The implementation avoids advice-like phrases such as:

- 買うべき
- 今が買い
- 安全
- 利益が出る
- 確実
- 推奨銘柄

## Tests added

The regression tests cover:

- generation of four asset classes
- gold and bonds staying outside the equity growth role
- missing candidate data still producing a valid display payload
- no forbidden advice phrases in the candidate payload
- markdown and HTML report rendering of the new section
- unchanged displayed `final_action` and `buy_readiness_score` fields during rendering

## Out of scope

This release does not add:

- gold-specific readiness score
- bond-specific readiness score
- final action integration
- threshold JSON changes
- reliability policy changes
- buy window or buy candidate threshold changes
- dependency changes
- CI or script changes
- automated trading or investment advice behavior

## Future design candidates

Future work can evaluate separate, role-specific diagnostics:

- gold defensive confirmation based on dollar, real-rate proxy, inflation monitor, and drawdown regime
- bond confirmation based on rate direction, MOVE, credit spread proxies, and risk-line stage
- cash-wait explanation linked to data reliability, strict missing indicators, and extreme risk-line states

Those should remain separate from equity buy readiness unless a validated cross-asset framework is designed and documented.
