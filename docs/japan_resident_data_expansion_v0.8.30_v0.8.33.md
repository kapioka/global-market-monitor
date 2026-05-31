# v0.8.30-v0.8.33 Japan Resident Data Expansion Fast Track

## Purpose

This fast track adds a display-only Japan-resident data foundation for future
multi-asset comparison. It does not introduce a new buy score, does not change
`final_action`, and does not feed into `buy_readiness_score`.

## Covered Data Groups

The inventory covers these future evaluation axes:

- Domestic JPY bonds: government, short, intermediate, and long duration.
- JGB yield curve: 2y, 5y, 10y, 20y, and 30y style fields.
- FX context: USD/JPY and JPY-strength context.
- Japanese equities: TOPIX, Nikkei, and broad Japan equity proxies.
- Japan inflation and domestic rates: CPI trend and BOJ-style rate context.
- Japanese REIT: domestic real-estate income context.
- Gold JPY proxy: gold viewed from a JPY resident perspective.
- Foreign bond context: foreign-currency bond data with FX caution.
- Cash / wait: non-market ticker wait-state context.

## Data Contract

The implementation records a data-source contract in
`project/japan_resident_asset_context.py`.

The contract is intentionally adapter-oriented:

- Existing `asset_compare` rows may provide real market metrics.
- Existing `acquisition_log` rows may provide requested/used ticker status.
- Existing `japan_risk.usd_jpy` may provide FX context.
- Optional future `japan_resident_context` may provide JGB, inflation, and
  domestic credit/rate context.
- Missing, failed, unavailable, partial, and sample-fallback inputs are gated
  conservatively.

The contract explicitly avoids committing raw price series, report history,
cache directories, generated reports, release archives, API responses, or local
paths.

## Display-Only Context Score

The Japan-resident context signal is a small display-only score with component
breakdown:

- `data_quality`
- `jpy_relevance`
- `trend`
- `domestic_rate`
- `fx`
- `inflation`
- `credit`
- `market_risk`

The score is not used by:

- `final_action`
- `buy_readiness_score`
- threshold JSON
- reliability policy
- buy window / candidate thresholds
- risk labels

Each row carries explicit non-impact flags:

- `japan_resident_must_not_affect_final_action`
- `japan_resident_must_not_affect_buy_readiness_score`

## Candidate Integration

`build_multi_asset_candidates()` now includes display rows for:

- equity
- gold
- foreign bond
- domestic JPY bond
- Japanese equity
- Japanese REIT
- cash / wait

The new Japan-resident rows are conservative when source data is missing. They
may show `unavailable` or `informational`, but they do not promote a final
decision.

The report multi-asset section displays the Japan-resident context as a compact
supplemental line per candidate when the context fields are present. This makes
the result visible outside the raw data-acquisition table while keeping the
section read-only and display-only.

In `--sample-only`, some Japan-resident series may remain intentionally
unavailable because the sample bundle does not include domestic JGB, domestic
CPI, or Japan REIT time series. Those rows should be shown as `データ不足`,
`未取得`, or `参考表示`. The implementation must not invent values or fetch new
network data to fill those gaps during sample-only runs.

v0.8.34 adds optional config wiring for `EURJPY=X`, `1321.T`, `2510.T`,
`1343.T`, and `1540.T` where the existing ticker acquisition path can handle
them. JGB yield curve, CPI, and BOJ/domestic-rate fields remain adapter-contract
items until an official source parser is designed separately.

## Conservative Gates

The context signal treats these input states conservatively:

- `missing`
- `failed`
- `unavailable`
- `partial`
- `sample_fallback`
- legacy-shaped rows without required status fields

These states remain display-only and do not become watch signals unless a real
source is available.

## Out of Scope

This fast track does not change:

- `final_action`
- threshold JSON
- `reliability_policy`
- `buy_readiness_score`
- buy blocker logic
- buy decision card logic
- buy window / candidate thresholds
- risk label definitions
- CI
- scripts
- dependencies
- generated reports or caches
- release archives
- GitHub Release or push state

## Validation Scope

Local validation is intentionally tiered. Full release validation is deferred
until tag, push, or release preparation.

Light/Medium validation for this fast track focuses on:

- targeted tests for the new context model
- targeted tests for candidate integration
- report rendering smoke through existing report tests
- `git diff --check`
- `ruff` and `black --check` because Python code changed
- `main.py --sample-only` because pipeline candidate inputs changed
