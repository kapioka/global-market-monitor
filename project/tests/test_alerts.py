from __future__ import annotations

from project.alerts import build_alerts


def test_build_alerts_emits_market_and_life_alerts():
    regime = {
        "regime_label": "credit_stress",
        "credit_regime_flag": "credit_stress_severe",
        "inflation_regime_flag": "stagflation_warning",
    }
    spot_signal = {"risk_off_relief_applied": False}
    credit_monitor = [{"ticker": "HYG/LQD", "signal_label": "信用収縮警戒"}]
    inflation_monitor = [
        {"ticker": "CL=F", "signal_label": "インフレ圧力上昇"},
        {"ticker": "DX-Y.NYB", "signal_label": "ドル高進行"},
        {"ticker": "GC=F", "signal_label": "安全資産選好"},
        {"ticker": "ZW=F", "signal_label": "食品価格上昇圧力"},
        {"ticker": "FRED:MORTGAGE30US", "signal_label": "住宅ローン負担上昇"},
    ]

    alerts = build_alerts(regime, spot_signal, credit_monitor, inflation_monitor)
    ids = {alert["id"] for alert in alerts}

    assert "credit_stress_severe" in ids
    assert "stagflation_warning" in ids
    assert "purchasing_power_pressure" in ids
    assert "food_price_pressure" in ids
    assert "mortgage_burden_pressure" in ids
    assert "household_defense_warning" in ids
    assert "slowdown_warning" in ids
    assert "defense_priority" in ids


def test_build_alerts_emits_relief_and_recovery_notes():
    regime = {
        "regime_label": "early_recovery",
        "credit_regime_flag": "credit_improving",
        "inflation_regime_flag": "neutral",
    }
    spot_signal = {"risk_off_relief_applied": True}

    alerts = build_alerts(regime, spot_signal, [], [])
    ids = {alert["id"] for alert in alerts}

    assert "risk_off_relief_applied" in ids
    assert "credit_improving" in ids
    assert "early_recovery" in ids
