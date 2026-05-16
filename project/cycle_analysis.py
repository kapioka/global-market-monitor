from __future__ import annotations

import math

import numpy as np
import pandas as pd

try:
    from scipy.signal import hilbert
except Exception:  # pragma: no cover
    hilbert = None


def analyze_cycle(prices: pd.Series) -> dict[str, object]:
    clean = prices.dropna()
    if len(clean) < 32:
        return {
            "phase_label": "insufficient_data",
            "phase_angle_deg": float("nan"),
            "signal_quality": "low",
            "note": "Not enough weekly observations for cycle analysis.",
        }

    detrended = np.log(clean).diff().dropna()
    detrended = detrended - detrended.ewm(span=8).mean()
    values = detrended.to_numpy()

    if hilbert is None:
        phase = _fallback_phase(values)
    else:
        analytic = hilbert(values)
        phase = float(np.angle(analytic[-1]))

    phase_deg = math.degrees(phase)
    if -45 <= phase_deg < 45:
        label = "upswing"
    elif 45 <= phase_deg < 135:
        label = "late_cycle"
    elif -135 <= phase_deg < -45:
        label = "recovery"
    else:
        label = "downswing"

    return {
        "phase_label": label,
        "phase_angle_deg": round(phase_deg, 2),
        "signal_quality": "medium" if hilbert is None else "high",
        "note": "Hilbert transform unavailable; using smoothed momentum fallback."
        if hilbert is None
        else "Hilbert phase derived from weekly log returns after EMA detrending.",
    }


def _fallback_phase(values: np.ndarray) -> float:
    last = values[-8:]
    slope = np.polyfit(np.arange(len(last)), last, 1)[0]
    if slope > 0:
        return math.radians(15)
    return math.radians(165)
