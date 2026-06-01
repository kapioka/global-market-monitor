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

## v0.8.40 live resolver note

The initial live-once path pointed at official information pages for Ministry of
Finance JGB rates, Statistics Bureau CPI, and BOJ statistics. Those URLs are
official references, but they may return HTML landing pages rather than stable
CSV/text datasets. v0.8.40 keeps the one-request-per-source behavior and adds
source-specific response classification before parser execution:

- `landing_page`: official URL returned HTML instead of data
- `unsupported_format`: official URL returned a non-CSV/text content type
- `empty_response`: official URL returned no body
- `network_error` / `timeout` / `source_unavailable`: transport-level issue
- `missing_required_fields` / `parse_error`: data-like response could not be parsed

This is an improvement over raw CSV tokenizer failures. The result remains
non-blocking and safe for display-only context. Stable downloadable endpoints can
be added later without changing the fallback contract.

## v0.8.41 endpoint discovery and fallback registry

v0.8.41 adds a two-level live source strategy:

1. Use a stable first-party machine-readable endpoint only when the format is
   small enough to parse robustly.
2. Otherwise keep the official page as a fallback source registry entry and
   return non-data structured status.

### MOF JGB yield curve

The Ministry of Finance exposes a first-party historical CSV endpoint:

- `https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv`

The parser now accepts the MOF title row plus the `Date,1Y,2Y,...,40Y` header
shape. It extracts:

- `jgb_2y`
- `jgb_5y`
- `jgb_10y`
- `jgb_20y`
- `jgb_30y`
- `jgb_curve_10y_2y`
- `jgb_curve_30y_10y`

If the endpoint returns a landing page or non-data response, the result becomes
a source registry entry instead of a parser failure.

### Japan CPI

The Statistics Bureau CPI page exposes downloadable files, and e-Stat can be a
future API source. v0.8.41 does not hard-code an e-Stat appId or stats table
mapping.

- If `ESTAT_APP_ID` is missing, the adapter returns `missing_credentials` and
  does not attempt an e-Stat network request.
- If `ESTAT_APP_ID` is present, the adapter still returns
  `endpoint_not_resolved` until a stable CPI table mapping is explicitly
  selected and tested.
- The Statistics Bureau landing page remains a fallback official source
  reference.

No credential value is logged or included in payloads.

### BOJ short-rate context

BOJ publishes short-rate pages, Time-Series Data Search links, and current XLSX
release files for call money market data. v0.8.41 does not scrape visual pages
or parse changing release spreadsheets. Until a stable no-credential CSV/API
series endpoint or BOJ series code is selected, the BOJ source returns
`endpoint_not_resolved`.

### Fallback registry contract

Fallback entries are source references only. They have no real macro value:

- `value: null`
- `observations: {}`
- `metadata.safe_for_context: false`
- `source_type: official_landing_page` or equivalent
- `error_category: landing_page_reference`, `endpoint_not_resolved`, or
  `missing_credentials`
- `human_action` describing what manual discovery is still required

`build_japan_macro_context` only promotes `ok` or `partial` parser results into
`jgb_yields`, `inflation`, or `domestic_rates`. Fallback registry entries remain
inside `macro_sources` and give no score boost.

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
