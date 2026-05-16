# risk_line_thresholds_proposed.json review

Updated: 2026-05-15 JST
Branch: `codex/threshold-proposal-review`
Base tag: `pre-v0.7.0-main-merge`

## Decision

`hold`

The proposed threshold file is valid JSON and can be kept as a review artifact, but it should not be applied to `risk_line_thresholds_active.json` yet.

Reasons:

- The stash diff itself only updates proposed metadata: `version` and `generated_at`.
- Active/proposed comparison shows all 30 stage rules differ from active thresholds.
- Proposed rules include 22 `fallback_review` rules and only 8 `adopt` rules.
- Existing action validation history has no `buy_window` cases and no 13w/26w/52w completed horizons, so it cannot prove the proposal improves investment decisions.
- Applying the full proposed set would change many feature definitions, not only threshold values.

## Stash Diff

Applied stash: `stash@{0}` before branch creation.

Changed file:

- `project/risk_line_thresholds_proposed.json`

Direct stash diff:

| field | before | after |
|---|---|---|
| `threshold_set.version` | `2026-05-09-194246` | `2026-05-14-214135` |
| `threshold_set.generated_at` | `2026-05-09T19:42:46+09:00` | `2026-05-14T21:41:35+09:00` |

No threshold rule value changed in the stash diff itself.

## Schema / Safety Checks

- JSON syntax: passed with `python -m json.tool project/risk_line_thresholds_proposed.json`
- Threshold-related tests: passed
- Full test suite: pending in this review branch
- Active threshold file: not changed

The proposed payload keeps:

- `schema_version: 1`
- `threshold_set.status: proposed`
- `threshold_set.name: risk-line-proposed`
- `indicators` for the same 10 monitored risk-line indicators as the active file

## Active / Proposed Difference

Summary:

| item | value |
|---|---:|
| active version | `2026-04-05-active-161353` |
| proposed version | `2026-05-14-214135` |
| active indicator count | 10 |
| proposed indicator count | 10 |
| added rules | 0 |
| removed rules | 0 |
| changed rules | 30 |
| unchanged rules | 0 |

Proposed decision breakdown:

| decision | count |
|---|---:|
| `adopt` | 8 |
| `fallback_review` | 22 |

High-level implication:

- This is not a small numeric retuning.
- It is a broad proposal that changes every active stage rule.
- Many proposed rules use different features than active rules, such as persistence, z-score, ROC, or composite drawdown/ROC features.
- Because most rules are `fallback_review`, adopting them wholesale would bypass the review warning embedded in the proposed payload itself.

## Changed Rule Examples

| indicator / stage | active | proposed | note |
|---|---|---|---|
| `SPY warning` | `drawdown_13w <= -0.024156` | `drawdown_and_roc_4w <= 0.0` | Feature changes from raw drawdown to composite signal. |
| `SPY danger` | `drawdown_13w <= -0.046031` | `drawdown_and_roc_4w <= 0.0` | Same proposed value for warning/danger, requires extra review. |
| `^VIX warning` | `level_zscore >= 0.289384` | `roc_8w >= 0.039703` | Shifts from level stress to momentum stress. |
| `^VIX extreme` | `level_percentile >= 0.923077` | `level_percentile >= 0.548077` | Much easier to trigger if adopted. |
| `HYG warning` | `drawdown_13w <= -0.009923` | `level_zscore <= -0.782115` | Feature changes from drawdown to level z-score. |
| `HYG/LQD warning` | `level_percentile <= 0.548077` | `roc_4w <= -0.017011` | Feature changes from level percentile to 4w ROC. |
| `^TNX danger` | `roc_2w >= 0.053033` | `adverse_persistence_8 >= 5.0` | Feature changes to persistence count. |

## Action Validation Impact

Current action validation baseline after main merge:

| action | count | 4w mean return | 4w win rate | 4w worst max drawdown |
|---|---:|---:|---:|---:|
| `wait` | 44 | 0.065898 | 1.0 | -0.03576 |
| `watch` | 23 | 0.096937 | 1.0 | -0.03576 |
| `buy_window` | 0 | n/a | n/a | n/a |

Diagnostics:

- `watch_count`: 23
- `watch_to_buy_window_promotion_rate`: 0.0
- `buy_window_negative_rate_13w`: n/a
- `wait_missed_rally_rate_13w`: n/a

Impact conclusion:

- Existing stored histories are evaluated against their already-recorded actions.
- Merely changing `risk_line_thresholds_proposed.json` does not change historical action validation output because proposed thresholds are not active.
- A true active/proposed action comparison requires replaying historical report generation with active thresholds and then with proposed thresholds.
- That replay is not implemented in this phase, so the proposal cannot be adopted based on action validation yet.

## Recommendation

Keep this proposal as `hold`.

Do not apply it to `project/risk_line_thresholds_active.json` until a replay-based impact check exists.

Minimum next checks before adoption:

- Build a replay runner that can regenerate historical risk-line stages under active and proposed threshold payloads.
- Compare final action changes, risk-line stage changes, and action validation metrics under both threshold sets.
- Review the 22 `fallback_review` rules individually.
- Reject or exclude rules where warning/danger/extreme collapse to similar behavior.
- Re-run sample-only and live-safe reports after any selected partial adoption.

## Commit Scope

Include:

- `project/risk_line_thresholds_proposed.json`
- `docs/risk_line_threshold_proposal_review.md`

Do not include:

- `project/risk_line_thresholds_active.json`
- generated `project/reports/*`
- cache/log/runtime files
- unrelated upload artifacts
