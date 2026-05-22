# buy_window calibration review

`buy_window` を増やす候補は、active threshold を直接変更せず replay 結果として比較します。

## 使い方

```powershell
python -m project.buy_window_calibration
```

出力:

- `project/reports/buy_window_calibration.json`
- `project/reports/buy_window_calibration.md`

## 採用判断

初期結論は原則 `hold` です。採用候補にするには、少なくとも以下を満たす必要があります。

- `buy_window` 件数が増える
- 13週 / 26週 excess return が悪化しない
- worst max drawdown が悪化しない
- false buy_window が増えすぎない
- risk line extreme と reliability cap を弱めていない

このレポートは calibration only であり、`risk_line_thresholds_active.json` と `risk_line_thresholds_proposed.json` は変更しません。

## 採用禁止条件

- max drawdown が悪化する
- false buy_window が増える
- reliability policy を弱める
- risk line extreme を無視する
- active/proposed threshold JSON を変更する
