from __future__ import annotations

from project.risk_lines import evaluate_risk_lines


def test_risk_lines_marks_credit_spillover_initial_before_full_credit_break():
    regime = {
        "regime_label": "inflation_shock",
        "credit_regime_flag": "credit_stress_moderate",
        "inflation_regime_flag": "inflation_shock_broad",
    }
    cycle = {"phase_label": "downswing"}
    stress_monitor = [
        {"ticker": "^VIX", "ticker_name_ja": "VIX指数", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.48, "weight": 1.2},
        {"ticker": "^TNX", "ticker_name_ja": "米10年金利", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.45, "weight": 1.05},
        {"ticker": "CL=F", "ticker_name_ja": "WTI原油先物", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.5, "weight": 0.9},
        {"ticker": "SPY", "ticker_name_ja": "米国大型株ETF", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.44, "weight": 1.15},
        {"ticker": "HYG/LQD", "ticker_name_ja": "ハイイールド債/投資適格債 比率", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.46, "weight": 1.3},
    ]

    result = evaluate_risk_lines(regime, cycle, [], [], stress_monitor)

    assert result["stage_key"] == "credit_spillover_initial"
    assert "波及" in result["summary"]


def test_risk_lines_marks_extreme_when_credit_and_volatility_break_together():
    regime = {
        "regime_label": "credit_stress",
        "credit_regime_flag": "credit_stress_severe",
        "inflation_regime_flag": "inflation_shock_broad",
    }
    cycle = {"phase_label": "downswing"}
    stress_monitor = [
        {"ticker": "^VIX", "ticker_name_ja": "VIX指数", "line_level": "danger", "line_level_label": "危険ライン到達", "pressure_score": 0.78, "weight": 1.2},
        {"ticker": "^MOVE", "ticker_name_ja": "MOVE指数", "line_level": "danger", "line_level_label": "危険ライン到達", "pressure_score": 0.82, "weight": 1.2},
        {"ticker": "HYG/LQD", "ticker_name_ja": "ハイイールド債/投資適格債 比率", "line_level": "extreme", "line_level_label": "非常に危険ライン到達", "pressure_score": 1.0, "weight": 1.3},
        {"ticker": "^TNX", "ticker_name_ja": "米10年金利", "line_level": "danger", "line_level_label": "危険ライン到達", "pressure_score": 0.8, "weight": 1.05},
        {"ticker": "BZ=F", "ticker_name_ja": "Brent原油先物", "line_level": "danger", "line_level_label": "危険ライン到達", "pressure_score": 0.76, "weight": 1.0},
        {"ticker": "SPY", "ticker_name_ja": "米国大型株ETF", "line_level": "danger", "line_level_label": "危険ライン到達", "pressure_score": 0.72, "weight": 1.15},
    ]

    result = evaluate_risk_lines(regime, cycle, [], [], stress_monitor)

    assert result["stage_key"] == "extreme_danger_line_reached"
    assert result["extreme_count"] >= 1
    assert any(row.get("type") == "indicator" and row.get("indicator") == "BZ=F" for row in result["trigger_path"])
    assert any(row.get("type") == "composite_score" for row in result["trigger_path"])

def test_risk_lines_returns_decision_overlay_fields():
    regime = {
        "regime_label": "inflation_shock",
        "credit_regime_flag": "credit_stress_moderate",
        "inflation_regime_flag": "inflation_shock_broad",
    }
    cycle = {"phase_label": "downswing"}
    stress_monitor = [
        {"ticker": "^VIX", "ticker_name_ja": "VIX指数", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.48, "weight": 1.2},
        {"ticker": "^TNX", "ticker_name_ja": "米10年金利", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.45, "weight": 1.05},
        {"ticker": "CL=F", "ticker_name_ja": "WTI原油先物", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.5, "weight": 0.9},
        {"ticker": "SPY", "ticker_name_ja": "米国大型株ETF", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.44, "weight": 1.15},
        {"ticker": "HYG/LQD", "ticker_name_ja": "ハイイールド債/投資適格債 比率", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.46, "weight": 1.3},
    ]

    result = evaluate_risk_lines(regime, cycle, [], [], stress_monitor)

    assert result["decision_level"] == "caution"
    assert "credit_spillover_initial" in result["decision_flags"]
    assert result["decision_summary"]


def test_risk_lines_warning_rates_and_dollar_do_not_block_alone():
    regime = {"regime_label": "transition", "credit_regime_flag": "neutral", "inflation_regime_flag": "neutral"}
    cycle = {"phase_label": "late_cycle"}
    stress_monitor = [
        {"ticker": "^TNX", "ticker_name_ja": "米10年金利", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.45, "weight": 1.05},
        {"ticker": "DX-Y.NYB", "ticker_name_ja": "ドル指数", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.42, "weight": 0.85},
    ]

    result = evaluate_risk_lines(regime, cycle, [], [], stress_monitor)

    assert result["decision_level"] == "caution"
    assert "rates_warning" in result["decision_flags"]
    assert "dollar_warning" in result["decision_flags"]


def test_risk_lines_uses_gold_safe_haven_as_credit_spillover_confirmation():
    regime = {"regime_label": "transition", "credit_regime_flag": "neutral", "inflation_regime_flag": "neutral"}
    cycle = {"phase_label": "downswing"}
    stress_monitor = [
        {"ticker": "^VIX", "ticker_name_ja": "VIX指数", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.48, "weight": 1.2},
        {"ticker": "^TNX", "ticker_name_ja": "米10年金利", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.45, "weight": 1.05},
        {"ticker": "SPY", "ticker_name_ja": "米国大型株ETF", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.44, "weight": 1.15},
        {"ticker": "HYG/LQD", "ticker_name_ja": "ハイイールド債/投資適格債 比率", "line_level": "warning", "line_level_label": "警戒ライン接近", "pressure_score": 0.46, "weight": 1.3},
    ]
    inflation_monitor = [{"ticker": "GC=F", "ticker_name_ja": "金先物", "change_1w": 0.03, "zscore": 1.2, "signal_label": "安全資産選好"}]

    result = evaluate_risk_lines(regime, cycle, [], inflation_monitor, stress_monitor)

    assert result["stage_key"] == "credit_spillover_initial"
    assert "gold_safe_haven" in result["decision_flags"]
    assert "gold_crash_confirmation" in result["decision_flags"]
    assert any(row.get("name") == "gold_safe_haven" for row in result["trigger_path"])
    assert any("金先物" in reason for reason in result["reasons"])


def test_risk_lines_does_not_raise_stage_from_gold_alone():
    regime = {"regime_label": "transition", "credit_regime_flag": "neutral", "inflation_regime_flag": "neutral"}
    cycle = {"phase_label": "downswing"}
    inflation_monitor = [{"ticker": "GC=F", "ticker_name_ja": "金先物", "change_1w": 0.03, "zscore": 1.2, "signal_label": "安全資産選好"}]
    stress_monitor = [
        {"ticker": "^VIX", "line_level": "normal", "pressure_score": 0.0, "weight": 1.2},
        {"ticker": "SPY", "line_level": "normal", "pressure_score": 0.0, "weight": 1.15},
        {"ticker": "HYG/LQD", "line_level": "normal", "pressure_score": 0.0, "weight": 1.3},
        {"ticker": "^TNX", "line_level": "normal", "pressure_score": 0.0, "weight": 1.05},
        {"ticker": "CL=F", "line_level": "normal", "pressure_score": 0.0, "weight": 0.9},
        {"ticker": "DX-Y.NYB", "line_level": "normal", "pressure_score": 0.0, "weight": 0.85},
        {"ticker": "^MOVE", "line_level": "normal", "pressure_score": 0.0, "weight": 1.2},
    ]

    result = evaluate_risk_lines(regime, cycle, [], inflation_monitor, stress_monitor)

    assert result["stage_key"] == "normal"
    assert "gold_safe_haven" in result["decision_flags"]
    assert "gold_crash_confirmation" not in result["decision_flags"]
