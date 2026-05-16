# Risk Line Threshold Schema

## Files

- `project/risk_line_thresholds_active.json`
  - 現在 live 判定で使う threshold 集合
- `project/risk_line_thresholds_proposed.json`
  - 再校正後に生成される提案 threshold 集合

## Top-Level Shape

```json
{
  "schema_version": 1,
  "threshold_set": {
    "name": "risk-line-active or risk-line-proposed",
    "version": "2026-04-05-active-v1",
    "status": "active or proposed",
    "generated_at": "ISO-8601 datetime",
    "source_report": "report name",
    "notes": "free text"
  },
  "indicators": {
    "SPY": {
      "weight": 1.15,
      "thresholds": {
        "warning": {
          "feature": "drawdown_13w",
          "threshold": -0.024156,
          "direction": "lower",
          "decision": "adopt",
          "reason": "passes_backtest_and_actual_value_check",
          "backtest_metrics": {},
          "actual_value_check": {}
        }
      }
    }
  }
}
```

## Rules

- `active` は live 判定専用。`review` や `reject` を入れない。
- `proposed` は reality-check 後の候補。apply 前提ではなく review 前提。
- `direction` は `higher` または `lower`。
- `feature` は `stress_monitor.py` が計算できる feature 名に限る。
- stage 名は `warning`, `danger`, `extreme` を使う。
- apply 前に `actual_value_check.status == pass` を必須にする予定。
