# 検証結果の読み方と限界

この文書は、Global Market Monitor の判断表示を検証するときの前提と限界をまとめたものです。

## 前提

このツールは、売買判断を自動化するエンジンではありません。

目的は、週次で市場状態を確認し、判断を急がないための材料を整理することです。`buy_window`、`watch`、`wait` は、売買指示ではなく、確認優先度を表すラベルとして扱います。

## データ品質ガード

次バージョンでは、データ品質が悪い日に強い判断が出ないよう、`reliability_policy.py` で action と confidence に上限をかけます。

主なルールは次のとおりです。

- sample-only は診断用として扱う
- sample fallback が1件でもあれば `buy_window` を出さない
- 重要系列の欠損があれば `buy_window` を出さない
- live ratio が低い場合は action と confidence を安全側に制限する
- proxy fallback のみの場合も confidence を抑制する

このため、判定ロジック単体では `buy_window` でも、最終表示では `watch` や `wait` に降格されることがあります。レポート上では `raw_action`、最終 `action`、`max_action`、`confidence_cap`、`cap_reason` を確認できます。

## action validation の役割

`action_validation.py` は、過去の判断ラベルと価格系列を使い、判断後の 4週、13週、26週、52週リターンを集計するための基礎機能です。

確認したいことは次のとおりです。

- `buy_window` の後に、実際にリターンが改善していたか
- `watch` と `wait` に意味のある差があったか
- 2018、2020、2022、2024-2025 などの局面で誤判定が偏っていないか
- 重みやしきい値を変更しても判断が極端に崩れないか

現時点の action validation は、まず履歴と価格系列から再現可能な検証表を作る段階です。検証結果は、判断ロジックを正当化するものではなく、弱点や過剰適合を見つけるための材料として扱います。

保存済み履歴と価格 JSON がある場合は、次の runner で検証レポートを作れます。

```bash
python -m project.run_action_validation
```

`project/reports/validation_prices.json` 以外を使う場合は、`--price-points-json` で明示します。
別ベンチマークと比較する場合は、benchmark 側の価格 JSON も渡します。

```bash
python -m project.run_action_validation --price-points-json project/reports/validation_prices_acwi.json --benchmark-price-points-json project/reports/validation_prices_spy.json
```

価格 JSON は、次の exporter で作成できます。

```bash
python -m project.validation_price_export --ticker ACWI --output project/reports/validation_prices.json
```

exporter は sample fallback を使いません。proxy fallback を検証データとして許可する場合は、`--allow-proxy` を明示します。
価格 JSON が存在しない場合、runner は `missing_price_points` を返します。スタックトレースではなく、価格 JSON を先に作るための案内を表示します。

価格 JSON は、`[{"date": "YYYY-MM-DD", "price": 100.0}]` の配列、または `{"prices": [...]}` の形式を受け付けます。価格系列は、検証したい対象と比較したい benchmark に合わせて明示的に用意します。`--benchmark-price-points-json` を指定した場合、`benchmark_returns` は別系列から計算し、`excess_returns` は対象リターンから benchmark リターンを差し引いて出します。指定しない場合は従来互換として対象価格系列を benchmark として扱います。

## 現時点の限界

- 検証は、入力された履歴と価格系列の品質に依存します。
- 価格系列に欠損がある場合、指定 horizon 以後の最初に利用できる価格を使います。
- 4週、13週、26週、52週は日数ベースの近似です。
- 配当、税金、為替手数料、実際の約定価格は考慮しません。
- `diagnostic_only` は通常の判断検証から除外します。
- サンプルデータや proxy が混ざった履歴は、通常の live 判定と同じ意味では扱えません。
- 検証件数が少ない action は、平均リターンだけで判断しません。

## 公開時の表現方針

README やリリースノートでは、次の表現を守ります。

- `buy_window` は購入指示ではなく、追加確認の候補状態として説明する
- sample-only は診断用であり、投資判断の根拠にしない
- データ品質が悪い日は `buy_window` を抑制する
- 検証結果は参考情報であり、将来成績を保証しない
- 他人に売買判断を委ねる用途では使わない
