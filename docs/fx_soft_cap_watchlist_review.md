# fx_soft_cap watchlist review

`fx_soft_cap` remains diagnostic-only. This watchlist tracks cases that would become `buy_candidate` under the diagnostic policy.

## Use

```powershell
python -m project.fx_soft_cap_watchlist
```

Outputs:

- `project/reports/fx_soft_cap_watchlist.json`
- `project/reports/fx_soft_cap_watchlist.md`

## Review Status

- `waiting_4w`: no 4-week result yet
- `waiting_13w`: 4-week result exists, 13-week result is still missing
- `waiting_26w`: 13-week result exists, 26-week result is still missing
- `ready_for_review`: 26-week result exists
- `reviewed`: reserved for future manual review state

Adoption remains `hold` until enough 13w/26w return, excess return, and max drawdown evidence is available.

When historical replay output is available, the watchlist also attaches similar historical case counts and 13w excess return / worst drawdown reference values. These fields are diagnostic only and do not affect final action.
