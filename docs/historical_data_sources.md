# historical data sources

このプロジェクトの historical replay は、まず yfinance の価格履歴を使います。

- yfinance: ETF、指数、FX、商品先物の初期取得候補
- FRED: 金利や macro 系列の補助候補
- Alpha Vantage 等: API key が必要な代替候補

注意点:

- 取得データは検証補助であり、投資助言ではありません。
- 欠損、上場時期、ticker 変更、代替 ticker の影響を summary で確認します。
- `project/cache` と `project/reports` の generated data は原則コミットしません。
- API key や秘密情報は repo-local `.env` や docs に保存しません。
