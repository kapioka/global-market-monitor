from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SyntheticSpec:
    seed: int
    drift: float
    volatility: float


def build_sample_prices(length: int = 520) -> pd.DataFrame:
    index = pd.date_range(end=pd.Timestamp.today().normalize(), periods=length, freq="W")
    specs = {
        "ACWI": SyntheticSpec(seed=1, drift=0.0008, volatility=0.018),
        "VT": SyntheticSpec(seed=2, drift=0.00075, volatility=0.017),
        "SPY": SyntheticSpec(seed=3, drift=0.0010, volatility=0.02),
        "VEA": SyntheticSpec(seed=4, drift=0.00065, volatility=0.017),
        "VWO": SyntheticSpec(seed=5, drift=0.00055, volatility=0.022),
        "EWJ": SyntheticSpec(seed=6, drift=0.0005, volatility=0.019),
        "XLK": SyntheticSpec(seed=7, drift=0.0012, volatility=0.025),
        "XLF": SyntheticSpec(seed=8, drift=0.0007, volatility=0.021),
        "XLE": SyntheticSpec(seed=9, drift=0.00045, volatility=0.03),
        "XLV": SyntheticSpec(seed=10, drift=0.00065, volatility=0.014),
        "XLY": SyntheticSpec(seed=11, drift=0.00085, volatility=0.02),
        "XLP": SyntheticSpec(seed=12, drift=0.00035, volatility=0.011),
        "XLI": SyntheticSpec(seed=13, drift=0.00072, volatility=0.018),
        "XLB": SyntheticSpec(seed=14, drift=0.00068, volatility=0.022),
        "XLU": SyntheticSpec(seed=15, drift=0.0003, volatility=0.012),
        "XLRE": SyntheticSpec(seed=16, drift=0.0004, volatility=0.018),
        "GLD": SyntheticSpec(seed=17, drift=0.00045, volatility=0.013),
        "AGG": SyntheticSpec(seed=18, drift=0.00018, volatility=0.006),
        "TIP": SyntheticSpec(seed=19, drift=0.00022, volatility=0.007),
        "VNQ": SyntheticSpec(seed=20, drift=0.00048, volatility=0.019),
        "HYG": SyntheticSpec(seed=21, drift=0.00042, volatility=0.014),
        "LQD": SyntheticSpec(seed=22, drift=0.00024, volatility=0.008),
        "CL=F": SyntheticSpec(seed=23, drift=0.00065, volatility=0.04),
        "GC=F": SyntheticSpec(seed=24, drift=0.00035, volatility=0.018),
        "DX-Y.NYB": SyntheticSpec(seed=25, drift=0.0002, volatility=0.01),
        "ZW=F": SyntheticSpec(seed=26, drift=0.00042, volatility=0.028),
        "ZC=F": SyntheticSpec(seed=27, drift=0.00036, volatility=0.024),
        "FRED:MORTGAGE30US": SyntheticSpec(seed=28, drift=0.00018, volatility=0.011),
        "^TNX": SyntheticSpec(seed=29, drift=0.00016, volatility=0.012),
        "USDJPY=X": SyntheticSpec(seed=30, drift=0.00035, volatility=0.009),
        "1306.T": SyntheticSpec(seed=31, drift=0.0004, volatility=0.016),
        "^SOX": SyntheticSpec(seed=32, drift=0.00125, volatility=0.032),
        "SOXX": SyntheticSpec(seed=33, drift=0.00115, volatility=0.028),
    }

    data: dict[str, pd.Series] = {}
    for ticker, spec in specs.items():
        rng = np.random.default_rng(spec.seed)
        returns = rng.normal(spec.drift, spec.volatility, size=length)
        returns[-8:] += np.linspace(-0.01, 0.012, 8)
        prices = 100 * np.exp(np.cumsum(returns))
        data[ticker] = pd.Series(prices, index=index)
    return pd.DataFrame(data)
