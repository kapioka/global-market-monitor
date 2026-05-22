# fx_soft_cap long-range guard replay

`without_equity_trend_guard` は短期の DD guard ablation では最有力候補だが、2024年以降だけで判断しない。

この replay は、2019年以降などの長期 price backfill から作った weekly features を使い、以下を diagnostic-only で比較する。

- current
- fx_soft_cap
- combined_dd_guard
- without_equity_trend_guard
- balanced_dd_guard

見る指標:

- count
- overblocked / correctly_blocked / promising_candidate
- missed_good
- 13w / 26w return
- 13w / 26w excess return
- worst DD
- regime breakdown

判断は安全側に置く。複数 regime で悪化しない、worst DD が改善する、excess return が悪化しない、correctly_blocked が増えすぎない、という条件が揃うまで adoption decision は `hold` とする。

この診断は final action には影響しない。
