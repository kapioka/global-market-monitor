# 2026-03-26 Sector Rotation Handoff

## 今日の到達点
- sector_vector_analysis の補助統合は維持したまま、internal_structure の抽象度と説明性を強化。
- internal_structure に 3 層を追加。
  - breadth
  - leadership
  - stability
- 補助影響に max_sector_adjustment を適用済み。
- 3週連続性チェックを追加済み。
- acceleration を追加済み。
- dispersion を追加済み。
- energy_dominance を single_sector_dominance へ一般化済み。
- dominance_strength を追加。
  - weak
  - medium
  - strong
- dominance penalty を regime / scoring / spot で regime 依存 + 強度依存に調整済み。
- internal_structure の閾値は absolute + ratio の併用へ変更済み。
- report_generator に以下を追加済み。
  - セクターローテーション内部構造
  - セクター分散指標
  - 内部構造3層
  - 単独主導セクター
  - 単独主導強度
  - 補助反映要約
- 補助反映要約は以下の改善済み。
  - cap より本質シグナルを優先表示
  - signal 名を日本語化
  - delta を固定小数化
  - regime / scoring / spot 見出しを日本語化

## 直近の安定状態
- 主判定は未変更。
- セクターは補助入力のみ。
- 既存 UI 主構造は未変更。
- report の説明力だけ上げている。
- 最新確認テスト
  - report subset: 11 passed
  - prior broader regression: 65 passed

## 今見えている改善案
### 優先度高
1. 補助反映要約の delta に「加点 / 減点」ラベルを追加
- 現状は `変化=+0.14`。
- 次は `加点 +0.14` / `減点 -0.01` のようにすると意味が一目で分かる。

2. dominance_strength の判定理由を 1 行で返す
- 例:
  - rank=1
  - active_count=1
  - low dispersion
- 現状は strength だけで、なぜ strong かが report からは分からない。

3. internal_structure の explain を report にもう少し自然文で出す
- 現状は構造化表示中心。
- breadth / leadership / stability を短い日本語文に変換すると読みやすい。

### 優先度中
4. dominance_strength を config 化
- 現状はロジック内の段階判定が固定。
- 境界値を config へ逃がすと調整しやすい。

5. broad / narrow の相対化をもう一段進める
- 今は absolute + ratio 併用。
- 次は top share ベースへ寄せる余地あり。

6. explain の優先順位ルールを共通化
- 現在は report_generator 側に優先ロジックあり。
- 将来的には explain 生成側と揃えると一貫性が上がる。

### 優先度低
7. HTML / Markdown で補助反映要約の見た目を少し整える
- 今は行ベース。
- badge 化や muted text 化で視認性を上げられる。

8. report の内部構造節に候補セクターとの対応を薄く追加
- 例: `次候補セクターは breadth 改善を補強` など。
- ただし長文化しないことが前提。

## 次回の最初の一手の推奨
- まず `加点 / 減点` ラベル追加。
- 次に `dominance_strength` の理由テキスト追加。
- この 2 つは表示改善だけで効果が大きく、既存ロジックを壊しにくい。

## 次回再開時の確認ポイント
- report_generator.py の補助反映要約まわりを起点に見る。
- sector_structure_summary.py の dominance_strength 算出を起点に見る。
- テストはまず以下を回す。
  - project/tests/test_report_generator.py
  - project/tests/test_main.py
- その後必要なら broader regression。

## 関連ファイル
- E:/作ってみた/追加投資確認/project/sector_structure_summary.py
- E:/作ってみた/追加投資確認/project/sector_rotation.py
- E:/作ってみた/追加投資確認/project/regime_analysis.py
- E:/作ってみた/追加投資確認/project/scoring.py
- E:/作ってみた/追加投資確認/project/spot_signal.py
- E:/作ってみた/追加投資確認/project/report_generator.py
- E:/作ってみた/追加投資確認/project/tests/test_sector_vector_analysis.py
- E:/作ってみた/追加投資確認/project/tests/test_regime_analysis.py
- E:/作ってみた/追加投資確認/project/tests/test_scoring.py
- E:/作ってみた/追加投資確認/project/tests/test_spot_signal.py
- E:/作ってみた/追加投資確認/project/tests/test_report_generator.py
- E:/作ってみた/追加投資確認/project/tests/test_main.py
# 2026-03-26 Follow-up Plan From ChatGPT Review

## レビュー要点
- ロジック追加より説明性強化を優先する。
- 補助レイヤー設計は妥当で、主判定維持・cap・フォールバック・explain 返却は良い。
- 単独主導リスクの扱いは概ね妥当。
- `dominance_strength` は内部根拠が曖昧になりやすいので、将来的には分解可能にする。
- `broad / narrow` は将来的に top share ベース相対化が有効。
- 直近で最も効くのは説明性の整備。

## 次回の改善テーマ
説明性強化を優先し、判定ロジックの大幅追加は後回しにする。

## 優先順位
### 1. 補助反映要約の `変化` を `加点 / 減点` 表示へ変更
目的
- 数値の意味を一目で分かるようにする。

実装方針
- `project/report_generator.py` の `_format_explain_entry()` を更新。
- `変化=+0.14` ではなく `加点=+0.14` / `減点=-0.01` に変換。
- 0 近辺は `変化=+0.00` のままでもよいが、まずは正負で分岐。

テスト
- `project/tests/test_report_generator.py` の期待値更新。

### 2. `dominance_strength` の理由を1行で返す
目的
- `weak / medium / strong` の意味を運用時に追えるようにする。

実装方針
- `project/sector_structure_summary.py` に内部説明用メタデータを追加。
- 最低限、以下を返す。
  - `dominance_reason_short`
  - `dominance_components`
- `dominance_components` 候補
  - `concentration`
  - `breadth_deficit`
  - `top_gap` or 暫定 proxy
- 初回は既存データで安全に出せる範囲に留める。
  - すでに持っている `active_count`, `dispersion_score`, `rank` から構成
  - `top_gap` は未計算なら `pending` 扱いでも可

表示方針
- レポートには 1 行だけ表示。
  - 例: `理由: 上位1セクター集中、裾野不足`
- 詳細は内部データに残す。

テスト
- `project/tests/test_sector_vector_analysis.py`
  - `dominance_strength` ごとの理由文確認
- `project/tests/test_report_generator.py`
  - 理由文の表示確認

### 3. `breadth / leadership / stability` の短文化
目的
- 3層構造を非技術ユーザーにも読める形にする。

実装方針
- `project/report_generator.py` に表示変換関数を追加。
- 例
  - `breadth=broad` → `裾野は広い`
  - `leadership=cyclical` → `景気敏感が主導`
  - `stability=accelerating` → `動きは加速`
- 元の raw 表記は残してもよいが、まずは日本語短文を併記。

テスト
- `project/tests/test_report_generator.py`

### 4. `stability` の内部2分割準備
目的
- 将来の説明性と保守性を上げる。

実装方針
- 表示は `stability` のまま維持。
- 内部的に以下を追加する設計を準備。
  - `consistency_state`
  - `momentum_quality_state`
- 次回は実装まで進めず、設計メモ or 軽い下地まででも可。

### 5. `dominance_strength` 境界の config 化
目的
- 調整容易性を上げる。

実装方針
- `project/config.yaml` に dominance 用しきい値候補を追加検討。
- ただし次回は説明性優先なので、余力があれば着手。

### 6. broad / narrow の top share 相対化
目的
- 将来のロジック安定性向上。

実装方針
- 説明性改善の後で着手。
- 先に設計メモだけ残す。

## 次回の実装順序
1. `加点 / 減点` 表示
2. `dominance_strength` 理由1行
3. 3層構造の短文化
4. 必要なら `stability` 内部分解の下地
5. 余力があれば config 化

## 次回の作業対象ファイル候補
- E:/作ってみた/追加投資確認/project/sector_structure_summary.py
- E:/作ってみた/追加投資確認/project/report_generator.py
- E:/作ってみた/追加投資確認/project/config.yaml
- E:/作ってみた/追加投資確認/project/tests/test_sector_vector_analysis.py
- E:/作ってみた/追加投資確認/project/tests/test_report_generator.py
- 必要なら E:/作ってみた/追加投資確認/project/tests/test_main.py

## 次回開始時の推奨テスト
- `C:\Python313\python.exe -m pytest project/tests/test_report_generator.py project/tests/test_sector_vector_analysis.py`
- 変更後に `project/tests/test_main.py` を追加
- 最後に必要なら広めの回帰

## すぐ使える次回の指示文
- 説明性強化を優先してください。
- 既存主判定は変えず、表示層と explain 層の差分実装で進めてください。
- まず `補助反映要約` の `変化` を `加点 / 減点` へ変更してください。
- 次に `dominance_strength` の理由を1行で返し、レポートに短く表示してください。
- 可能なら `breadth / leadership / stability` を短い日本語へ変換してください。
- 既存機能を壊さないことを最優先にしてください。

## 2026-03-27 説明性強化の進捗
- `補助反映要約` の delta 表示を `加点 / 減点 / 変化` に変更。
- `project/sector_structure_summary.py` に `dominance_reason_short` を追加。
- `project/report_generator.py` で以下を追加。
  - `内部構造要約`
  - `単独主導理由`
- `breadth / leadership / stability` を短い日本語文へ変換する表示関数を追加。
- focused regression:
  - `project/tests/test_report_generator.py`
  - `project/tests/test_sector_vector_analysis.py`
  - `project/tests/test_main.py`
  - 33 passed
- `dominance_components` を追加。
  - concentration
  - breadth_deficit
  - top_gap
- `dominance_reason_short` はこの内部要素を使って生成する形へ整理。
- focused regression: 33 passed
- `dominance_strength` の境界を config 化。
  - dominance_strong_active_max
  - dominance_strong_rank_max
  - dominance_medium_active_max
  - dominance_medium_dispersion_buffer_per_sector
- focused regression: 34 passed
- broad / narrow 判定へ top share 補助指標を追加。
  - watch_share
  - promising_share
  - broad_watch_share_threshold
  - broad_promising_share_threshold
  - narrow_promising_share_max
- focused regression: 35 passed

## 2026-03-27 説明性強化の追加進捗
- `補助反映要約` の delta 表示を `加点 / 減点 / 変化` に変更。
- `dominance_reason_short` を追加し、単独主導理由を 1 行で返すようにした。
- `breadth / leadership / stability` を短い日本語へ変換する表示を追加。
- `dominance_components` を追加。
  - concentration
  - breadth_deficit
  - top_gap
- `dominance_reason_short` は component ベースで生成する形へ整理。
- `dominance_strength` の境界を config 化。
  - dominance_strong_active_max
  - dominance_strong_rank_max
  - dominance_medium_active_max
  - dominance_medium_dispersion_buffer_per_sector
- broad / narrow 判定へ top share 補助指標を追加。
  - watch_share
  - promising_share
  - broad_watch_share_threshold
  - broad_promising_share_threshold
  - narrow_promising_share_max
- report の内部構造節に以下を追加・改善。
  - 内部構造要約
  - 単独主導理由
  - 単独主導内訳
  - 相対広がり指標
  - 相対広がり要約
  - stability内訳
- `internal_structure.reason` を自然文中心へ改善。
- `dominance_reason_short` を自然文中心へ改善。
- `stability内訳` も自然文中心へ改善。

### 現時点の次の候補
1. ここまでの変更をまとめて ChatGPT 再評価用の要約を更新する
2. focused regression だけでなく、広めの回帰を再実行する
3. 必要ならコミットを作る

### 現時点の確認テスト
- `project/tests/test_sector_vector_analysis.py`
- `project/tests/test_report_generator.py`
- `project/tests/test_main.py`
- focused regression は直近すべて pass
