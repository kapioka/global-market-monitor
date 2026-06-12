# Release Notes v0.9.0

v0.9.0 は、Hindenburg Omen を補助表示として使いやすくするためのリリースです。

この機能は売買判断を自動化するものではありません。`final_action`、買い候補度、メインリスク判定には影響しません。

## v0.9.0 の主な追加点

- Hindenburg Omenを補助表示として追加・整理しました。
- 自動取得は実験的で、取得できない場合があります。
- 自動取得できない場合でもアプリ全体は壊れません。
- 手動CSVで市場幅データを取り込めます。
- CSVテンプレートを用意しました。
- 日本語列名や英語列名を正準CSVへ整形するconverterを追加しました。
- 1日分の手入力CLIを追加しました。
- SQLiteで前回確定値を保持します。
- 取得不可、履歴不足、入力不正、点灯なしを区別します。
- Hindenburg Omenは売買判断には使いません。

## 使う人が注意すること

- 投資判断を保証しません。
- Hindenburg Omenだけで判断しないでください。
- データが未取得の状態を「点灯なし」と見なさないでください。
- 異なるサイトの数値を1日分に混ぜないでください。
- データ取得元の利用条件は利用者側で確認してください。

## 手動データを使う場合

空のCSVを作る:

```powershell
python -m project.hindenburg_manual create-template --output project/manual_sources/hindenburg_breadth.csv
```

手元CSVをアプリ用の形式に整える:

```powershell
python -m project.hindenburg_manual normalize-csv --input path/to/source.csv --output project/manual_sources/hindenburg_breadth.csv
```

1日分だけ手入力する:

```powershell
python -m project.hindenburg_manual daily-input --date 2026-01-02 --new-highs 80 --new-lows 75 --advancers 1200 --decliners 1200 --total-issues 2600 --nyse-index 10000 --index-50d-ago 9800 --source-note manual-confirmed
```

詳しい手順は `docs/hindenburg_omen_data_acquisition.md` と `docs/hindenburg_omen_manual_input.md` を見てください。
