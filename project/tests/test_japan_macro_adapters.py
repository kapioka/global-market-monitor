from __future__ import annotations

from project.japan_macro_adapters import (
    build_japan_macro_context,
    parse_boj_domestic_rate_csv,
    parse_japan_cpi_csv,
    parse_jgb_yield_curve_csv,
    run_official_japan_macro_dry_run,
)

JGB_CSV = """Date,JGB 2Y,JGB 5Y,JGB 10Y,JGB 20Y,JGB 30Y
2026-05-24,0.31,0.55,1.02,1.75,2.05
2026-05-31,0.34,0.58,1.08,1.80,2.12
"""

CPI_CSV = """Date,CPI YoY,Core CPI YoY
2026-04-01,2.4,2.1
2026-05-01,2.7,2.4
"""

BOJ_CSV = """Date,Policy Rate,Call Rate
2026-04-01,0.25,0.23
2026-05-01,0.25,0.28
"""


def test_parse_jgb_yield_curve_fixture_returns_required_fields() -> None:
    result = parse_jgb_yield_curve_csv(JGB_CSV)

    assert result["status"] == "ok"
    assert result["latest_date"] == "2026-05-31"
    assert result["observations"]["jgb_2y"] == 0.34
    assert result["observations"]["jgb_10y"] == 1.08
    assert result["observations"]["jgb_30y"] == 2.12
    assert result["observations"]["jgb_curve_10y_2y"] == 0.74
    assert result["observations"]["jgb_curve_30y_10y"] == 1.04
    assert "Ministry of Finance" in result["source_name"]


def test_parse_japan_cpi_fixture_returns_trend_without_fake_values() -> None:
    result = parse_japan_cpi_csv(CPI_CSV)

    assert result["status"] == "ok"
    assert result["observations"]["jp_cpi_yoy"] == 2.7
    assert result["observations"]["jp_core_cpi_yoy"] == 2.4
    assert result["observations"]["jp_cpi_trend"] == "rising"
    assert "Statistics Bureau" in result["source_name"]


def test_parse_boj_domestic_rate_fixture_returns_context() -> None:
    result = parse_boj_domestic_rate_csv(BOJ_CSV)

    assert result["status"] == "ok"
    assert result["observations"]["boj_policy_rate"] == 0.25
    assert result["observations"]["boj_call_rate"] == 0.28
    assert result["observations"]["domestic_rate_context"] == "rising"
    assert "Bank of Japan" in result["source_name"]


def test_parse_failures_return_structured_failed_status() -> None:
    result = parse_jgb_yield_curve_csv("not,a,valid,schema\n1,2,3,4")

    assert result["status"] == "failed"
    assert result["observations"] == {}
    assert result["error_message"]


def test_build_japan_macro_context_maps_adapter_outputs_to_display_context() -> None:
    context = build_japan_macro_context(
        [
            parse_jgb_yield_curve_csv(JGB_CSV),
            parse_japan_cpi_csv(CPI_CSV),
            parse_boj_domestic_rate_csv(BOJ_CSV),
        ]
    )

    assert context["jgb_yields"]["jgb_10y"] == 1.08
    assert context["inflation"]["jp_cpi_trend"] == "rising"
    assert context["domestic_rates"]["domestic_rate_context"] == "rising"
    assert set(context["macro_sources"]) == {"jgb_yield_curve", "japan_cpi", "boj_domestic_short_rate"}


def test_dry_run_contract_is_safe_without_live_fetch() -> None:
    result = run_official_japan_macro_dry_run(live=False)

    assert result["status"] == "unavailable"
    assert result["mode"] == "contract_only"
    assert set(result["context"]["macro_sources"]) == {"jgb_yield_curve", "japan_cpi", "boj_domestic_short_rate"}
