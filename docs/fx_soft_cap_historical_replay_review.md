# fx_soft_cap historical replay review

`fx_soft_cap_historical_replay` は、過去の週次 feature を使って current policy と diagnostic-only の `fx_soft_cap` を比較します。

- current final action は変更しない
- `fx_soft_cap` は diagnostic only
- adoption decision は安全側に `hold` を基本とする
- 13w / 26w の評価可能件数が不足する場合は採用判断しない
- excess return と max drawdown を確認する

初期版は完全な当時レポート再構成ではありません。価格履歴から作った週次 feature により、FX caution / headwind と市場候補条件が揃う疑似ケースを抽出します。採用判断に使う前に、実 watchlist と照合して過剰適合を避けます。
