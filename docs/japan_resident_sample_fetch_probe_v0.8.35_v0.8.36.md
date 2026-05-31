# v0.8.35-v0.8.36 Japan Resident Sample Coverage and Fetch Safe Probe

## Purpose

This checkpoint makes the v0.8.34 Japan-resident optional ticker wiring visible
in sample-only mode before relying on live fetch behavior.

It does not add JGB curve, Japan CPI, or BOJ official adapters.

## Sample Coverage

Synthetic sample series were added for:

- `2510.T` domestic JPY bond proxy
- `1343.T` Japanese REIT proxy
- `1540.T` domestic gold proxy
- `1321.T` Nikkei 225 proxy
- `EURJPY=X` optional FX context

The sample data is artificial and exists only for sample-mode coverage. It is
not a live data source and must not be used as a decision signal.

## Sample-Only Report Behavior

With `python project/main.py --sample-only`, the added series appear as sample
fallback rows in data acquisition output. The multi-asset section can now show
Japan-resident context for JPY bonds, Japan REIT, gold JPY proxy, Japanese
equity, and FX context as `参考表示` or other conservative Japanese labels.

JGB curve, Japan CPI, and BOJ domestic-rate fields remain missing/deferred. No
fake macro values are introduced.

## Limited Fetch Safe Probe

The limited probe used the existing `fetch_market_data()` path for only:

- `2510.T`
- `1343.T`
- `1540.T`
- `1321.T`
- `EURJPY=X`

Observed result in the local probe:

| Ticker | Status | Provider | Handling |
| --- | --- | --- | --- |
| `2510.T` | `ok` | `yfinance` | existing path handled |
| `1343.T` | `ok` | `yfinance` | existing path handled |
| `1540.T` | `ok` | `yfinance` | existing path handled |
| `1321.T` | `ok` | `yfinance` | existing path handled |
| `EURJPY=X` | `ok` | `yfinance` | existing path handled |

This probe is not a broad actual-smoke run and is not CI-required.

## Non-Impact Boundary

Unchanged by this checkpoint:

- `final_action`
- equity `buy_readiness_score`
- threshold JSON
- reliability policy
- buy blocker logic
- buy decision card logic
- buy window / candidate thresholds
- risk label definitions
- CI configuration
- scripts
- dependencies
- generated reports, cache, or release archives
