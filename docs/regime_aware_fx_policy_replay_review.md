# regime-aware FX policy replay review

一律 `fx_soft_cap` は 2022 rate shock などで壊れやすいため、相場局面ごとに FX caution / headwind の扱いを変える候補を比較する。

比較対象:

- current
- fx_soft_cap
- combined_dd_guard
- without_equity_trend_guard
- recovery_only_soft_cap
- normal_recovery_soft_cap
- stress_block_soft_cap
- conservative_regime_aware
- regime_aware_with_dd_guard

評価項目:

- count
- overblocked_by_current
- correctly_blocked
- missed_good
- 13w / 26w excess return
- 13w / 26w worst DD
- regime breakdown

`candidate_for_future_adoption` はかなり厳しくする。2022 rate shock で壊れる、13w/26w excess が改善しない、DD だけ改善して missed_good が大きい、または候補が複雑すぎる場合は `hold`。

この replay は diagnostic-only であり、final action、reliability policy、threshold JSON は変更しない。
