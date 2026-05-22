# market regime classifier review

`market_regime_classifier.py` は historical features または replay case を軽量に分類する diagnostic helper。

初期分類:

- normal
- recovery
- risk_off
- rate_shock
- inflation_shock
- fx_stress
- credit_stress
- crash_or_drawdown
- uncertain

主な入力:

- ACWI / SPY trend
- ACWI drawdown
- VIX level / change
- TNX change
- HYG/LQD proxy
- USDJPY change
- oil family movement
- FX flags

この分類は final action には使わない。目的は、`fx_soft_cap` を一律に見るのではなく、rate shock や risk-off では block、normal/recovery では diagnostic buy_candidate 候補として比較するための前処理。
