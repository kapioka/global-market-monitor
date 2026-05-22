# buy_window sparsity review

`buy_window` が少ない場合は、閾値を直接緩める前に raw / risk-adjusted / final のどこで止まったかを確認します。

## 方針

- `market_raw_action`: 市場スコアと回復証拠だけに近い判定
- `risk_adjusted_action`: 危険ライン、信用、インフレ、為替などの blocker を反映した判定
- `final_action`: data reliability policy まで通した最終表示
- `buy_candidate`: 買い推奨ではなく、`watch` と `buy_window` の間の買い場候補

## 使い方

```powershell
python -m project.buy_window_diagnostics
```

出力:

- `project/reports/buy_window_diagnostics.json`
- `project/reports/buy_window_diagnostics.md`

generated reports は検証成果物であり、通常はコミット対象にしません。

## 読み方

`raw_buy_window_count` があるのに `final_buy_window_count` が0なら、市場シグナルは出たが安全ガードで止まっています。

`raw_buy_window_count` も0なら、市場スコア、回復証拠、または blocker が `buy_window` に届いていません。

`buy_candidate` は「買い場候補」です。買い指示ではありません。
