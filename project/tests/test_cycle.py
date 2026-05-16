from __future__ import annotations

import numpy as np
import pandas as pd

from project.cycle_analysis import analyze_cycle


def test_cycle_analysis_returns_expected_keys():
    values = 100 + np.sin(np.linspace(0, 8, 80)).cumsum()
    series = pd.Series(values)
    result = analyze_cycle(series)
    assert "phase_label" in result
    assert "signal_quality" in result
