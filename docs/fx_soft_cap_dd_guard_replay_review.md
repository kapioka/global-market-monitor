# fx_soft_cap DD guard replay review

`fx_soft_cap_dd_guard_replay` は、`fx_soft_cap` に deep drawdown guard を追加した場合の診断比較です。

比較対象:

- current
- fx_soft_cap
- best conditional candidate
- equity_trend_guard
- volatility_guard
- credit_guard
- drawdown_context_guard
- combined_dd_guard

確認する指標:

- 13w worst DD が改善するか
- correctly_blocked が減るか
- overblocked_by_current を逃しすぎないか
- 13w mean excess が悪化しないか
- count が少なすぎないか

初期判断は `hold` を基本にします。`candidate_for_future_adoption` は、deep DD が明確に改善し、平均 excess と missed good candidate の代償が小さい場合だけ候補表示します。

`combined_dd_guard` が missed good を増やす場合は、`fx_soft_cap_missed_good_analysis` と `fx_soft_cap_guard_ablation` でどの guard が原因かを確認し、`balanced_dd_guard` を比較します。
