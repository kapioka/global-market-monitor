# historical backfill review

historical backfill は、`fx_soft_cap` の採用判断を実時間の 26 週待ちだけに依存させないための検証補助です。

- 初期データソースは yfinance
- 出力先は `project/cache` と `project/reports`
- API key は不要な範囲から開始
- 取得失敗 ticker は落とさず summary に残す
- cache / generated reports は source-controlled threshold ではない

この backfill は投資助言ではなく、過去価格から replay 用 feature を作るための補助データです。`risk_line_thresholds_active.json` と `risk_line_thresholds_proposed.json` は変更しません。
