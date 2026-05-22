from __future__ import annotations

from project.market_regime_classifier import classify_market_regime


def test_market_regime_classifier_detects_rate_shock() -> None:
    payload = classify_market_regime(
        {
            "feature_snapshot": {
                "tnx_change_4w": 0.12,
                "acwi_return_13w": -0.02,
                "vix_level": 27.0,
                "hyg_lqd_ratio_return_4w": -0.02,
            }
        }
    )

    assert payload["regime"] == "rate_shock"
    assert "rates" in payload["stress_families"]


def test_market_regime_classifier_detects_recovery() -> None:
    payload = classify_market_regime(
        {
            "feature_snapshot": {
                "acwi_return_13w": 0.08,
                "acwi_return_4w": 0.03,
                "spy_return_13w": 0.05,
                "acwi_drawdown_13w": -0.02,
                "vix_level": 16.0,
                "vix_change_4w": -0.10,
                "hyg_lqd_ratio_return_4w": 0.01,
            }
        }
    )

    assert payload["regime"] == "recovery"
    assert payload["regime_confidence"] == "high"
