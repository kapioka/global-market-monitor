# threshold historical replay review

Updated: 2026-05-15 JST
Branch: `codex/threshold-proposal-review`

## Decision

`hold`

The proposed threshold set should not be applied to `risk_line_thresholds_active.json`.
v0.7.0 should proceed with active thresholds unchanged.

Historical replay shows that the proposed thresholds make the current history set more defensive, but the evidence is not strong enough to adopt:

- `buy_window` remains 0 in both active and proposed replay.
- Proposed thresholds change 7 `watch` cases into `wait`.
- Proposed thresholds change those same 7 dates from `normal` risk stage to `extreme_danger_line_reached`.
- 13w / 26w / 52w forward returns are not available yet for this history set.
- There are no cases where proposed thresholds prevented a bad `buy_window`.
- There are no cases where proposed thresholds missed a good `buy_window`, but this is because there were no `buy_window` cases to evaluate.

This is a strong defensive shift, not confirmed improvement. The proposal remains a review candidate only.

## Replay Outputs

- `project/reports/threshold_historical_replay_active.json`
- `project/reports/threshold_historical_replay_proposed.json`
- `project/reports/threshold_historical_replay_diff.json`

These files are generated reports and are not intended to be committed with the source change.

## Method

The replay runner evaluates each saved history date twice:

1. Rebuild risk-line monitor rows from cached market snapshot prices using `risk_line_thresholds_active.json`.
2. Rebuild risk-line monitor rows from the same prices using `risk_line_thresholds_proposed.json`.
3. Recompute risk-line stage and spot action using the saved history regime, score, cycle, credit monitor, inflation monitor, sector rotation, and reliability policy.
4. Run action validation against `project/reports/validation_prices.json`.

The active threshold file itself is not modified.

## Summary

| metric | active | proposed | interpretation |
|---|---:|---:|---|
| total history count | 67 | 67 | Same replay target. |
| `buy_window` count | 0 | 0 | No adoption evidence for buy-window quality. |
| `watch` count | 7 | 0 | Proposed removes all watch cases. |
| `wait` count | 60 | 67 | Proposed increases wait by 7. |
| final action changed count | - | 7 | All changes are `watch` to `wait`. |
| risk stage changed count | - | 7 | All changes are `normal` to `extreme_danger_line_reached`. |
| cases where proposed prevented bad `buy_window` | - | 0 | No buy-window cases existed. |
| cases where proposed missed good `buy_window` | - | 0 | No buy-window cases existed. |
| cases where proposed increased wait | - | 7 | Practical usability risk. |

## Forward Return Metrics

| action / horizon | active count | active mean return | active win rate | active worst max DD | proposed count | proposed mean return | proposed win rate | proposed worst max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `wait` / 4w | 39 | 0.078632 | 1.0 | -0.03576 | 39 | 0.078632 | 1.0 | -0.03576 |
| `watch` / 4w | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 13w | 0 | n/a | n/a | n/a | 0 | n/a | n/a | n/a |
| 26w | 0 | n/a | n/a | n/a | 0 | n/a | n/a | n/a |
| 52w | 0 | n/a | n/a | n/a | 0 | n/a | n/a | n/a |

Interpretation:

- The only usable forward-return horizon in the current data is 4w.
- Longer horizons are unavailable because the saved history is too recent relative to the validation price series.
- 4w results do not distinguish active/proposed quality because proposed mainly reclassifies recent `watch` cases whose 4w future return is not available yet.

## Changed Cases

| date | active action | proposed action | active risk stage | proposed risk stage |
|---|---|---|---|---|
| 2026-05-05 | `watch` | `wait` | `normal` | `extreme_danger_line_reached` |
| 2026-05-06 | `watch` | `wait` | `normal` | `extreme_danger_line_reached` |
| 2026-05-07 | `watch` | `wait` | `normal` | `extreme_danger_line_reached` |
| 2026-05-08 | `watch` | `wait` | `normal` | `extreme_danger_line_reached` |
| 2026-05-09 | `watch` | `wait` | `normal` | `extreme_danger_line_reached` |
| 2026-05-10 | `watch` | `wait` | `normal` | `extreme_danger_line_reached` |
| 2026-05-11 | `watch` | `wait` | `normal` | `extreme_danger_line_reached` |

## Judgment

### Adopt criteria

Not met.

- There are no `buy_window` cases, so false positive reduction cannot be demonstrated.
- 13w / 26w metrics are unavailable.
- Proposed thresholds increase `wait` and eliminate all `watch` cases in the changed period.

### Hold criteria

Met.

- Evidence is incomplete.
- `buy_window` is too sparse.
- Proposed thresholds are materially more defensive.
- Phase 12 already found many `fallback_review` proposed rules.

### Reject criteria

Not fully met.

- Proposed thresholds do increase `wait`, but there is not enough forward-return evidence yet to prove that this is harmful.
- Maximum drawdown does not worsen in the available 4w data, but the decisive changed cases have no completed forward horizon.

## Recommendation

Keep `risk_line_thresholds_proposed.json` as a review artifact.

Do not manually copy proposed thresholds into `risk_line_thresholds_active.json`.

Adoption is blocked until all of the following are available:

- More historical saved reports with completed 13w / 26w outcomes.
- A longer backfilled replay dataset that can produce `buy_window` cases.
- Enough `buy_window` cases to judge false positives and missed opportunities.
- Evidence that 13w / 26w / 52w returns do not deteriorate.
- Evidence that maximum drawdown improves or at least does not worsen.
- Per-rule review that excludes `fallback_review` rules from automatic adoption.
- A partial-adoption test that evaluates only `decision: adopt` proposed rules.
