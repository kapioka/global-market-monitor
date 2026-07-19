# 危険察知・補助指標ロジック評価用メモ

作成日: 2026-06-20

対象レポート: `project/reports/report.html`

実データスナップショット: `project/reports/history/report_2026-06-20_191759.json`

データソース: `mixed`
目的: ChatGPT など外部レビューに、使用指標、計算ロジック、実際の表示結果、設計上の制約をまとめて評価してもらうための資料。

## 1. この資料で評価してほしいこと

- 危険察知に使っている指標の組み合わせが妥当か。
- VIX、MOVE、米10年、原油、ドル、信用、SPY、ゴールドの役割分担が過不足ないか。
- ゴールドを「インフレ確認」および「暴落前の安全資産選好確認」に使う現在の条件が妥当か。
- 単独シグナルで過剰に危険判定を上げない設計が妥当か。
- しきい値、総合ストレス指数、表示文言が投資判断の説明として誤解を生みにくいか。

注意: このシステムは買い推奨を出すものではなく、追加投資判断の補助レポートである。`final_action` や本番しきい値 JSON は保護対象で、今回のゴールド追加では変更していない。

## 2. 現在の最終表示結果

2026-06-20 19:17:59 の実データレポートでは以下。

| 項目 | 結果 |
| --- | --- |
| 最終判断 | `監視継続` |
| 買い候補度 | `40` |
| 危険ライン段階 | `通常` |
| 総合ストレス指数 | `10.79` |
| 厳密性 | `厳密判定可` |
| 不足指標 | `なし` |
| 警戒 / 危険 / 非常に危険 | `0 / 0 / 0` |
| 危険ライン decision_level | `none` |
| 危険ライン decision_flags | `[]` |
| 主なアラート | `外貨資産の為替依存` |
| 補助確認のゴールド表示 | `金 / 中立 / レジーム補助` |

危険ラインの要約:

> 主要指標はまだ危険ラインの手前で、強い複合ストレスは確認されていません。

判断カードの主な阻害要因:

- `fx_risk`: 外貨建て資産の為替依存、国内投資家目線の為替リスク。
- `score_shortfall`: total score `0.6085` が買いしきい値 `0.65` を下回る。

## 3. 使用している主要指標

### 3.1 危険ライン監視の必須指標

`project/risk_lines.py` の `REQUIRED_INDICATORS`:

| ティッカー | 役割 |
| --- | --- |
| `SPY` | 米国大型株の下落・回復確認 |
| `HYG` | ハイイールド債の単独状態 |
| `LQD` | 投資適格社債の単独状態 |
| `HYG/LQD` | 信用リスク、リスク選好の相対確認 |
| `^VIX` | 株式ボラティリティ、急落警戒 |
| `^MOVE` | 債券市場ボラティリティ |
| `CL=F` | WTI 原油、インフレ・供給ショック確認 |
| `BZ=F` | Brent 原油、原油ショック確認 |
| `DX-Y.NYB` | 米ドル指数、ドル高ストレス・外貨環境 |
| `^TNX` | 米10年金利、金利ショック確認 |

### 3.2 厳密判定に必須のコア指標

`STRICT_CORE_INDICATORS`:

`SPY`, `HYG/LQD`, `^VIX`, `^MOVE`, `BZ=F`, `^TNX`, `DX-Y.NYB`

今回の実データでは、コア指標はすべて取得済みで `厳密判定可`。

### 3.3 インフレ・レジーム補助指標

`inflation_monitor` に含まれる系列:

| ティッカー | 日本語名 | 現在値 | 1週 | 4週 | 12週 | zscore | signal_label |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `CL=F` | WTI原油先物 | 76.54 | 0.0000 | -0.1239 | -0.3138 | 0.2655 | インフレ圧力鈍化 |
| `GC=F` | 金先物 | 4172.8999 | 0.0000 | -0.0850 | -0.1029 | -0.1219 | 中立 |
| `DX-Y.NYB` | 米ドル指数 | 100.849 | 0.0000 | 0.0196 | 0.0082 | 2.2260 | 中立 |
| `ZW=F` | 小麦先物 | 605.75 | 0.0000 | -0.0078 | 0.0125 | 1.2741 | 中立 |
| `ZC=F` | トウモロコシ先物 | 417.5 | 0.0000 | -0.0655 | -0.0768 | -0.5207 | 食品価格圧力鈍化 |
| `FRED:MORTGAGE30US` | 米30年固定住宅ローン金利 | 6.47 | 0.0000 | -0.0092 | 0.0015 | 0.6804 | 中立 |
| `^TNX` | 米10年金利 | 4.487 | 0.0000 | 0.0076 | 0.0403 | 1.5167 | 中立 |

### 3.4 信用監視指標

| ティッカー | 日本語名 | 現在値 | 1週 | 4週 | 12週 | zscore | signal_label |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `HYG` | 米国ハイイールド債ETF | 80.01 | 0.0000 | 0.0014 | 0.0161 | 1.5041 | 中立 |
| `LQD` | 米国投資適格社債ETF | 109.07 | 0.0000 | 0.0011 | 0.0073 | 0.8624 | 中立 |
| `HYG/LQD` | ハイイールド債/投資適格債 比率 | 0.7336 | 0.0000 | 0.0002 | 0.0088 | 1.2260 | 信用温度差を監視 |

## 4. 危険ラインの特徴量計算

`project/stress_monitor.py` の `_build_feature_values()` で、各時系列から以下を作る。

| 特徴量 | 意味 |
| --- | --- |
| `current` | 最新値 |
| `change_1w` | 短期窓の変化率 |
| `change_4w` | 中期窓の変化率 |
| `change_12w` | 長期窓の変化率 |
| `level_zscore` | 水準のローリング z-score |
| `level_percentile` | 水準のローリング百分位 |
| `drawdown_13w` | 13週ドローダウン |
| `roc_1w`, `roc_2w`, `roc_4w`, `roc_8w` | 1/2/4/8週の変化率 |
| `roc_z_1w`, `roc_z_2w`, `roc_z_4w`, `roc_z_8w` | 変化率のローリング z-score |
| `drawdown_zscore` | 13週ドローダウンの z-score |

複合特徴量:

- VIX、MOVE、金利、原油、ゴールド、為替など上昇がストレスになりやすい系列:
  - `level_and_roc_4w = max(level_percentile, 正規化した roc_z_4w)`
  - `level_and_roc_8w = max(level_percentile, 正規化した roc_z_8w)`
- `HYG/LQD`:
  - `level_and_roc_4w = max(低水準ストレス, 低下方向の roc_z_4w ストレス)`
  - `level_and_roc_8w = max(低水準ストレス, 低下方向の roc_z_8w ストレス)`
- 株式・債券 ETF など下落がストレスになりやすい系列:
  - `drawdown_and_roc_4w = max(ドローダウン悪化, 4週変化率悪化)`
  - `level_and_roc_8w = max(低水準ストレス, 8週変化率悪化)`

## 5. 危険ラインの段階判定

各指標ごとに `warning`, `danger`, `extreme` のしきい値ルールを持つ。
判定は `extreme -> danger -> warning` の順に確認し、以下を満たした最上位段階を採用する。

- 該当特徴量がしきい値を超えている。
- そのしきい値が `allowed_for_stage=True`。
- `fallback_review` など診断専用ルールは、本判定の段階上げには使わない。

`pressure_score` は、各指標の現在値が危険方向へどの程度近いかを 0.0-1.0 で表す補助スコア。
総合ストレス指数は以下。

```text
composite_risk_score = weighted_average(pressure_score, weight) * 100
```

実装上の重要修正:

- `pressure_score=0.0` を欠損扱いして `0.5` にしてしまうと、正常指標が中立 50 点扱いになる。
- 現在は `None` のみを欠損扱いし、`0.0` は正しく 0 点として扱う。

## 6. 危険ライン全体の段階ロジック

`project/risk_lines.py` の `evaluate_risk_lines()` で以下の順に段階を決める。

### 6.1 extreme_line

以下のいずれか:

- `composite_risk_score >= 78`
- `extreme` 指標が 2 本以上
- VIX の危険・非常に危険が継続
- `HYG/LQD` が extreme かつ VIX danger かつ MOVE danger
- `credit_stress_severe` かつ VIX/MOVE extreme かつ原油 danger

### 6.2 danger_line

以下のいずれか:

- `composite_risk_score >= 62`
- `danger` 指標が 3 本以上
- VIX danger が継続
- VIX danger かつ米10年 danger かつ原油 danger
- `HYG/LQD` danger かつ VIX または MOVE danger

### 6.3 credit_spillover_initial

以下をすべて満たす:

- VIX warning
- 米10年 warning
- SPY warning
- `HYG/LQD` warning または信用レジームが moderate/severe
- 原油 warning、DXY warning、ゴールド安全資産選好、またはインフレレジーム悪化

意味: 金利・株安・信用・インフレ/ドル/ゴールドのどれかが同時に悪化し、信用波及の入口に見える状態。

### 6.4 caution

以下のいずれか:

- `composite_risk_score >= 35`
- warning 指標が 3 本以上
- VIX warning かつ SPY warning
- 米10年 warning かつ原油 warning
- ゴールドのインフレ確認フラグ
- ゴールドの暴落前確認フラグ

### 6.5 normal

上記に該当しない場合。

## 7. ゴールド利用ロジック

### 7.1 目的

ゴールドは以下の2用途で使う。

1. インフレ・通貨不安・原油ストレスの確認材料。
2. 株安・信用不安・VIX上昇と同時に起きる安全資産選好、つまり暴落前の防御シグナル確認。

単独では危険ラインを上げない。
理由: ゴールドはインフレ、実質金利、ドル、地政学、中央銀行需要など複数要因で動くため、単独上昇を市場危機と断定すると誤検知が増える。

### 7.2 ゴールド安全資産選好の定義

対象行:

- `GC=F`
- 代替として `GLD`
- 代替として `IAU`

条件:

```text
gold_safe_haven =
    signal_label == "安全資産選好"
    OR (change_1w >= 0.02 AND zscore >= 1.0)
```

### 7.3 インフレ確認フラグ

```text
gold_inflation_confirmation =
    gold_safe_haven
    AND (
        oil_warning
        OR DXY warning
        OR inflation_regime_flag in {
            inflation_shock_broad,
            inflation_shock_oil_only,
            stagflation_warning
        }
    )
```

意味: ゴールド上昇が、原油・ドル・インフレレジーム悪化と同時に出ている場合だけ、インフレ/通貨不安系の確認材料とする。

### 7.4 暴落前確認フラグ

```text
gold_crash_confirmation =
    gold_safe_haven
    AND (
        VIX warning
        OR SPY warning
        OR HYG/LQD warning
        OR credit_regime_flag in {
            credit_stress_moderate,
            credit_stress_severe
        }
    )
```

意味: ゴールド上昇が、VIX上昇・株安・信用悪化と同時に出ている場合だけ、暴落前の防御シグナルとして確認する。

### 7.5 現在の実データでのゴールド判定

| 項目 | 値 |
| --- | --- |
| ティッカー | `GC=F` |
| 現在値 | `4172.8999` |
| 1週変化 | `0.0000` |
| 4週変化 | `-0.0850` |
| 12週変化 | `-0.1029` |
| zscore | `-0.1219` |
| signal_label | `中立` |
| gold_safe_haven | `False` |
| gold_inflation_confirmation | `False` |
| gold_crash_confirmation | `False` |
| HTML表示 | `金 / 中立 / レジーム補助` |

## 8. 実データの危険ライン各指標結果

| 指標 | 現在値 | 段階 | pressure_score | 主なしきい値証拠 |
| --- | ---: | --- | ---: | --- |
| SPY | 746.74 | 通常 | 0.1412 | warning: `drawdown_13w=-0.010332 > -0.024156` で未到達 |
| HYG | 80.01 | 通常 | 0.0000 | warning: `drawdown_13w=0.0 > -0.009923` で未到達 |
| LQD | 109.07 | 通常 | 0.0180 | warning: `drawdown_13w=-0.001158 > -0.021275` で未到達 |
| HYG/LQD | 0.7336 | 通常 | 0.1022 | warning: `level_percentile=0.956731`, direction lower, threshold `0.548077` で未到達 |
| VIX | 16.4 | 通常 | 0.1523 | warning: `level_zscore=-0.459563 < 0.289384` で未到達 |
| MOVE | 69.36 | 通常 | 0.0689 | warning: `roc_8w=-0.014913 < 0.082386` で未到達 |
| WTI原油 | 76.54 | 通常 | 0.0000 | warning: `roc_8w=-0.249166 < 0.095138` で未到達 |
| Brent原油 | 80.59 | 通常 | 0.0000 | warning: `roc_z_1w=-0.082054 < 0.566310` で未到達 |
| DXY | 100.849 | 通常 | 0.2659 | warning: `level_percentile=0.629808 < 0.781731` で未到達 |
| 米10年 | 4.487 | 通常 | 0.3200 | warning: `level_percentile=0.860577 < 0.875000` で未到達 |

特に WTI 原油について:

- 現在値は `76.54`。
- warning 判定に使う特徴量は `roc_8w`。
- 実測 `roc_8w=-0.249166`。
- warning しきい値 `0.095138`。
- direction は `higher` なので、`-0.249166 >= 0.095138` ではない。
- よって WTI の危険度 `0/100` は現在の計算上は妥当。

## 9. レポート上の表示

### 9.1 HTML の主要表示

- 危険ラインパネル:
  - `通常 / 総合ストレス指数 10.7900`
  - `厳密判定可`
  - 不足指標なし
- 補助確認:
  - セクションチップ: `リスク文脈 / 単独判断には不使用`
  - ゴールド: `金 / 中立 / レジーム補助`
- 判断とリスク文脈:
  - 本体判断: `最終判断: 監視継続 / 買い候補度: 40`
  - グローバル危険ライン: `通常 / 総合ストレス指数 10.7900`
  - アラート: `外貨資産の為替依存`

### 9.2 開発補助情報の扱い

通常 HTML からは、以下の開発者向けパネルを非表示にしている。

- `しきい値レビュー`
- `しきい値提案`
- `しきい値利用方針`
- `しきい値ルール認証`

ただし、Markdown や内部 JSON には診断用情報として残している。
理由: 一般のレポート読者にはノイズだが、開発者がロジックを検証するには必要なため。

## 10. しきい値の採用方針

`threshold_usage` の実データ:

| 項目 | 値 |
| --- | --- |
| operational_set | `active` |
| diagnostic_sets | `proposed`, `candidate_v2` |
| proposed_status | `hold` |
| candidate_v2_status | `diagnostic_only` |
| currently_affects_final_action | `False` |
| active_thresholds_changed | `False` |
| eligible_for_final_action | `False` |

ブロック理由:

> Proposed/candidate thresholds lack completed forward-return evidence and overblock watch cases.

意味:

- 提案中・候補版しきい値は診断用。
- 本番判断や `final_action` には未採用。
- 採用には、将来リターン検証と過剰ブロック確認が必要。

## 11. 現在の設計上の意図

### 良い点として狙っていること

- VIX や原油など単独指標の急変だけで過剰反応しない。
- 信用、金利、株式、原油、ドル、ゴールドが同時に悪化する場合を強く見る。
- ゴールドは危険の「主役」ではなく、確認材料として使う。
- 診断専用しきい値は表示・検証には使うが、本番判定には使わない。
- `pressure_score=0.0` を正しく 0 として扱い、正常指標を中立 50 点にしない。

### 弱点・レビューしてほしい点

- ゴールド安全資産選好の条件 `1週変化 >= 2% AND zscore >= 1.0` は妥当か。
- ゴールドを `caution` へ反映するのは、他指標と重なる場合だけで十分か。
- `credit_spillover_initial` の条件に `gold_safe_haven` を入れるのは妥当か。
- 総合ストレス指数のしきい値 `35 / 62 / 78` は、説明用として適切か。
- 米10年の pressure_score が `0.3200` とやや高いが warning 未満という表示は直感的か。
- `HYG/LQD` の direction lower と level_percentile の組み合わせは、読者に説明しやすいか。
- `fallback_review` を完全に本判定から外す方針は保守的すぎないか。

## 12. 評価時に見てほしいソースファイル

- `project/risk_lines.py`
  - 危険ライン全体判定、ゴールド統合、総合ストレス指数。
- `project/stress_monitor.py`
  - 各指標の特徴量、しきい値証拠、pressure score。
- `project/report_generator.py`
  - HTML/Markdown の表示。
- `project/reports/history/report_2026-06-20_191759.json`
  - 今回の実データ結果。
- `project/reports/report.html`
  - 実際にユーザーが見る表示。

## 13. 評価用の短い質問文

外部レビューに投げる場合は、以下のように聞くとよい。

> 添付の追加投資確認レポートでは、VIX、MOVE、SPY、HYG/LQD、HYG、LQD、米10年、原油、DXY、ゴールドを使って危険ラインを判定しています。ゴールドは単独で危険判定を上げず、原油・DXY・インフレレジーム、または VIX・SPY・信用ストレスと重なった場合だけ確認材料にしています。この設計、しきい値、表示結果に過剰検知や見落としのリスクがないか、投資判断補助レポートとしてレビューしてください。
