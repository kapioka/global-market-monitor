from __future__ import annotations

from project.alerts import build_alerts


def test_build_alerts_emits_market_and_life_alerts():
    regime = {
        "regime_label": "credit_stress",
        "credit_regime_flag": "credit_stress_severe",
        "inflation_regime_flag": "stagflation_warning",
    }
    spot_signal = {"risk_off_relief_applied": False, "second_leg_risk": "high"}
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
    assert "crash_caution" in ids
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



def test_build_alerts_does_not_emit_crash_caution_when_second_leg_risk_is_not_high():
    regime = {
        "regime_label": "inflation_shock",
        "credit_regime_flag": "neutral",
        "inflation_regime_flag": "inflation_shock_broad",
    }
    spot_signal = {"risk_off_relief_applied": False, "second_leg_risk": "moderate"}

    alerts = build_alerts(regime, spot_signal, [], [{"ticker": "CL=F", "signal_label": "インフレ圧力上昇"}, {"ticker": "DX-Y.NYB", "signal_label": "ドル高進行"}])
    ids = {alert["id"] for alert in alerts}

    assert "crash_caution" not in ids


def test_build_alerts_marks_strict_judgement_unavailable_when_core_indicators_missing():
    regime = {
        "regime_label": "inflation_shock",
        "credit_regime_flag": "neutral",
        "inflation_regime_flag": "inflation_shock_broad",
    }
    spot_signal = {"risk_off_relief_applied": False, "second_leg_risk": "moderate"}
    risk_lines = {
        "stage_key": "caution",
        "strict_judgement_available": False,
        "strict_missing_indicators": ["^VIX", "^MOVE"],
    }

    alerts = build_alerts(regime, spot_signal, [], [], risk_lines=risk_lines)
    ids = {alert["id"] for alert in alerts}

    assert "strict_judgement_unavailable" in ids


def test_build_alerts_include_usdjpy_based_japan_risk():
    alerts = build_alerts(
        {"regime_label": "transition"},
        {"second_leg_risk": "moderate"},
        [],
        [],
        japan_risk={
            "level": "high",
            "flags": ["fx_shock", "yen_weakness", "foreign_asset_fx_dependency"],
            "usd_jpy": {"signal_label": "円安急進"},
        },
    )
    ids = {alert["id"] for alert in alerts}

    assert "yen_weakness_living_cost_pressure" in ids
    assert "foreign_asset_fx_dependency" in ids
