# Global Market Monitor

Global Market Monitor は、相場の流れを毎週まとめて確認するための Python アプリです。

株式、セクター、債券、コモディティ、為替などをまとめて見て、
「今の市場は強いのか、弱いのか」「追加投資は急がなくていいのか」を、
レポートとダッシュボードで分かりやすく確認できるようにしています。

このアプリは、未来を予測するためのものではありません。
判断を急がず、見落としを減らすための補助ツールとして作っています。

## できること

- 複数の市場データをまとめて取得する
- 市場の地合いを判定する
- 危険ライン監視を相対指標ベースで確認する
- 危険ラインしきい値の再校正 proposal を定期的に見直す
- セクターごとの強弱を見る
- USD/JPY と外貨資産の円建てリスクを見る
- 追加投資のタイミングを補助的に判断する
- HTML / Markdown レポートを自動生成する
- 補足ダッシュボードで履歴、判定、セクター、市場監視、監査を切り替えて確認する
- 過去価格の backfill / replay で diagnostic-only の FX soft-cap 候補を検証する
- Buy Decision Card で final / raw / risk-adjusted の違い、買い候補度、主な阻害要因、次に見る条件を確認する

## v0.7.2 Buy Decision Clarity

v0.7.2 は、買い判断を緩める版ではありません。正式判断は引き続き `final_action` です。

- Buy Decision Card で、final / raw / risk-adjusted の違いを短く確認できます
- `buy_readiness_score` は説明用で、成功確率・期待リターン・投資成功率ではありません
- next review conditions / `unlock_conditions` は次に確認する条件であり、自動買い条件ではありません
- `fx_soft_cap` / regime-aware FX candidates は diagnostic-only / hold のままです
- TimesFM は通常機能に含めていません

## v0.7.3 Release / Operation Hardening

v0.7.3 は、GitHub公開後の運用安定性と配布手順を固める版です。投資判断ロジック、`final_action`、`reliability_policy`、active/proposed threshold JSON、`buy_window` / `buy_candidate` の閾値は変更しません。

- GitHub Actions CI で pytest / ruff / black --check / mypy / 依存監査 / security audit を確認します
- source-only の配布アーカイブを作るスクリプトを追加しています
- 生成済みレポート、cache、runtime log、release作業フォルダは配布物やコミット対象から除外します
- security audit はローカルとCIの両方で使えるようにしています

## v0.8.1 Report UI Redesign Plan

v0.8.1 は、`report.html` 上段の表示設計を整理するドキュメント版です。`まず見る要約` と `Buy Decision Card / 買い判断カード` を、初心者が最初に確認しやすい `まず見るポイント` と5ステップ式の `買い判断カード` へ分ける方針をまとめています。

- 方針文書は `docs/report_ui_redesign_plan_v0.8.1.md` です
- v0.8.1 では `project/report_generator.py` の実装変更はしません
- 判定ロジック、`final_action`、`buy_readiness_score`、threshold JSON、`reliability_policy` は変更しません
- 英語・内部用語は上段から外し、日本語の表示ラベルに寄せる方針です
- 実装は v0.8.2 以降で、まずHTML/CSS中心に進めます

## こんな人向けです

- 毎週の相場チェックを手作業でやっていて時間がかかる人
- セクターの流れや市場全体の強弱をまとめて見たい人
- 感覚だけではなく、一定のルールで市場を確認したい人
- 日本円ベースで外貨資産や為替リスクも確認したい人

## はじめ方

### 3分で確認する最短手順

```powershell
python -m pip install -r project/requirements.txt
python project/main.py --sample-only
```

`--sample-only` は、表示や処理の流れを確認するためのサンプル実行です。実データの市場判断ではありません。sample-only の結果で `buy_window` や `buy_candidate` を投資判断として扱わないでください。

README参照用の最小サンプルは `docs/sample/sample_report_summary.json` に置いています。このファイルは synthetic fixture であり、実データや個人情報を含めません。

### 1. 必要なもの

- Windows
- Python 3.11 以上
- インターネット接続

### 2. ライブラリを入れる

```bash
python -m pip install -r project/requirements.txt
```

再現性を優先する場合は、現在の検証済み環境から作った lock file も使えます。

```bash
python -m pip install -r project/requirements-lock.txt
```

`requirements-lock.txt` は、作成環境での再現性を優先した固定依存です。Windows / Python バージョン / 手元環境の影響を受けるため、別OSや別Python minor versionでは `requirements.txt` の方が安定する場合があります。通常は `requirements.txt`、同じ環境を再現したいときは `requirements-lock.txt` を使ってください。

依存関係の脆弱性監査では、CUDA ローカルビルド表記の pin が PyPI の解決条件と合わない場合があります。その場合は監査不能項目を分離して、残りの pinned dependencies を監査します。

```powershell
.\scripts\audit_python_dependencies.ps1
```

このスクリプトは `.tmp\pip-audit\requirements-lock.pip-audit.txt` を生成し、`torch==2.8.0+cu129` のようなローカルビルド表記は `.tmp\pip-audit\requirements-lock.pip-audit-excluded.md` に理由付きで記録します。除外分は脆弱性なしという意味ではなく、配布元に合わせて別途確認する監査不能項目です。

### CI / security audit / release package

ローカルで公開前に近い確認をする場合は、次を使います。

```powershell
python -m pytest
python -m ruff check .
python -m black --check .
python -m mypy .
.\scripts\security_audit.ps1 -ExpectedTag "" -Strict
python scripts/create_release_package.py --dry-run
```

配布用の source-only archive を作る場合は、作業ツリーが clean な状態で実行します。

```powershell
python scripts/create_release_package.py
```

配布アーカイブには manifest が入り、commit、tag、含めたファイル、除外ルールを確認できます。`project/reports/`、`project/cache/`、`.tmp/`、`release/`、`github_upload/` などの生成物・作業フォルダは含めません。

GitHub公開前は、詳細な確認表として `docs/github_publish_readiness_checklist.md` を使ってください。CI、security audit、release package manifest、forbidden entries、generated/cache除外、threshold JSON非変更、判定ロジック非変更を確認します。公開前運用全体の責務分担は `docs/pre_publish_integration_review_v0.7.11.md`、最終dry-runの確認表は `docs/github_publish_final_dry_run_v0.7.12.md` にまとめています。公開後の初回運用基準は `docs/post_publish_operation_baseline_v0.8.0.md` にまとめています。

### Historical replay

`fx_soft_cap` は final action には採用せず、historical replay と watchlist で検証します。

```powershell
python -m project.historical_price_backfill --start 2024-01-01 --end 2026-05-21 --output project/cache/historical_prices.csv
python -m project.historical_feature_builder --input project/cache/historical_prices.csv --output project/cache/historical_features.csv
python -m project.fx_soft_cap_historical_replay --features project/cache/historical_features.csv
```

`project/cache` と generated reports は原則コミットしません。threshold JSON と final action policy はこの replay では変更しません。

Python が複数入っている場合は、次でも動きます。

```bash
py -3 -m pip install -r project/requirements.txt
```

### 3. 実行する

```bash
python project/main.py
```

または Windows では次でも実行できます。

```powershell
.\run_main.bat
```

初回は、しきい値の確認や履歴の再構成に数分かかることがあります。

実行が終わると、次のファイルが作られます。

- `project/reports/report.html`
- `project/reports/report.md`
- `project/reports/report_summary.json`
- `project/reports/supplement_dashboard.html`
- `project/reports/history_dashboard.html`

## 主な見方

### 最新レポート

`report.html` では、最新の市場状態を1回分まとめて確認できます。

- 今の市場レジーム
- 合成スコア
- スポット投資判断
- 危険ライン監視
- しきい値 review 状況
- セクターの流れ
- 円建て・為替リスク
- 資産クラス比較

### 補足ダッシュボード

`supplement_dashboard.html` では、補足レポートの情報を5つの画面に分けて確認できます。

- 履歴
- 判定
- セクター
- 市場監視
- 監査

最新レポートでは全体感を確認し、補足ダッシュボードでは根拠や履歴を深く見る、という使い方を想定しています。

### データ品質ガード

取得データの品質が低いときに強い判断が出ないよう、データ信頼性ポリシーを入れています。

- サンプルデータだけの実行は診断用として扱う
- sample fallback が混ざった日は `buy_window` を出さない
- 重要系列が欠損した日は `buy_window` を出さない
- live 取得率が低い日は confidence と action を安全側に制限する
- レポートには live ratio、fallback 件数、action cap、cap reason を表示する

`buy_window` は購入指示ではありません。市場状態を見直す候補日という意味であり、データ品質ガードで `watch` や `wait` に降格されることがあります。

### Buy Decision Card

Buy Decision Card は、買い判断を強めるための仕組みではなく、判断の内訳を読みやすくするための表示です。

- `final` は正式判断です
- `raw` はリスク調整前の見え方です
- `risk_adjusted` はデータ品質やリスク要因を反映した見え方です
- `buy_readiness_score` は説明用スコアで、成功確率や期待リターンではありません
- `primary_blockers` は、候補化を妨げている主な要因です
- `next_review_conditions` / `unlock_conditions` は、次に確認する条件であり、自動買い条件ではありません

### 履歴ダッシュボード

`history_dashboard.html` では、過去の実行結果を時系列で見返せます。

- 過去から現在までの変化を見る
- レポート1回分では見えにくい変化を追う
- 同じ基準で履歴を確認する

## 補足ダッシュボードだけ再生成する

既存の `project/reports/report_summary.json` と履歴データから、補足ダッシュボードだけを再生成できます。

```powershell
.\scripts\render_supplement_dashboard.ps1
```

## 表示確認

Playwright CLI が使える環境では、補足ダッシュボードの5画面をスクリーンショットで確認できます。

```powershell
.\scripts\verify_supplement_dashboard.ps1
```

確認用の画像は `docs/visual-evidence/` に作られます。
このフォルダは Git 管理の対象外です。

## v0.7.0 の主な追加点

- データの取得に失敗したり、サンプルデータが混ざったりした日は、強い判断を出さないようにしました。
- 過去に出した `buy_window`、`watch`、`wait` のあと、市場がどう動いたかを4週、13週、26週、52週で確認できるようにしました。
- 新しい危険ライン候補をすぐ実運用に入れず、過去データで試してから判断できるようにしました。
- レポート上で「実際の判断に使っている閾値」と「検証中の閾値」を分けて表示するようにしました。
- 検証中の閾値は、全体をまとめて採用するのではなく、項目ごとに根拠を確認できるようにしました。
- v0.7.0 では、検証中の閾値や候補ルールは最終判断に自動では使いません。
- 実運用の判断は、これまでの active threshold とデータ品質チェックを中心にしています。
- 根拠が弱い暫定値は、診断用として表示するだけで、最終判断には使わないようにしました。
- 現在の履歴では `buy_window` の件数が少ないため、買い場判定の精度はまだ十分に評価できないことを明記しました。
- 原油やVIXなど一部の指標だけで警戒が強くなりすぎていないか、あとから確認しやすくしました。

## v0.6.0 の主な追加点（過去版）

- 補足レポートを、履歴、判定、セクター、市場監視、監査の5画面ダッシュボードとして再設計
- `report.html` から補足ダッシュボードへ移動しやすい導線を追加
- 最新レポートの上部ダッシュボードを整理し、主要判断を見やすく改善
- セクターローテーション図、候補表、危険ライン監視、市場監視の表示を調整
- レポート本文内の英語ラベルを日本語へ寄せ、確認時の読みやすさを改善
- データ品質が悪い日に `buy_window` を出さない reliability policy を追加
- sample-only、sample fallback、重要系列欠損、live ratio 低下時の action / confidence 制限を整理
- レポートと補足ダッシュボードに data quality guard の状態を表示
- `main.py` から pipeline、snapshot、backfill、report runtime を分離
- 判定理由の attribution と action validation の土台を追加
- 検証結果の読み方と限界を文書化
- GitHub公開用に、生成済みレポート、ログ、キャッシュ、ローカルメモを除外した公開パッケージを整理

## v0.5.0 の主な追加点

- 日本人が円建てで見るための `USDJPY=X` 監視を追加
- 米国株、海外株、金、債券、REIT などの外貨資産を円建てリターンで確認できるように改善
- 外貨資産の上昇が、資産本体の上昇なのか、円安による見かけ上の押し上げなのかを分けて表示
- 円安急進、円高急進、為替寄与依存などを alert / spot signal / report / dashboard に反映
- サンプルデータ実行でも円建てリスクの表示を確認できるようにテストを追加

## 注意点

- 投資判断を保証するものではありません
- 売買判断の自動化エンジンではありません
- `buy_window` は購入指示ではなく、追加確認の候補状態です
- `buy_candidate` は買い場候補であり、買い指示ではありません
- `buy_readiness_score` は成功確率ではありません
- sample-only の結果は実データによる判断ではありません
- generated files、cache、runtime logs、配布作業フォルダはコミットしません

## よくある誤解

- `buy_window` が出たら買う、という意味ではありません。確認候補日の表示です。
- `buy_candidate` は注文や売買指示ではありません。
- `buy_readiness_score` が高いほど利益が出る、という意味ではありません。
- sample-only の結果は、実運用判断の根拠にはなりません。
- `fx_soft_cap` / regime-aware FX candidates は検証用で、正式判断には採用していません。
- `buy_readiness_score` は成功確率・期待リターン・投資成功率ではありません。買い判断に近い条件の揃い具合を示す説明用スコアです
- unlock_conditions は「次に確認する条件」であり、自動買い条件ではありません
- raw / risk-adjusted / final action を分けて、強い判定がどこで弱まったかを確認できます
- `fx_soft_cap` は診断専用です。final action には影響せず、為替リスクありの買い候補を検証するために使います。
- データ取得元の都合で、一時的に取得に失敗することがあります
- 実データ取得に失敗した場合は、サンプルデータへフォールバックする設計が一部入っています
- サンプルデータや重要系列の欠損がある場合は、強い判断を出さないように制限します
- 過去検証は追加中ですが、すべての市場局面で有効性を保証するものではありません
- 生成済みレポート、ログ、キャッシュは公開版には含めていません

## 検収チェックリスト

- sample-only で起動できる
- live 取得失敗時に report が生成される
- データ品質不足時に `buy_window` が出ない
- critical ticker 欠損時に action が制限される
- action validation が実行できる
- config 不備時に分かりやすいエラーが出る
- pytest が通る
- ruff / black の確認方法がある

## 開発時の確認

開発用ツールを入れる場合:

```bash
python -m pip install -r project/requirements-dev.txt
```

通常確認:

```bash
python -m compileall -q project
python -m pytest
python project/main.py --sample-only
python project/run_action_validation.py
```

品質ツール:

```bash
python -m ruff check .
python -m black --check .
python -m mypy project/reliability_policy.py project/action_validation.py project/config_loader.py project/config_schema.py
```

mypy は段階導入です。現時点では `reliability_policy.py`、`action_validation.py`、`config_loader.py`、`config_schema.py` を対象にします。

## 詳しい説明

セットアップ、出力ファイル、補足ダッシュボード、検証手順などの詳細は、[project/README.md](project/README.md) を見てください。

検証の読み方と限界は、[docs/validation_limits.md](docs/validation_limits.md) にまとめています。

## 公開ポリシー

この公開版には、次のようなローカル専用データは含めていません。

- ログ
- キャッシュ
- 生成済みレポート
- スクリーンショット
- 個人用メモ
- 手元環境向けの内部メモ
- ローカル実行環境の秘密情報
