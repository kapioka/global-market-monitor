# v0.8.42 Japan Macro Manual Sources

## Purpose

Japan official macro data is optional and display-only. v0.8.42 avoids making a
shared API key or per-user API registration part of normal use. The preferred
order is:

1. Official appId-free public files.
2. Local manual CSV files downloaded by the user from official pages.
3. Existing cache reuse only when freshness is explicitly validated in a future
   checkpoint.
4. Optional e-Stat API only when a user supplies `ESTAT_APP_ID`.

No macro value affects `final_action`, equity `buy_readiness_score`, threshold
JSON, reliability policy, buy blockers, or buy decision card logic.

## Manual directory

Manual source files may be placed under:

```text
project/manual_sources/
```

This directory is optional. It is not created by normal runtime and should not be
committed with downloaded official files.

## CPI manual CSV

Expected filename:

```text
project/manual_sources/japan_cpi.csv
```

Expected compact columns:

```csv
Date,CPI YoY,Core CPI YoY
2026-04-01,2.4,2.1
2026-05-01,2.7,2.4
```

Accepted date column labels include `Date`, `month`, `年月`, and `年月日`.
Accepted CPI value labels include:

- `CPI YoY`
- `All Items YoY`
- `jp_cpi_yoy`
- `総合前年比`

Accepted core CPI labels include:

- `Core CPI YoY`
- `core yoy`
- `jp_core_cpi_yoy`
- `生鮮食品を除く総合前年比`

If the file is absent, the source returns `manual_file_missing` and no CPI value
is used.

## BOJ short-rate manual CSV

Expected filename:

```text
project/manual_sources/boj_short_rate.csv
```

Expected compact columns:

```csv
Date,Policy Rate,Call Rate
2026-04-01,0.25,0.23
2026-05-01,0.25,0.28
```

Accepted date column labels include `Date`, `month`, `年月`, and `年月日`.
Accepted short-rate labels include:

- `Policy Rate`
- `boj_policy_rate`
- `政策金利`
- `Call Rate`
- `boj_call_rate`
- `無担保コール翌日物`

If the file is absent and no stable appId-free BOJ CSV endpoint is selected, the
source returns `endpoint_not_resolved`.

## e-Stat policy

e-Stat remains optional only.

- No appId is bundled.
- No appId is logged.
- Tests, CI, sample-only, and normal report generation do not require appId.
- If `ESTAT_APP_ID` is absent, no e-Stat network request is attempted.

## Result handling

Only source results with `status` equal to `ok` or `partial` are promoted into
Japan-resident display context fields such as `inflation` and
`domestic_rates`.

Fallback statuses are source references only:

- `manual_file_missing`
- `endpoint_not_resolved`
- `missing_credentials`
- `unavailable`
- `failed`

These entries keep `value: null` and `observations: {}` and must not be treated
as real macro values.
