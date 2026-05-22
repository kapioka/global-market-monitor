# buy_candidate near-miss review

`buy_candidate` が0件でも、実装失敗とは限りません。条件未達か、履歴内に候補局面が少ない可能性があります。

## 使い方

```powershell
python -m project.buy_candidate_near_miss
```

出力:

- `project/reports/buy_candidate_near_miss.json`
- `project/reports/buy_candidate_near_miss.md`

## 読み方

near-miss は、`buy_candidate` 条件のうち1〜2条件だけ不足した履歴です。

主な不足条件を見てから、将来 `buy_candidate` 条件を見直すか判断します。現時点では条件を緩めません。

FX policy 候補ごとに near-miss が `buy_candidate` へ変わるかは `python -m project.fx_policy_replay` で確認します。
