# Global Market Monitor 詳細ガイド

このファイルは、Global Market Monitor の詳しい使い方をまとめた説明書です。

「まず動かしてみたい」という場合は、先に [../README.md](../README.md) を読んでください。

## このアプリがやること

このアプリは、複数の市場データをまとめて取り込み、毎週の市場状態を整理してレポート化します。

見る対象は主に次のようなものです。

- 世界株と米国株
- セクター ETF
- 債券と信用市場
- 金、原油、ドルなどのマクロ関連指標
- ボラティリティや金利などのリスク指標
- USD/JPY と外貨資産の円建てリスク

その上で、

- 市場全体の地合い
- 直近のサイクル状態
- 日本人が円建てで見たときの為替リスク
- 追加投資を急ぐべきかどうか
- どのセクターに資金が向かっているか

を、ひとつのレポートにまとめます。

v0.7.0 では、データ品質ガード、action validation、threshold replay、rule-level threshold certification を安全層として統合しています。

- reliability policy により、データ品質が悪い日は `buy_window` を出さず `watch` / `wait` 側へ制限
- action validation で過去 action の 4週、13週、26週、52週リターンを確認
- threshold historical replay で active / proposed / candidate_v2 を比較
- threshold certainty / threshold usage で、どの threshold set が final action に関係するかを明示
- rule-level threshold certification で、`indicator:threshold_type` 単位の将来採用候補を診断
- proposed / candidate / rule certification は final action に自動反映しない
- active threshold は実運用値、fallback_review は診断のみ

v0.7.x では、`fx_soft_cap` を diagnostic-only として追跡します。

- `fx_soft_cap` は final action には影響しない
- `Buy Decision Card` / `buy_readiness_score` / `unlock_conditions` は説明用で、final action には影響しない
- watchlist で current cases の future data を追跡
- historical backfill / replay で過去類似ケースを補助検証
- replay 結果だけで threshold JSON や final action policy を変更しない

v0.6.0 では、補足レポートを5画面の補足ダッシュボードとして再設計しています。

- 履歴、判定、セクター、市場監視、監査を画面切り替えで確認
- 最新レポートから補足ダッシュボードへ移動しやすい導線を追加
- セクターローテーション図、候補表、危険ライン監視、市場監視の表示を整理
- 英語ラベルをできるだけ日本語へ寄せ、確認時の読みやすさを改善

v0.5.0 では、特に日本人向けの円建てリスク管理を追加しています。

- `USDJPY=X` の急変を監視し、円安急進、円高急進、円安進行、円高進行を判定
- 外貨資産のドル建てリターン、円建てリターン、為替寄与を分けて表示
- 為替寄与に依存した上昇や、円高による円建て評価額の悪化を alert / spot signal / report に反映
- 履歴ダッシュボードでも円建てリスクの状態を確認できるように更新

v0.4.0 では、特に危険ライン監視を見直しています。

- 固定絶対値に寄りすぎないよう、`drawdown`、`roc`、`percentile`、`z-score` を使った相対化を導入
- しきい値を `active` と `proposed` に分け、再校正候補を差分で確認できるように整理
- drift 監視と再校正 proposal 自動生成を追加し、見直し忘れを減らす構成に変更

## ファイル構成

主に見るファイルは次のとおりです。

- `main.py`
  - 実行の入口です
- `config.yaml`
  - ティッカー、重み、しきい値、出力先をまとめた設定ファイルです
- `pipeline.py`
  - データ取得からレポート用 payload 構築までの流れをまとめます
- `reliability_policy.py`
  - データ品質が悪い日の action と confidence の上限を決めます
- `snapshot_store.py`
  - snapshot の保存、読込、backfill 用の補助処理を扱います
- `report_generator.py`
  - レポート HTML / Markdown を作ります
- `history_dashboard.py`
  - 履歴ダッシュボードと補足ダッシュボード HTML を作ります
- `render_supplement_dashboard.py`
  - 既存のレポート要約と履歴から、補足ダッシュボードだけを再生成します
- `stress_monitor.py`
  - 危険ライン監視の判定を行います
- `japan_risk_monitor.py`
  - USD/JPY と外貨資産の円建てリスクを確認します
- `risk_line_thresholds_active.json`
  - 現在採用中の危険ライン基準です
- `risk_line_thresholds_proposed.json`
  - 再校正で提案された検証候補です。v0.7.0 では final action へ直接使いません
- `threshold_historical_replay.py`
  - active / proposed / candidate threshold を過去履歴で比較します
- `threshold_metadata.py`, `threshold_candidate_policy.py`, `threshold_certainty.py`, `threshold_decision_policy.py`
  - threshold の confidence、candidate_v2、certification、final action への利用可否を管理します
- `threshold_rule_identity.py`, `threshold_rule_evidence.py`, `threshold_rule_certification.py`
  - proposed threshold を rule 単位で評価し、future eligible / diagnostic only / reject などに分類します
- `threshold_rule_certification_report.py`
  - rule-level certification の JSON / Markdown レポートを生成します
- `run_risk_line_recalibration.py`
  - 再校正 proposal と diff レポートを生成します
- `action_validation.py`
  - 過去の action と価格系列から、4週、13週、26週、52週後のリターンを検証します
- `action_validation_report.py`
  - action validation の JSON / Markdown レポートを書き出します
- `tests/`
  - テストコードです

## セットアップ

### 必要なもの

- Windows
- Python 3.11 以上

### インストール

```bash
python -m pip install -r project/requirements.txt
```

Python の呼び出し方が環境によって違う場合は、次でも構いません。

```bash
py -3 -m pip install -r project/requirements.txt
```

再現性を優先して、現在の検証済み環境に近い依存でそろえる場合は lock file を使います。

```bash
python -m pip install -r project/requirements-lock.txt
```

`requirements-lock.txt` は、作成環境での再現性を優先した固定依存です。Windows / Python バージョン / 手元環境の影響を受けるため、別OSや別Python minor versionでは `requirements.txt` の方が安定する場合があります。通常は `requirements.txt`、同じ環境を再現したいときは `requirements-lock.txt` を使ってください。

### 依存関係の脆弱性監査

`pip-audit` で lock file を監査するとき、CUDA ローカルビルド表記の pin が PyPI の解決条件と合わず、監査前の dry-run 解決で止まることがあります。その場合は、監査不能項目を分離して残りの pinned dependencies を監査します。

```powershell
.\scripts\audit_python_dependencies.ps1
```

生成される主なファイル:

- `.tmp\pip-audit\requirements-lock.pip-audit.txt`
  - `pip-audit --no-deps` に渡す監査可能な requirements
- `.tmp\pip-audit\requirements-lock.pip-audit-excluded.md`
  - `torch==2.8.0+cu129` など、PyPI 既定 index では解決できないローカルビルド表記の除外理由

除外分は「脆弱性なし」ではありません。配布元や実際のインストール元に合わせて別途確認する監査不能項目です。

## 実行方法

### 通常実行

```bash
python project/main.py
```

### 補足ダッシュボードだけ再生成

既存の `project/reports/report_summary.json` と `project/reports/history/` から、`project/reports/supplement_dashboard.html` だけを再生成します。

```powershell
.\scripts\render_supplement_dashboard.ps1
```

Python を明示する場合:

```powershell
.\scripts\render_supplement_dashboard.ps1 -Python py
```

### 補足ダッシュボードの表示検証

主要5画面のスクリーンショットを `docs/visual-evidence/` に出力し、最低限のHTML要素が存在することを確認します。

```powershell
.\scripts\verify_supplement_dashboard.ps1
```

この検証は既存の `npx` / Playwright CLI と、Playwright 管理の bundled Chromium を使います。Playwright やブラウザが使えない場合は、再インストールやPATH変更を自動で繰り返さず停止します。既存のChromeで代替したい場合だけ `-Channel chrome` を指定します。

### サンプルデータだけで試す

```bash
python project/main.py --sample-only
```

`--sample-only` は表示や診断の確認用です。通常の投資判断表示としては扱わず、最終 action は安全側に制限されます。

### スケジュール実行

```bash
python project/main.py --schedule
```

`--schedule` を使うと、`config.yaml` の時刻設定に従って日次実行します。

## 出力されるもの

### 最新レポート

- `project/reports/report.html`
- `project/reports/report.md`
- `project/reports/report_summary.json`
- `project/reports/history_dashboard.html`
- `project/reports/supplement_dashboard.html`

### 履歴

- `project/reports/history/report_YYYY-MM-DD_HHMMSS.md`
- `project/reports/history/report_YYYY-MM-DD_HHMMSS.html`
- `project/reports/history/report_YYYY-MM-DD_HHMMSS.json`

## 何を見ればよいか

### まず見るもの

初心者なら、まずは `report.html` を開いてください。

最初に見るとよい項目は次の3つです。

- 市場レジーム
- 合成スコア
- 危険ライン監視
- 円建て・為替リスク
- スポット投資判断

そのあとで、必要に応じて

- セクターローテーション
- 資産クラス比較
- 信用市場の補助情報

を見る流れが分かりやすいです。

### 補足ダッシュボードの役割

`supplement_dashboard.html` は、最新レポートの詳細確認用画面です。

- 履歴
- 判定
- セクター
- 市場監視
- 監査

を切り替えて確認できます。

最新レポートで全体感を見て、補足ダッシュボードで判定理由や監査情報を確認する流れを想定しています。

### 履歴ダッシュボードの役割

`history_dashboard.html` は、過去の変化を見るための画面です。

- 以前より強くなっているか
- 以前より弱くなっているか
- 一時的な動きなのか、継続しているのか

を見たいときに使います。

### 危険ラインの見方

危険ラインは、単純な価格水準だけではなく、相対化した特徴量も使って判定します。

- `warning`
  - 注意段階です
- `danger`
  - 実害リスクが高まりやすい段階です
- `threshold review status`
  - しきい値自体の見直しが必要かどうかを示します

`threshold review status` が `review` のときは、再校正 proposal が生成されている可能性があります。`project/reports/` 配下の diff レポートを確認してください。

### threshold certification の見方

v0.7.0 では、危険ラインの値を次の役割に分けます。

- active: 実運用で final action に使う基準
- proposed: 検証候補
- candidate_v2: family cap、multi-family extreme、stage jump limiter を試す診断候補
- certified: 将来、十分な根拠を満たした場合だけ final action に影響できる候補

`fallback_review`、`not_evaluable`、`low confidence` の値は final action から隔離します。`buy_window` が0件の期間では、buy_window の誤判定防止性能は評価できません。

rule-level certification は、`^VIX:warning` や `BZ=F:extreme` のような個別 rule ごとに判定します。v0.7.x では certified / conditional であっても自動的に final action へ入れず、将来採用候補として扱います。

### 円建て・為替リスクの見方

円建て・為替リスクでは、日本人が外貨資産を見るときに重要な USD/JPY と円建てリターンを確認します。

- `USDJPY=X`
  - 円安急進、円高急進、円安進行、円高進行などの為替状態を示します
- `円建てリターン`
  - 外貨資産を USD/JPY で換算したときのリターンです
- `為替寄与`
  - 円建てリターンのうち、為替がどれだけ押し上げ、または押し下げたかを示します

外貨資産が上がっていても、為替寄与が大きい場合は、資産本体の強さだけでなく円安の影響も含まれます。追加投資判断では、この状態を少し慎重に扱います。

### データ品質ガードの見方

レポートには、取得データの信頼性を確認するための項目があります。

- `live ratio`
  - 実データとして取得できた割合です
- `sample fallback`
  - サンプルデータで代替された件数です
- `proxy fallback`
  - 代替ティッカーなどで補完された件数です
- `unavailable`
  - 取得できなかった件数です
- `max action`
  - データ品質上、許可される最大 action です
- `confidence cap`
  - データ品質上の confidence 上限です
- `cap reason`
  - action や confidence が制限された理由です

たとえば、内部ロジックが `buy_window` を出しても、sample fallback や重要系列の欠損がある場合は `watch` または `wait` に降格されます。`buy_window` は購入指示ではなく、追加確認の候補状態です。

### 検証レポートの見方

action validation は、過去の `buy_window` / `watch` / `wait` と、その後の 4週、13週、26週、52週リターンを比較するための検証機能です。

先に、検証対象ベンチマークの価格 JSON を用意します。

```bash
python -m project.validation_price_export --ticker ACWI --output project/reports/validation_prices.json
```

その後、保存済み履歴と価格 JSON から `action_validation.json` と `action_validation.md` を生成します。

```bash
python -m project.run_action_validation
```

明示的に価格 JSON を指定する場合:

```bash
python -m project.run_action_validation --price-points-json project/reports/validation_prices.json
```

別ベンチマークとの excess return を確認する場合:

```bash
python -m project.validation_price_export --ticker ACWI --output project/reports/validation_prices_acwi.json
python -m project.validation_price_export --ticker SPY --output project/reports/validation_prices_spy.json
python -m project.run_action_validation --price-points-json project/reports/validation_prices_acwi.json --benchmark-price-points-json project/reports/validation_prices_spy.json
```

この exporter は sample fallback を使いません。代替ティッカーによる proxy fallback を検証データとして許可する場合だけ、明示的に `--allow-proxy` を指定します。

`project/reports/validation_prices.json` が存在しない場合、runner は `missing_price_points` を返します。その場合は exporter を先に実行するか、`--price-points-json` で別の価格 JSON を指定してください。

`--benchmark-price-points-json` を指定すると、`benchmark_returns` は別価格系列で計算し、`excess_returns` は対象リターンから benchmark リターンを差し引きます。指定しない場合は従来互換として、対象価格系列を benchmark として扱います。

出力される検証ファイル:

- `project/reports/action_validation.json`
- `project/reports/action_validation.md`
- `project/reports/action_validation_summary.json`
- `project/reports/action_validation_summary.csv`
- `project/reports/action_validation_summary.md`

価格 JSON は次の形式です。

```json
[
  {"date": "2026-01-02", "price": 100.0},
  {"date": "2026-04-06", "price": 106.2}
]
```

検証結果は、判断ロジックを保証するものではありません。局面ごとの弱点、件数不足、過剰適合の疑いを見つけるために使います。詳しい限界は [../docs/validation_limits.md](../docs/validation_limits.md) を確認してください。

## テスト

```bash
python -m pytest project/tests
```

## 配布パッケージを作る

Windows 向けの配布用ファイルは次で作れます。

```powershell
pwsh -File project/build_distribution.ps1
```

出力先:

- `release/GlobalMarketMonitor-win64/`
- `release/GlobalMarketMonitor-win64.zip`

## 公開版で含めないもの

このリポジトリでは、次のようなローカル専用ファイルは Git 管理の対象外にしています。

- `project/reports/`
- `project/logs/`
- `project/cache/`
- `project/sample_output/`
- 個人用の handoff メモや review メモ

## 補足

このアプリは、投資の正解を出すためのものではありません。
数字を並べて判断を固定するのではなく、「今どんな状態かを落ち着いて確認する」ための道具として使うのが前提です。
## buy_window sparsity diagnostics

`buy_window` が少ない場合は、閾値を直接緩めずに診断します。

```powershell
python -m project.buy_window_diagnostics
python -m project.buy_window_calibration
```

`buy_candidate` は `watch` と `buy_window` の中間ラベルです。買い推奨ではなく、買い場候補の確認用です。
