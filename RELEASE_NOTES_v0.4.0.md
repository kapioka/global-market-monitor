# v0.4.0 Release Notes

## 概要

v0.4.0 では、危険ライン監視の考え方を大きく見直しました。

今回の更新では、単に閾値を増やすのではなく、

- 実数値と見比べたときに納得しやすい基準にすること
- 時代による水準変化に追随しやすい形へ整理すること
- しきい値の見直し忘れを減らし、運用しやすくすること

を重視しています。

## 主な変更点

### 1. 危険ライン監視を再設計

- `SPY`、`HYG`、`LQD`、`HYG/LQD`、`^VIX`、`^MOVE`、`CL=F`、`BZ=F`、`DX-Y.NYB`、`^TNX` を対象に再評価
- 固定絶対値だけでなく、`drawdown`、`roc`、`percentile`、`z-score` を候補として比較
- 実数値と見比べて不自然な基準は採用せず、reality-check を通した基準だけを active に反映

### 2. 再校正フローを追加

- `active` と `proposed` のしきい値 JSON を分離
- recalibration proposal、diff、drift report を生成する runner を追加
- しきい値は自動では切り替えず、人が確認して apply する構成に整理

### 3. 見直し忘れを減らす review 通知を追加

- 実行時に drift を更新
- 一定期間経過、または drift review 発生時に proposal を自動生成
- report に `threshold review status` と `threshold review reasons` を表示

### 4. レポートの説明性を強化

- 危険ラインの warning / danger 判定を追いやすく改善
- しきい値 version と calibrated_at を表示
- 運用者が「今の判定」と「基準の見直し要否」を同時に確認できるよう整理

### 5. workspace を archive 優先で整理

- live 運用に不要な build 生成物、旧テスト出力、設計メモを archive へ退避
- 消すべきものと残すべきものを分けた上で、安全側で整理
- 公開版には internal cleanup 記録や archive 内容を含めない形へ整理

## このバージョンで改善されたこと

- 危険ライン判定が、以前より実数感覚とずれにくくなりました
- 指標水準の時代変化に対して、固定絶対値だけに依存しない形へ改善しました
- 再校正の proposal を忘れにくくなりました
- レポートから、しきい値の review 要否まで追えるようになりました

## 注意点

- しきい値 proposal は自動生成されますが、自動適用はしません
- `threshold review status` が `review` の場合は、diff レポート確認が前提です
- 一部の Windows 一時ディレクトリは ACL 制約で cleanup 対象外のまま残しています
- このアプリは投資判断を保証するものではありません

## 今後の予定

- review / drift の運用フローをさらに分かりやすく整理
- 必要に応じて apply フローの確認手順を README へ追加
- archive 済み領域と live 領域の整理を継続
