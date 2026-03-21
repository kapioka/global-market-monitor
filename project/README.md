# Global Market Monitor

Windows 向けの Python 市場監視アプリです。予測装置ではなく、誤認回避のための判断補助ツールとして設計しています。実データ取得に失敗した場合でも、警告を残したうえでサンプルデータへフォールバックしてレポート生成を継続します。

## 構成

- `main.py`: 実行エントリポイントとスケジュール起動
- `config.yaml`: ティッカー、重み、しきい値、出力先、スケジュール設定
- `data_fetcher.py`: yfinance 取得、キャッシュ初期化、サンプルデータへのフォールバック
- `indicators.py`: ATR、ADX、drawdown、relative strength などの共通指標
- `regime_analysis.py`: 市場レジーム判定
- `cycle_analysis.py`: ヒルベルト位相ベースのサイクル判定
- `scoring.py`: 合成スコア計算
- `sector_rotation.py`: セクター順位比較
- `asset_compare.py`: 資産クラス比較
- `spot_signal.py`: スポット投資タイミング判定
- `analogue_search.py`: 類似局面検索
- `report_generator.py`: Markdown / HTML レポート生成と履歴保存
- `history_dashboard.py`: 履歴 JSON 集約とインタラクティブ `dashboard.html` 生成
- `scheduler.py`: 日次スケジューラ
- `tests/`: モック系列ベースの単体テスト

## セットアップ

```bash
python -m pip install -r project/requirements.txt
```

Windows で複数の Python が入っている場合は、`py -3 -m pip install -r project/requirements.txt` のように明示実行してください。

## 実行

通常実行:

```bash
python project/main.py
```

サンプルデータ固定実行:

```bash
python project/main.py --sample-only
```

日次スケジュール実行:

```bash
python project/main.py --schedule
```

`--schedule` は起動直後に 1 回実行し、その後は `config.yaml` の `scheduler.hour` / `scheduler.minute` に従って毎日実行します。PC が停止していた時間帯の取りこぼしは内蔵スケジューラーだけでは埋まらないため、通常起動時には `startup.max_backfill_days` の範囲で未生成日の履歴を穴埋めします。穴埋め時は日足を取得し、その日までの実データで週次判定を再計算します。

## 出力

最新ファイル:

- `project/reports/report.md`
- `project/reports/report.html`
- `project/reports/report_summary.json`
- `project/reports/dashboard.html`

履歴ファイル:

- `project/reports/history/report_YYYY-MM-DD_HHMMSS.md`
- `project/reports/history/report_YYYY-MM-DD_HHMMSS.html`
- `project/reports/history/report_YYYY-MM-DD_HHMMSS.json`

その他:

- `project/sample_output/report_sample.md`
- `project/sample_output/report_sample.html`
- `project/logs/app.log`
- `project/cache/`: yfinance のキャッシュ配置先

## ダッシュボード

`project/reports/dashboard.html` は履歴 JSON を束ねたインタラクティブビューです。

- スライダーで過去から現在までの時点を切替
- `再生` ボタンで履歴をアニメーション再生
- 合成スコア推移チャートの下にシークと主要指標をまとめ、時間操作と変化を同じ視野で確認
- 関係マップで `市場レジーム`、`合成スコア`、`サイクル判定`、`スポット判断`、`先導セクター`、`上位資産クラス`、`データ取得状況` のつながりを可視化
- ノードクリックで右側の詳細パネルが切り替わり、セクター、資産クラス、取得状況まで掘れる

## テスト

```bash
python -m pytest project/tests
```

## 配布パッケージ作成

Windows 向けの配布用 `exe` と ZIP は次で作成できます。

```powershell
pwsh -File project/build_distribution.ps1
```

出力先:

- `release/GlobalMarketMonitor-win64/`
- `release/GlobalMarketMonitor-win64.zip`

配布物には `GlobalMarketMonitor.exe` と `project/config.yaml` が含まれます。

## 公開時の前提

- このリポジトリにはローカルのログ、キャッシュ、レポート生成物を含めない想定です。
- `.gitignore` で `project/reports/`、`project/logs/`、`project/cache/`、`release/` などを除外しています。
- 個人環境の絶対パスや手元メモは公開用コピーから外しています。
