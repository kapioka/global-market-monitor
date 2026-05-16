# Release Notes v0.7.0

## 概要

v0.7.0 は、個人用の市場監視・追加投資判断補助ツールとして、安全側の最終判断、過去 action 検証、threshold replay、rule-level threshold certification を統合したリリースです。

final action は引き続き `active threshold + reliability policy` を基準にします。proposed / candidate_v2 / rule certification は diagnostic / future adoption only であり、明示的な別フェーズなしに final action へ自動反映しません。

## 主な変更

- reliability policy を最終 action の安全ガードとして整理
- sample-only、sample fallback、重要系列欠損、live ratio 低下時に action / confidence を安全側へ制限
- sample-only 実行では final action を `wait` 相当に制限
- action validation を 4週、13週、26週、52週の forward return 集計に拡張
- action validation summary の JSON / CSV / Markdown 出力を追加
- action validation の price-points JSON 不在時に `missing_price_points` を返すよう改善
- `threshold_historical_replay` の price-points JSON / history / market snapshot 不在時に、スタックトレースではなく status JSON を返すよう改善
- config schema validation を追加
- data quality report section を分離
- ruff / black / mypy を段階導入
- threshold historical replay tool を追加
- proposed threshold review result は `hold`
- active thresholds は変更なし
- threshold certification layer を追加
- proposed / candidate_v2 は certified されない限り final action から隔離
- candidate_v2 diagnostics と family cap / multi-family extreme / stage jump limiter を追加
- rule-level threshold certification を追加

## Rule-Level Certification

rule-level threshold certification は、proposed threshold 全体を一括採用せず、`indicator:threshold_type` 単位で証拠を評価するための診断層です。

現時点の確認結果:

- certified_count: 0
- conditional_count: 0
- diagnostic_only_count: 22
- not_evaluable_count: 8
- currently_affects_final_action: false

`fallback_review` は certified 禁止です。`buy_window` が0件のため、買い場誤判定防止性能はまだ評価できません。

## Threshold JSON の扱い

- `project/risk_line_thresholds_active.json`: 実運用で使用する閾値
- `project/risk_line_thresholds_proposed.json`: 検証候補
- proposed thresholds は historical replay で `hold` 判定
- proposed thresholds は手動で active にコピーしない
- v0.7.0 では active thresholds unchanged として扱う
- `threshold_usage.operational_set` は `active`
- `threshold_certainty.proposed.level` は現状 high ではない

## 確認済み

- `python -m compileall -q project`: exit 0
- `python -m pytest project/tests --basetemp .test_tmp_rule_certification`: 212 passed
- `python project/main.py --sample-only`: OK
- sample-only final action: `wait`
- sample-only policy reasons: `sample_only`
- `python -m project.validation_price_export`: 522 price points
- `python -m project.run_action_validation`: OK
- `python -m project.threshold_historical_replay`: OK / decision `hold`
- `python -m project.threshold_rule_certification_report`: OK
- `python -m ruff check .`: OK
- `python -m black --check .`: OK
- targeted mypy: OK

## 別作業として残すもの

- buy_window が出る局面を含む replay 比較
- 13w / 26w / 52w と最大DDの十分な比較
- rule-level certification で future eligible になった rule の明示的な採用判断
- 必要な場合のみ、partial adoption を別コミット化

## 注意点

action validation は履歴 67 件で動作確認済みですが、統計的に十分とは限りません。threshold historical replay では proposed が 7 件の `watch` をすべて `wait` に落とし、同じ 7 件で `normal` を `extreme_danger_line_reached` に変えました。これは過剰防御の可能性があるため、v0.7.0 では active threshold を維持します。
