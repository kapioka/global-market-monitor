# Report UI Snapshot QA v0.8.4

v0.8.4 validates the beginner-readable top sections added in v0.8.2 and polished in v0.8.3. This is a synthetic/sample-only display verification task. It does not change investment decision logic, thresholds, data reliability rules, or score calculations.

## Scope

Validated sections:

- `まず見るポイント`
- 5-step `買い判断カード`

Validated synthetic scenarios:

| Scenario | Intended display check |
| --- | --- |
| standard | `監視継続` with `SPY` / `XLK` candidates |
| near_candidate | Candidate-adjacent state remains `材料待ち`, not advice |
| wait | Wait/decline state remains short and readable |
| insufficient_data | Internal sample wording is replaced with beginner-readable Japanese |
| no_candidates | `候補なし` renders without layout damage |
| long_blocker | Long reason text wraps without overflow or overlap |

## Snapshot Method

- Generated temporary HTML under `.tmp/v084_report_snapshots/`.
- Captured synthetic screenshots for each scenario at 1366px, 1024px, and 768px widths.
- Checked rendered beginner sections for horizontal scroll, element overflow, and overlap.
- Kept all generated HTML and screenshots outside version control.

## Results

All six scenarios passed at all three viewport widths:

- no page-level horizontal scrolling
- no measured overflow in the beginner summary tiles, decision steps, or readiness panel
- no measured overlap between beginner summary tiles or decision-flow items
- required labels remained present
- candidate-present and candidate-absent states rendered
- long blocker wording wrapped without breaking the layout

## Wording Checks

Top beginner sections do not show these internal terms:

- `raw/final buy_window`
- `raw/final buy_candidate`
- `diagnostic only`
- `proposed / candidate`
- `trigger path`
- `live_data_sufficient`
- `sample-only`
- `final_action`
- `buy_readiness_score`

Top beginner sections do not show these advice or outcome-guarantee phrases:

- `買うべき`
- `今が買い`
- `利益が出る`
- `安全に買える`

`これは成功確率ではありません` remains visible to prevent the explanatory readiness score from being read as an outcome forecast.

## Change Decision

The v0.8.3 HTML/CSS layout passed the multi-scenario checks without requiring product UI changes. v0.8.4 adds automated synthetic coverage and this QA record only.

## Non-Goals

- No JavaScript.
- No external libraries.
- No report decision logic changes.
- No threshold JSON changes.
- No `reliability_policy`, `final_action`, or `buy_readiness_score` calculation changes.
- No generated report, cache, screenshot, or release archive commits.
