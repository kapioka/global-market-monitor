# v0.8.34 Japan Resident Series Inventory and Config Wiring

## Purpose

This checkpoint inventories the real-data series needed by the Japan-resident
multi-asset context and wires only series that can use the existing ticker
configuration and yfinance/FRED acquisition pattern safely.

No new mandatory network source, official statistics parser, final decision
logic, equity buy-readiness score, threshold JSON, reliability policy, blocker
logic, or card logic is introduced.

## Current Existing Inputs

| Group | Existing input | Status |
| --- | --- | --- |
| FX / USDJPY | `config.tickers.japan.usd_jpy = USDJPY=X` | already available through existing yfinance path and `japan_risk` |
| Japanese equity / TOPIX proxy | `config.tickers.japan.topix_proxy = 1306.T` | already available through existing yfinance path |
| Japanese equity / broad USD ETF | `EWJ` in `global_equities` | already available, but kept separate from TOPIX proxy |
| Foreign bonds | `AGG`, `TIP`, `LQD`, `HYG` | already available as foreign-currency bond context |
| USD gold | `GLD`, `GC=F` | already available |
| Gold JPY context | USD gold plus `USDJPY=X` | already available as calculated context |

## New Safe Config Wiring

The following series were added because they fit the existing ticker-map and
yfinance acquisition pattern. They remain optional and sample-only may report
them as unavailable if no synthetic sample series exists.

| Classification | Config key | Ticker | Handling |
| --- | --- | --- | --- |
| `fx_eurjpy` | `tickers.japan.eur_jpy` | `EURJPY=X` | optional FX context |
| `equity_jp_nikkei` | `tickers.japan.nikkei_proxy` | `1321.T` | optional Japan equity proxy |
| `bond_jpy_intermediate` | `tickers.japan.jpy_bond_intermediate` | `2510.T` | optional domestic JPY bond proxy |
| `reit_jp` | `tickers.japan.jp_reit_proxy` | `1343.T` | optional Japanese REIT proxy |
| `gold_jpy_proxy` | `tickers.japan.gold_jpy_proxy` | `1540.T` | optional domestic gold proxy |

These additions are configuration and label wiring only. They do not create new
scores that affect trading decisions.

## Missing or Deferred Series

| Group | Desired fields | Classification | Reason |
| --- | --- | --- | --- |
| JGB yield curve | `jgb_2y`, `jgb_5y`, `jgb_10y`, `jgb_20y`, `jgb_30y`, curve spreads | official/statistical adapter needed | existing yfinance/FRED path does not provide a reliable full JGB curve contract |
| Japan CPI | `jp_cpi_yoy`, `jp_core_cpi_yoy`, `jp_cpi_trend` | official/statistical adapter needed | do not scrape or invent CPI values in this checkpoint |
| BOJ / domestic rates | `boj_policy_rate`, `boj_call_rate`, `domestic_rate_context` | official/statistical adapter needed | no existing parser or stable ticker contract in repo |
| Short and long JPY bonds | `bond_jpy_short`, `bond_jpy_long` | config-only candidate / investigate | can be added later if specific supported tickers are selected |
| JPY strength proxy | `fx_jpy_strength` | fixture/contract only | requires a defined basket or proxy method |

## Sample-Only Behavior

`--sample-only` remains conservative:

- New optional `.T` and FX series are requested through the existing config path.
- If a ticker has no synthetic sample series, acquisition logs show it as
  unavailable.
- Multi-asset report rows use `データ不足`, `未取得`, or `参考表示`.
- No values are synthesized for JGB curve, CPI, BOJ rates, or Japan REIT.
- Generated reports and cache outputs remain uncommitted artifacts.

## Candidate and Report Wiring

The multi-asset candidate layer now recognizes configured domestic JPY bond,
Japanese equity, Japanese REIT, and gold JPY proxy tickers when they appear in
`availability_map` or acquisition logs.

The report displays Japan-resident context as a compact supplemental line. This
is for visibility only and carries explicit non-impact flags.

## Non-Impact Boundary

Unchanged by v0.8.34:

- `final_action`
- equity `buy_readiness_score`
- threshold JSON
- reliability policy
- buy blocker logic
- buy decision card logic
- buy window / candidate thresholds
- risk label definitions
- CI
- scripts
- dependencies
- generated reports / cache / release archives

## Next Possible Work

- Choose explicit short and long JPY bond tickers before adding config keys.
- Add a dedicated official/statistical adapter for JGB yield curve and Japan CPI
  if a stable source and tests are defined.
- Add synthetic fixture-only JGB/CPI cases before any live adapter.
