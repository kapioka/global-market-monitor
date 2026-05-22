# japan_fx downgrade review

FX downgrade は診断対象です。現時点では `japan_fx_risk` の penalty や final action policy は変更しません。

## 使い方

```powershell
python -m project.japan_fx_downgrade_diagnostics
```

出力:

- `project/reports/japan_fx_downgrade_diagnostics.json`
- `project/reports/japan_fx_downgrade_diagnostics.md`

## 読み方

- `beneficial_downgrade`: 降格後に return または drawdown が悪化し、止めた判断が有効だった可能性
- `overblocked`: 降格後の return / excess return が良く、drawdown も浅かった可能性
- `inconclusive`: future return が不足している、または判断材料が足りない

`japan_fx_risk_moderate` は、今は policy 変更ではなく追跡対象として扱います。

FX policy 候補は `python -m project.fx_policy_replay` で replay 比較します。これは診断専用であり、現行 policy は変更しません。
