# fx_soft_cap missed_good analysis

`fx_soft_cap_missed_good_analysis` は、`combined_dd_guard` が除外した `overblocked_by_current` ケースを確認する診断です。

確認する項目:

- 除外された日付
- guard reasons
- 13w / 26w return
- 13w excess return
- 13w max drawdown
- ACWI/SPY relative strength
- USDJPY change
- VIX level / change
- credit proxy
- rates proxy
- oil family change

目的は、deep DD を防ぎながら missed good を減らせるかを見ることです。final action には影響しません。
