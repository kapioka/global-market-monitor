# threshold overblocking diagnostics

Updated: 2026-05-15 JST
Branch: `codex/threshold-proposal-review`

## Decision

`hold`

The current proposed thresholds remain too defensive for adoption. Candidate policies can reduce the severity label in some cases, but they do not restore the 7 `watch` cases or provide evidence that proposed thresholds improve realized outcomes.

## Baseline

| set | wait | watch | buy_window | risk stage summary |
|---|---:|---:|---:|---|
| active | 60 | 7 | 0 | `extreme_danger_line_reached: 60`, `normal: 7` |
| proposed | 67 | 0 | 0 | `extreme_danger_line_reached: 67` |

The 7 changed cases are all:

```text
watch / normal -> wait / extreme_danger_line_reached
```

There is still no `buy_window` case, so the replay cannot show that proposed thresholds prevented a bad `buy_window`.

## Changed Case Diagnostics

Generated files:

- `project/reports/threshold_changed_cases.json`
- `project/reports/threshold_changed_cases.md`

| date | active | proposed | active score | proposed score | proposed danger / extreme | classification | main contributors |
|---|---|---|---:|---:|---:|---|---|
| 2026-05-05 | `watch / normal` | `wait / extreme` | 27.26 | 51.86 | 3 / 2 | `inconclusive` | `^VIX`, `CL=F`, `BZ=F` |
| 2026-05-06 | `watch / normal` | `wait / extreme` | 29.54 | 46.34 | 2 / 1 | `inconclusive` | `^VIX`, `BZ=F` |
| 2026-05-07 | `watch / normal` | `wait / extreme` | 25.88 | 34.85 | 1 / 0 | `inconclusive` | `BZ=F` |
| 2026-05-08 | `watch / normal` | `wait / extreme` | 29.64 | 38.67 | 1 / 0 | `inconclusive` | `BZ=F` |
| 2026-05-09 | `watch / normal` | `wait / extreme` | 29.64 | 38.67 | 1 / 0 | `inconclusive` | `BZ=F` |
| 2026-05-10 | `watch / normal` | `wait / extreme` | 26.41 | 42.06 | 1 / 1 | `inconclusive` | `BZ=F` |
| 2026-05-11 | `watch / normal` | `wait / extreme` | 26.41 | 42.06 | 1 / 1 | `inconclusive` | `BZ=F` |

All 7 cases are `inconclusive` because the replay has no completed 4w / 13w / 26w / 52w forward returns for those dates.

## Overblocking Cause

The proposed set is not merely tightening existing active rules. It changes the active feature definitions and introduces proposed rules that are much easier to trigger in early May 2026.

Observed contributors:

- `^VIX` moves from `normal` to `extreme` on 2026-05-05 and 2026-05-06.
- `CL=F` moves from `normal` to `extreme` on 2026-05-05.
- `BZ=F` is the persistent driver across all 7 changed cases.
- The proposed composite risk score rises materially, even when danger/extreme counts remain low.

Important detail:

- On 2026-05-07 to 2026-05-09, proposed has only `danger_count: 1` and `extreme_count: 0`, yet the final risk stage is still `extreme_danger_line_reached`.
- This indicates that the existing risk-line stage logic can reach `extreme_danger_line_reached` through persistence or overlay conditions, not only through `extreme_count >= 2`.

## Candidate Comparison

Generated file:

- `project/reports/threshold_candidate_comparison.json`

| candidate | wait | watch | buy_window | stage counts | action changes vs active | increased wait vs active | interpretation |
|---|---:|---:|---:|---|---:|---:|---|
| active | 60 | 7 | 0 | extreme 60 / normal 7 | 0 | 0 | Current baseline. |
| proposed | 67 | 0 | 0 | extreme 67 | 7 | 7 | Overblocks the 7 watch cases. |
| stage_limited | 67 | 0 | 0 | extreme 53 / danger 14 | 7 | 7 | Reduces some extreme labels, but action remains wait. |
| multi_confirm_extreme | 67 | 0 | 0 | extreme 53 / danger 14 | 7 | 7 | Similar to stage_limited in current replay. |
| ignore_fallback_extreme | 67 | 0 | 0 | danger 67 | 7 | 7 | Removes extreme labels, but turns all stages into danger. |

Interpretation:

- Candidate policies are useful diagnostics for stage severity.
- None of the current candidates improves action balance.
- Because `danger_line_reached` still acts as a blocker, downgrading `extreme` to `danger` does not restore `watch`.
- `ignore_fallback_extreme` is too blunt: it removes all extreme labels but still leaves every case in danger.

## Normal To Extreme Diagnosis

`extreme_danger_line_reached` can occur through several paths:

- composite risk score is high enough
- at least 2 extreme indicators
- VIX danger persistence
- credit ratio extreme with VIX/MOVE danger
- credit stress severe with VIX/MOVE extreme and oil danger

In the changed 7 cases:

- Some cases have enough extreme indicators to justify an extreme stage under current proposed rules.
- Some cases have low explicit extreme count but still land in extreme, likely due to persistence/overlay behavior.
- `fallback_review` proposed rules are still part of the evaluated threshold payload, so weakly reviewed rules can contribute to high stage severity.

## Recommendation

Keep proposed thresholds as `hold`.

Do not adopt any of the current candidates directly.

Next improvement should be narrower:

1. Add replay diagnostics that records exact stage trigger path from `evaluate_risk_lines`.
2. Review the proposed `BZ=F`, `^VIX`, and `CL=F` rules first.
3. Test a partial candidate that uses only `decision: adopt` rules and excludes `fallback_review` rules entirely.
4. Consider making `danger_line_reached` less automatically blocking only after realized forward returns prove that active `watch` was unsafe.

## Safety Boundary

- `project/risk_line_thresholds_active.json` remains unchanged.
- Proposed thresholds are not adopted.
- Candidate policies are diagnostic only.
- Generated reports should not be committed.
