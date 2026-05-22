# conditional fx_soft_cap replay review

`fx_conditional_soft_cap_replay` は、一律 `fx_soft_cap` ではなく条件付き候補を比較します。

候補:

- `normal_high_reliability`
- `normal_or_caution_no_credit_stress`
- `score_gap_limited`
- `combined_conservative`

比較する指標:

- buy_candidate count
- overblocked_by_current count
- correctly_blocked count
- promising_candidate count
- 13w / 26w return
- 13w excess return
- worst max drawdown
- missed candidate count

初期判断は安全側です。`combined_conservative` が良く見えても、final action には採用せず、current watchlist の future data と合わせて確認します。

条件付き候補でも worst DD が残る場合は、`fx_soft_cap_dd_guard_replay` で equity trend、volatility、credit、drawdown context の guard 候補を比較します。
