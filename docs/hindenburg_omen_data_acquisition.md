# Hindenburg Omen データ取得・CSV作成ガイド

Hindenburg Omen は任意の補助表示です。`final_action`、買い候補度、メインリスク判定には影響しません。

## 位置づけ

- built-in の自動取得 provider は実験的です。Barchart、MarketWatch、WSJ などの公開ページは構造や利用条件が変わるため、取得失敗はアプリ本体の故障ではありません。
- Hindenburg Omen の算出には指数価格だけではなく、NYSE の市場幅データが必要です。
- データがない状態、不十分な履歴、provider 取得失敗は、いずれも `点灯なし` ではありません。
- 1日分のレコードに、複数サイトから集めた値を混ぜないでください。必須値は同一 provider / 同一ページ / 同一 market date から揃えてください。
- 公開ページ、表示名、利用条件は変わる可能性があります。ログイン、購読、CAPTCHA、ブラウザ検証、非公開 endpoint、hidden token の回避は使わないでください。
- データソースの利用可否と利用条件の確認は利用者の責任です。

## 必須値

| 日本語ラベル | CSV列 |
| --- | --- |
| 日付 | `date` |
| 新52週高値数 / 新高値 | `new_highs` |
| 新52週安値数 / 新安値 | `new_lows` |
| 値上がり銘柄数 | `advancers` |
| 値下がり銘柄数 | `decliners` |

## 任意だが有用な値

| 日本語ラベル | CSV列 | 用途 |
| --- | --- | --- |
| 対象銘柄数 | `total_issues` | 高値・安値比率の分母を明示 |
| NYSE指数 | `nyse_index` | 上昇トレンド判定の補助 |
| 50日前指数 | `index_50d_ago` | 上昇トレンド判定の補助 |
| McClellan Oscillator | `mcclellan_oscillator` | 条件判定。未入力時は39営業日以上の履歴から内部算出 |
| メモ | `source_note` | データ取得元や確認メモ |

## 正準CSV形式

正準CSVの列は次の順です。

```csv
date,new_highs,new_lows,advancers,decliners,total_issues,nyse_index,index_50d_ago,mcclellan_oscillator,source_note
```

必須列:

- `date`
- `new_highs`
- `new_lows`
- `advancers`
- `decliners`

任意列:

- `total_issues`
- `nyse_index`
- `index_50d_ago`
- `mcclellan_oscillator`
- `source_note`

形式:

- `date` は `YYYY-MM-DD`
- 件数列は0以上の整数
- 指数・McClellanは数値
- 文字コードは UTF-8
- 完成CSVの既定パスは `project/manual_sources/hindenburg_breadth.csv`

有効例:

```csv
date,new_highs,new_lows,advancers,decliners,total_issues,nyse_index,index_50d_ago,mcclellan_oscillator,source_note
2026-01-02,80,75,1200,1200,2600,10000,9800,-5,manual-confirmed
```

無効例:

```csv
date,new_highs,new_lows,advancers,decliners,source_note
2026/01/02,80,75,1200,1200,bad date
2026-01-03,-1,75,1200,1200,negative value
2026-01-04,80,75,1200,1200,EXAMPLE_DO_NOT_IMPORT sample only
```

## 空テンプレートを作る

```powershell
python -m project.hindenburg_manual create-template --output project/manual_sources/hindenburg_breadth.csv
```

既存ファイルを上書きする場合だけ `--overwrite` を付けます。

## 手元CSVを正準形式へ変換する

日本語または英語の一般的な列名を含むCSVを、アプリの正準CSVへ変換できます。ネットワーク取得、スクレイピング、ブラウザ操作は行いません。

```powershell
python -m project.hindenburg_manual normalize-csv --input path/to/source.csv --output project/manual_sources/hindenburg_breadth.csv
```

上書きする場合:

```powershell
python -m project.hindenburg_manual normalize-csv --input path/to/source.csv --output project/manual_sources/hindenburg_breadth.csv --overwrite
```

対応する主な列名:

- `日付`, `date`, `market_date` -> `date`
- `新高値`, `新52週高値`, `new_highs`, `highs` -> `new_highs`
- `新安値`, `新52週安値`, `new_lows`, `lows` -> `new_lows`
- `値上がり`, `値上がり銘柄数`, `advancers`, `advancing` -> `advancers`
- `値下がり`, `値下がり銘柄数`, `decliners`, `declining` -> `decliners`
- `対象銘柄数`, `total_issues`, `issues` -> `total_issues`
- `NYSE指数`, `nyse_index` -> `nyse_index`
- `50日前指数`, `index_50d_ago` -> `index_50d_ago`
- `McClellan`, `mcclellan_oscillator` -> `mcclellan_oscillator`
- `メモ`, `source_note` -> `source_note`

## 初期39営業日履歴を作る

1. 同一データソースから、少なくとも39営業日分の `date`, `new_highs`, `new_lows`, `advancers`, `decliners` を集めます。
2. 可能であれば `total_issues`, `nyse_index`, `index_50d_ago`, `mcclellan_oscillator`, `source_note` も入力します。
3. `normalize-csv` で `project/manual_sources/hindenburg_breadth.csv` に変換します。
4. 通常のレポート生成を実行すると、手動CSVからブートストラップされます。

39営業日未満、または上昇トレンド判定・McClellan 判定に必要な履歴が不足する場合、表示は不十分な履歴または未確認になります。これは `点灯なし` ではありません。

## 1日分を追加する

SQLite状態へ1日分を直接追加する場合は既存CLIを使います。

```powershell
python -m project.hindenburg_manual daily-input --date 2026-01-02 --new-highs 80 --new-lows 75 --advancers 1200 --decliners 1200 --total-issues 2600 --nyse-index 10000 --index-50d-ago 9800 --source-note manual-confirmed
```

CSVファイルへ追記したい場合は、同じ列順で1行追加してから通常のレポート生成または取り込みを実行してください。

## 表示状態の読み分け

- no data: CSVがなく、providerも成立していない状態。判定不能です。
- insufficient history: 必須値はあるが、履歴や補助値が不足している状態。点灯なしではありません。
- provider acquisition failure: 実験的自動取得が成立しなかった状態。前回確定値があれば保持されます。
- confirmed no trigger: 必要条件が揃ったうえで、最新日が点灯条件を満たさなかった状態です。

## 最終対応モード

- automatic built-in providers: 実験的。失敗しても安全に取得不可表示へ落ちます。
- configured static CSV URL: 対応済み。
- local manual CSV: 対応済み。
- manual daily input: 対応済み。
- converter utility: 対応済み。
- previous confirmed value preservation: 対応済み。
- no-data と insufficient-history は `点灯なし` として扱いません。
