# v0.8.16 Actual Data Readiness Regression and Smoke Command

## Why Sample-Only Is Not Enough

`python project/main.py --sample-only` is an effective startup and generated
report smoke check, but it intentionally exercises synthetic/fallback data.
It therefore does not protect the actual-data combination observed in the
field: `watch`, normal risk stage, high reliability, building recovery, and
caution-level rates/FX blockers.

## Sanitized Actual-Data Fixture

The fixture at
`project/tests/fixtures/actual_readiness_case_v0.8.16.json` is derived from a
locally generated actual-data report captured at `2026-05-26T19:10:51 JST`.
It stores only the minimum fields needed to rebuild the explanatory readiness
calculation:

- action layers
- risk stage
- reliability level and decision-allowed status
- recovery grade
- caution flags
- total score and buy threshold
- expected explanatory score and blocker severities

It intentionally excludes raw price series, report HTML, report history,
network/API payloads, cache contents, local paths, and personal information.

The fixture locks the v0.8.15 regression boundary:

- pre-fix displayed score documented from the captured report: `1`
- current expected score: `31`
- accepted explanatory range: `25` to `45`
- `final_action`: `watch`
- risk stage: `normal`

## Optional Actual-Data Smoke Command

Run locally when a real-data check is required:

```powershell
python project\main.py --actual-smoke
```

This command is separate from `--sample-only`.

- If a saved acquired market snapshot exists under the configured cache
  directory, the newest complete snapshot is used to build a report.
- If no saved snapshot exists, the normal remote-fetch path is attempted.
- If cached data cannot be used and fetch fails, the command reports that the
  optional actual-data smoke failed; it is not a required CI gate.

The output report remains under ignored generated-report paths. It must not be
committed.

## Unchanged Boundaries

This work does not change:

- `buy_readiness_score` logic established in v0.8.15
- blocker classification or buy decision logic
- `final_action`
- threshold decisions or threshold JSON
- reliability policy
- buy-window or buy-candidate thresholds
- risk labels
- CI workflows, security scripts, or dependency definitions

## Optional Local Validation

1. Run `python project\main.py --actual-smoke`.
2. Open the generated `project/reports/report.html`.
3. Check the displayed `買い候補度` and current decision.
4. Inspect `project/reports/report_summary.json` for the score factors and
   action layers.
5. Confirm generated outputs remain ignored and are not staged.

Network access and changing market data make this command unsuitable as a
mandatory CI test. The committed fixture provides the stable regression gate.
