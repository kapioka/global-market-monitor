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

その上で、

- 市場全体の地合い
- 直近のサイクル状態
- 追加投資を急ぐべきかどうか
- どのセクターに資金が向かっているか

を、ひとつのレポートにまとめます。

## ファイル構成

主に見るファイルは次のとおりです。

- `main.py`
  - 実行の入口です
- `config.yaml`
  - ティッカー、重み、しきい値、出力先をまとめた設定ファイルです
- `report_generator.py`
  - レポート HTML / Markdown を作ります
- `history_dashboard.py`
  - 履歴をまとめたダッシュボード HTML を作ります
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

## 実行方法

### 通常実行

```bash
python project/main.py
```

### サンプルデータだけで試す

```bash
python project/main.py --sample-only
```

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
- `project/reports/dashboard.html`

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
- スポット投資判断

そのあとで、必要に応じて

- セクターローテーション
- 資産クラス比較
- 信用市場の補助情報

を見る流れが分かりやすいです。

### ダッシュボードの役割

`dashboard.html` は、過去の変化を見るための画面です。

- 以前より強くなっているか
- 以前より弱くなっているか
- 一時的な動きなのか、継続しているのか

を見たいときに使います。

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
