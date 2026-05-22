# buy_window case study review

raw `buy_window` が final action で降格されたケースを確認するためのレビューです。

## 使い方

```powershell
python -m project.buy_window_case_study
```

出力:

- `project/reports/buy_window_case_study.json`
- `project/reports/buy_window_case_study.md`

## 読み方

- `beneficial_block`: 降格後に下落または深い drawdown があり、止めた判断が有効だった可能性
- `overblocked`: 降格後の return / excess return が良く、drawdown も浅かった可能性
- `inconclusive`: 将来データ不足または判定材料不足

このレビューは判断材料です。active/proposed threshold JSON は変更しません。
