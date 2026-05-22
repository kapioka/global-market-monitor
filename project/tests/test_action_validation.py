from __future__ import annotations

from project.action_validation import build_action_validation


def test_build_action_validation_summarizes_forward_returns_by_action():
    history = [
        {
            "generated_at": "2026-01-01T07:30:00",
            "spot_signal": {"action_decision": {"action": "buy_window"}},
            "data_reliability": {"level": "high"},
        },
        {
            "generated_at": "2026-01-02T07:30:00",
            "spot_signal": {"action_decision": {"action": "watch", "reliability_cap_applied": True}},
            "data_reliability": {"level": "medium", "max_action": "watch"},
        },
    ]
    prices = [
        {"date": "2026-01-01T00:00:00", "price": 100.0},
        {"date": "2026-01-02T00:00:00", "price": 110.0},
        {"date": "2026-03-05T00:00:00", "price": 120.0},
        {"date": "2026-07-08T00:00:00", "price": 130.0},
        {"date": "2027-01-01T00:00:00", "price": 140.0},
    ]

    result = build_action_validation(history, prices)

    assert result["status"] == "ok"
    assert result["action_summary"]["buy_window"]["count"] == 1
    assert result["action_summary"]["buy_window"]["horizons"]["4w"]["mean_return"] == 0.2
    assert result["action_summary"]["buy_window"]["horizons"]["13w"]["mean_return"] == 0.3
    assert result["action_summary"]["buy_window"]["horizons"]["13w"]["median_return"] == 0.3
    assert result["action_summary"]["buy_window"]["horizons"]["13w"]["win_rate"] == 1.0
    assert result["action_summary"]["buy_window"]["horizons"]["13w"]["max_loss"] == 0.3
    assert result["action_summary"]["buy_window"]["horizons"]["13w"]["max_gain"] == 0.3
    assert result["cases"][0]["max_drawdowns"]["13w"] == 0.0
    assert result["action_summary"]["watch"]["reliability_capped_count"] == 1
    assert "buy_candidate" in result["action_summary"]
    assert result["action_summary"]["buy_candidate"]["count"] == 0
    assert result["diagnostics"]["buy_window_negative_rate_13w"] == 0.0


def test_build_action_validation_excludes_diagnostic_only_history():
    history = [
        {
            "generated_at": "2026-01-01T07:30:00",
            "spot_signal": {"action_decision": {"action": "wait"}},
            "data_reliability": {"level": "diagnostic", "max_action": "diagnostic_only"},
        }
    ]
    prices = [
        {"date": "2026-01-01T00:00:00", "price": 100.0},
        {"date": "2026-03-05T00:00:00", "price": 120.0},
    ]

    result = build_action_validation(history, prices)

    assert result["status"] == "insufficient_data"
    assert result["cases"] == []


def test_build_action_validation_handles_insufficient_data():
    result = build_action_validation([], [])

    assert result["status"] == "insufficient_data"


def test_build_action_validation_calculates_external_benchmark_excess_return():
    history = [
        {
            "generated_at": "2026-01-01T07:30:00",
            "spot_signal": {"action_decision": {"action": "buy_window"}},
            "data_reliability": {"level": "high"},
        }
    ]
    prices = [
        {"date": "2026-01-01T00:00:00", "price": 100.0},
        {"date": "2026-01-30T00:00:00", "price": 110.0},
    ]
    benchmark_prices = [
        {"date": "2026-01-01T00:00:00", "price": 200.0},
        {"date": "2026-01-30T00:00:00", "price": 210.0},
    ]

    result = build_action_validation(history, prices, benchmark_prices)

    case = result["cases"][0]
    assert result["benchmark_source"] == "external"
    assert case["forward_returns"]["4w"] == 0.1
    assert case["benchmark_returns"]["4w"] == 0.05
    assert case["excess_returns"]["4w"] == 0.05
    assert result["action_summary"]["buy_window"]["horizons"]["4w"]["mean_excess_return"] == 0.05
    assert result["action_summary"]["buy_window"]["horizons"]["4w"]["excess_win_rate"] == 1.0
