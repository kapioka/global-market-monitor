# fx_soft_cap outcome analysis

`fx_soft_cap_outcome_analysis` は、一律 `fx_soft_cap` の historical replay 結果を分類別に分解します。

- `overblocked_by_current`: 現行 policy が慎重すぎた可能性
- `correctly_blocked`: 現行 policy のブロックが妥当だった可能性
- `promising_candidate`: 悪くないが決定打不足
- `inconclusive`: future data または条件不足

見る項目は、risk stage、reliability、score band、FX flags、VIX、credit proxy、USDJPY change、13w excess return、13w max drawdown です。この分析は条件付き `fx_soft_cap` 候補を作るための診断であり、final action には影響しません。
