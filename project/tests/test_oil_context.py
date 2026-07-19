from __future__ import annotations

from project.oil_context import attach_oil_context_to_rows, build_oil_context


def _row(ticker: str, level: str = "normal", change_4w: float = 0.0, **extra):
    return {
        "ticker": ticker,
        "line_level": level,
        "pressure_score": 0.0,
        "change_1w": 0.0,
        "change_4w": change_4w,
        "change_12w": change_4w,
        "quality_flags": ["valid"],
        "stage_eligible": True,
        "limitations": [],
        **extra,
    }


def test_oil_inflation_watch_requires_confirmation():
    result = build_oil_context(
        [
            _row("CL=F", change_4w=0.06),
            _row("^TNX", level="warning", change_4w=0.03),
            _row("SPY", change_4w=0.02),
            _row("HYG/LQD", change_4w=0.0),
        ],
        settings={"oil": {"inflation_shock_return_4w": 0.08, "demand_collapse_return_4w": -0.12}},
    )

    assert result["overall_status"] == "inflation_watch"
    assert result["inflation_pressure_score"] > 0
    assert result["demand_collapse_score"] == 0.0


def test_oil_drop_alone_is_not_demand_collapse():
    result = build_oil_context(
        [
            _row("CL=F", change_4w=-0.18),
            _row("SPY", change_4w=0.02),
            _row("HYG/LQD", change_4w=0.0),
            _row("DX-Y.NYB", change_4w=0.0),
        ],
        settings={"oil": {"demand_collapse_return_4w": -0.12}},
    )

    assert result["overall_status"] == "normal"
    assert result["oil_decline_pressure_score"] > 0
    assert result["demand_collapse_score"] < result["oil_decline_pressure_score"]
    assert "株式と信用の確認を待ちます" in " ".join(result["limitations"])


def test_oil_drop_with_equity_and_credit_confirms_demand_watch():
    result = build_oil_context(
        [
            _row("CL=F", change_4w=-0.18),
            _row("SPY", level="warning", change_4w=-0.08),
            _row("HYG/LQD", level="warning", change_4w=-0.01),
        ],
        settings={"oil": {"demand_collapse_return_4w": -0.12}},
    )

    assert result["overall_status"] in {"demand_watch", "demand_stress"}
    assert result["equity_confirmation"] is True
    assert result["credit_confirmation"] is True
    assert result["demand_collapse_score"] > 0


def test_oil_comparison_unavailable_is_not_reported_as_zero():
    result = build_oil_context(
        [
            _row(
                "CL=F",
                change_4w=-0.18,
                quality_flags=["comparison_unavailable"],
                stage_eligible=False,
                limitations=["return_4w comparison unavailable"],
            )
        ],
        settings={"oil": {"demand_collapse_return_4w": -0.12}},
    )

    assert result["overall_status"] == "unavailable"
    assert result["demand_collapse_score"] is None
    assert result["risk_signal_allowed"] is False


def test_oil_suspicious_discontinuity_is_reference_only():
    result = build_oil_context(
        [
            _row(
                "CL=F",
                change_4w=0.30,
                quality_flags=["suspicious_discontinuity"],
                stage_eligible=False,
                limitations=["large one-period change detected"],
            ),
            _row("^TNX", level="warning", change_4w=0.03),
        ]
    )

    assert result["overall_status"] == "unavailable"
    assert result["inflation_pressure_score"] is None
    assert result["risk_signal_allowed"] is False
    assert "原油リスクシグナルから除外" in " ".join(result["limitations"])


def test_attach_oil_context_only_to_oil_rows():
    rows = [_row("CL=F"), _row("SPY")]
    context = build_oil_context(rows)

    attached = attach_oil_context_to_rows(rows, context)

    assert "oil_context" in attached[0]
    assert "oil_context" not in attached[1]
