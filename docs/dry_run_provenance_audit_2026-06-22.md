# Dry-Run Provenance Audit 2026-06-22

## Scope

This file records Phase 0-2 evidence for the dry-run/cache-only provenance audit.

Goal:
`Dry-Run Provenance Audit, Strict Primary Historical Replay Evidence, Holdout Validation, and Durable Risk-Engine Finalization`

Protected items not changed:

- `project/config.yaml`
- `project/risk_line_thresholds_active.json`
- `project/risk_line_thresholds_proposed.json`
- production `final_action`
- production `buy_readiness_score`
- `risk_engine_v2.mode`
- production report history

## Reproduction

Baseline:

```powershell
git status --short
git branch --show-current
git log -3 --oneline
git diff --check
```

Observed repository state:

- branch: `main`
- HEAD: `7093d6a fix: add risk engine promotion gate`
- worktree before implementation: clean

Isolated output root:

```text
<workspace>\.tmp\dry_run_provenance\phase0_20260622_192046
```

The temporary config redirected:

- `logs_dir`
- `reports_dir`
- `sample_output_dir`
- `cache_dir`

Cache used for cache-only actual smoke:

```text
.tmp\dry_run_provenance\phase0_20260622_192046\cache\market_snapshots\market_snapshot_2026-06-20_210709.csv
.tmp\dry_run_provenance\phase0_20260622_192046\cache\market_snapshots\market_snapshot_2026-06-20_210709.json
```

Executed cache-only command:

```powershell
python -c "from project.main import run_actual_smoke; run_actual_smoke(r'.tmp\dry_run_provenance\phase0_20260622_192046\config.yaml', open_dashboard=False)"
```

Execution mode after repair:

- `execution_mode`: `actual_smoke_cache_only`
- `data_mode_label`: `キャッシュ使用`
- `network_access`: `not_used_when_cache_available`
- `cache_read_allowed`: `true`
- `cache_write_allowed`: `false`
- `production_state_write_allowed`: `false`

## Side-Effect Audit

Compared SHA-256 hashes before and after isolated runs for:

- `project/reports/risk_engine_v2_state.json`
- `project/risk_line_thresholds_active.json`
- `project/risk_line_thresholds_proposed.json`
- `project/config.yaml`
- files under `project/reports/history`

Result:

```text
NO_PRODUCTION_HASH_DIFFS_BY_HASH
```

`git status --short` after isolated runs showed only intentional source/test/doc edits.

## Four-Week Return Contract

Canonical rule selected for this report path:

- weekly series: `4週` = 4 valid weekly observations
- daily exchange-traded market series: `4週` must not mean 4 daily rows
- incomplete future weekly labels must be dropped before forward-fill

Defect found:

`resample("W-FRI").last().dropna(how="all").ffill()` kept a `2026-06-20` row where only `USDJPY=X` had a value. Pandas labeled that row as week ending `2026-06-26`, then `ffill()` carried Japan ETF values into that future week. As a result, the displayed `4週` for Japan ETFs compared `2026-05-29` to `2026-06-19`, effectively a 3-week comparison.

Repair:

`project/pipeline.py::resample_weekly_closes` now drops weekly labels later than the latest raw observation date before applying `ffill()`.

## Value Provenance

Source:

- `source_kind`: cache snapshot
- `source_id`: `market_snapshot_2026-06-20_210709`
- `retrieved_at`: `2026-06-20T21:07:09`
- `report_generated_at`: `2026-06-22T19:42:39`
- `report_path`: `.tmp\dry_run_provenance\phase0_20260622_192046\reports\history\report_2026-06-22_194239.json`

### 1306.T

```yaml
symbol: 1306.T
display_label: TOPIX連動ETF
execution_mode: actual_smoke_cache_only
dry_run_kind: cache-only actual smoke
source_kind: cache_snapshot
source_id: market_snapshot_2026-06-20_210709
dataset_or_fixture_id: none
cache_path_or_manifest_id: market_snapshot_2026-06-20_210709.json
evaluation_date: 2026-06-22
latest_observation_date: 2026-06-19
comparison_observation_date: 2026-05-22
comparison_session_count: 4 weekly observations
comparison_calendar_days: 28
current_value: 429.7
comparison_value: 412.4
return_4w: 4.1950
quality_flags:
  - split_or_discontinuity_suspected
stage_eligible: false for strict risk use
report_section: domestic_market_metrics / multi_asset_candidates
calculation_function: project.domestic_market_metrics._change_percent
formula: ((429.7 / 412.4) - 1) * 100
display_result: 12週変化 and drawdown are excluded because split/discontinuity is suspected
write_side_effects: isolated reports/state only
```

### 2510.T

```yaml
symbol: 2510.T
display_label: 国内債券ETF
execution_mode: actual_smoke_cache_only
dry_run_kind: cache-only actual smoke
source_kind: cache_snapshot
source_id: market_snapshot_2026-06-20_210709
dataset_or_fixture_id: none
cache_path_or_manifest_id: market_snapshot_2026-06-20_210709.json
evaluation_date: 2026-06-22
latest_observation_date: 2026-06-19
comparison_observation_date: 2026-05-22
comparison_session_count: 4 weekly observations
comparison_calendar_days: 28
current_value: 813.7
comparison_value: 806.0
return_4w: 0.9553
quality_flags:
  - valid
stage_eligible: informational only
report_section: domestic_market_metrics / multi_asset_candidates
calculation_function: project.domestic_market_metrics._change_percent
formula: ((813.7 / 806.0) - 1) * 100
display_result: 4週 1.0%
write_side_effects: isolated reports/state only
```

### 1343.T

```yaml
symbol: 1343.T
display_label: 国内REIT ETF
execution_mode: actual_smoke_cache_only
dry_run_kind: cache-only actual smoke
source_kind: cache_snapshot
source_id: market_snapshot_2026-06-20_210709
dataset_or_fixture_id: none
cache_path_or_manifest_id: market_snapshot_2026-06-20_210709.json
evaluation_date: 2026-06-22
latest_observation_date: 2026-06-19
comparison_observation_date: 2026-05-22
comparison_session_count: 4 weekly observations
comparison_calendar_days: 28
current_value: 1914.0
comparison_value: 1934.5
return_4w: -1.0597
quality_flags:
  - valid
stage_eligible: informational only
report_section: domestic_market_metrics / multi_asset_candidates
calculation_function: project.domestic_market_metrics._change_percent
formula: ((1914.0 / 1934.5) - 1) * 100
display_result: 4週 -1.1%
write_side_effects: isolated reports/state only
```

## WTI Display Finding

The old display concern was valid: `pressure_score = 0` can be misleading for WTI because it only describes the adopted upward/inflation pressure rule.

Current display after repair:

```text
WTI原油
インフレ方向圧力 0/100
需要減速方向 40/100
4週変化 -20.8%
データ品質 有効
```

Reason:

```text
原油は下落方向の圧力がありますが、株式・信用市場の同時悪化が揃っていないため、需要崩壊シグナルにはしていません。
```

This means WTI is no longer presented as a generic `危険度 0/100` in the risk track. It is split into inflation and demand-deceleration directions.

## Tests

Targeted tests run:

```powershell
python -m pytest project/tests/test_pipeline.py project/tests/test_domestic_market_metrics.py project/tests/test_oil_context.py project/tests/test_report_generator.py::test_render_html_shows_oil_directional_context_instead_of_generic_zero_risk -q
```

Result:

```text
13 passed
```

Compile check:

```powershell
python -m compileall -q project
```

Result:

- exit code: `0`
- warning only: several `project\.runtime\pytest-*` temporary paths could not be listed

## Remaining Blockers

Later phases are still blocked until the full strict goal is completed:

- official primary-series inventory
- durable raw/normalized store
- point-in-time replay
- independent episode evidence
- frozen train/validation/holdout split
- holdout run
- promotion-gate reevaluation
- full validation

`risk_engine_v2.mode` remains `shadow`.
