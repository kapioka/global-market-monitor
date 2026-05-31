# v0.8.37-v0.8.38 Official Japan Macro Adapters

## Purpose

This note records the optional official Japan macro adapter contract for the
Japan-resident multi-asset context. The adapters are display-only inputs. They
must not affect `final_action`, equity `buy_readiness_score`, threshold JSON,
reliability policy, buy blockers, or buy decision card logic.

## Adapter contracts

### JGB yield curve

Source class: Ministry of Finance Japan JGB yield curve.

Supported fields:

- `jgb_2y`
- `jgb_5y`
- `jgb_10y`
- `jgb_20y`
- `jgb_30y`
- `jgb_curve_10y_2y`
- `jgb_curve_30y_10y`

The parser accepts compact CSV-style fixture data and normalizes dates and
numeric percent values. Missing maturities produce `partial` rather than fake
values.

### Japan CPI / core CPI

Source class: Statistics Bureau of Japan CPI.

Supported fields:

- `jp_cpi_yoy`
- `jp_core_cpi_yoy`
- `jp_cpi_trend`

The trend label is conservative: `high` for elevated YoY inflation, `rising`
when core CPI YoY rises versus the previous row, `falling` when it declines,
and `stable` otherwise.

### BOJ / domestic short-rate context

Source class: Bank of Japan official/statistical short-rate context.

Supported fields:

- `boj_policy_rate`
- `boj_call_rate`
- `domestic_rate_context`

The domestic-rate context is display-only. Rising or high short-rate context can
add caution to domestic bonds and Japan REIT rows, while supporting the cash/wait
context. Missing data gives no boost.

## Safe dry-run behavior

`python project\main.py --japan-macro-dry-run`

The default dry-run is contract-only and does not perform live official fetches.
It returns structured `unavailable` macro source entries so the report pipeline
can keep safe fallback behavior.

`python project\main.py --japan-macro-dry-run --japan-macro-live-once`

This optional mode attempts each configured official source once. It is not a CI
requirement and should not be retried repeatedly if a source fails or returns a
non-CSV landing page. Failures remain structured as `failed` and are not shown
as raw parser errors in beginner-facing output.

## Integration

The pipeline now attaches an optional Japan macro context to
`multi_asset_candidates`:

- `jgb_yields`
- `inflation`
- `domestic_rates`
- `macro_sources`

The Japan-resident context consumes these fields only for display components:

- `domestic_rate`
- `inflation`
- `data_quality`
- `jpy_relevance`

The candidate payload continues to expose:

- `affects_final_action: false`
- `affects_buy_readiness_score: false`
- per-row `japan_resident_must_not_affect_final_action: true`
- per-row `japan_resident_must_not_affect_buy_readiness_score: true`

## Missing data behavior

Official macro data is optional.

- Missing JGB data gives no boost.
- Missing CPI data gives no boost.
- Missing BOJ/call-rate data gives no boost.
- Failed or partial official adapters stay unavailable or informational.
- No official macro result creates a strong candidate by itself.

Safe report wording should stay in the existing caution style:

- 国内金利データは未取得です
- 国内インフレデータは未取得です
- 公式統計データは確認できませんでした
- 参考表示

## Validation notes

Fixture-backed parser tests cover:

- JGB yield curve fields and curve spreads
- CPI/core CPI and trend labels
- BOJ/call-rate context
- failed parser status
- context mapping into Japan-resident display inputs
- contract-only dry-run behavior

Live official fetch is intentionally optional because official pages may expose
HTML, Excel, or changing CSV schemas. If live parsing needs a larger design, it
should be handled in a separate Goal.
