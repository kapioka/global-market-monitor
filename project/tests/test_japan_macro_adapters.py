from __future__ import annotations

from project.japan_macro_adapters import (
    BOJ_MANUAL_FILENAMES,
    BOJ_SHORT_RATE_SOURCE,
    CPI_MANUAL_FILENAMES,
    JGB_SOURCE,
    _classify_download_response,
    _failed_result,
    _resolve_boj_live_source,
    _resolve_cpi_live_source,
    _resolve_manual_csv_adapter,
    _source_reference_result,
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

MOF_JGB_CSV = """Interest Rate,,,,,,,,,,,,,,,(Unit : %)
Date,1Y,2Y,3Y,4Y,5Y,6Y,7Y,8Y,9Y,10Y,15Y,20Y,25Y,30Y,40Y
2026/05/28,0.50,0.75,0.80,0.90,1.00,1.05,1.10,1.15,1.20,1.30,1.55,1.80,1.95,2.05,2.25
2026/05/29,0.51,0.76,0.81,0.91,1.01,1.06,1.11,1.16,1.21,1.32,1.56,1.82,1.96,2.08,2.26
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


def test_parse_mof_jgb_csv_with_title_row_returns_latest_curve() -> None:
    result = parse_jgb_yield_curve_csv(
        MOF_JGB_CSV, source_url="https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
    )

    assert result["status"] == "ok"
    assert result["latest_date"] == "2026-05-29"
    assert result["observations"]["jgb_2y"] == 0.76
    assert result["observations"]["jgb_10y"] == 1.32
    assert result["observations"]["jgb_30y"] == 2.08
    assert result["observations"]["jgb_curve_10y_2y"] == 0.56
    assert result["metadata"]["source_type"] == "official_csv"


def test_parse_japan_cpi_fixture_returns_trend_without_fake_values() -> None:
    result = parse_japan_cpi_csv(CPI_CSV)

    assert result["status"] == "ok"
    assert result["observations"]["jp_cpi_yoy"] == 2.7
    assert result["observations"]["jp_core_cpi_yoy"] == 2.4
    assert result["observations"]["jp_cpi_trend"] == "rising"
    assert "Statistics Bureau" in result["source_name"]


def test_manual_cpi_csv_resolver_returns_local_manual_source(tmp_path) -> None:
    manual_dir = tmp_path / "manual_sources"
    manual_dir.mkdir()
    (manual_dir / "japan_cpi.csv").write_text(CPI_CSV, encoding="utf-8")

    result = _resolve_manual_csv_adapter(
        {
            "source_name": "Local manual Japan CPI CSV",
            "source_url": "",
            "source_group": "japan_cpi",
            "source_type": "local_manual_file",
            "source_kind": "local_manual_file",
        },
        "japan_cpi",
        parse_japan_cpi_csv,
        CPI_MANUAL_FILENAMES,
        manual_dir=manual_dir,
    )

    assert result["status"] == "ok"
    assert result["source_kind"] == "local_manual_file"
    assert result["local_path"].endswith("japan_cpi.csv")
    assert result["observations"]["jp_core_cpi_yoy"] == 2.4
    assert result["metadata"]["safe_for_context"] is True


def test_parse_boj_domestic_rate_fixture_returns_context() -> None:
    result = parse_boj_domestic_rate_csv(BOJ_CSV)

    assert result["status"] == "ok"
    assert result["observations"]["boj_policy_rate"] == 0.25
    assert result["observations"]["boj_call_rate"] == 0.28
    assert result["observations"]["domestic_rate_context"] == "rising"
    assert "Bank of Japan" in result["source_name"]


def test_manual_boj_csv_resolver_returns_local_manual_source(tmp_path) -> None:
    manual_dir = tmp_path / "manual_sources"
    manual_dir.mkdir()
    (manual_dir / "boj_short_rate.csv").write_text(BOJ_CSV, encoding="utf-8")

    result = _resolve_manual_csv_adapter(
        {
            "source_name": "Local manual BOJ short-rate CSV",
            "source_url": "",
            "source_group": "boj_domestic_short_rate",
            "source_type": "local_manual_file",
            "source_kind": "local_manual_file",
        },
        "boj_domestic_short_rate",
        parse_boj_domestic_rate_csv,
        BOJ_MANUAL_FILENAMES,
        manual_dir=manual_dir,
    )

    assert result["status"] == "ok"
    assert result["source_kind"] == "local_manual_file"
    assert result["local_path"].endswith("boj_short_rate.csv")
    assert result["observations"]["boj_call_rate"] == 0.28
    assert result["metadata"]["safe_for_context"] is True


def test_parse_failures_return_structured_failed_status() -> None:
    result = parse_jgb_yield_curve_csv("not,a,valid,schema\n1,2,3,4")

    assert result["status"] == "failed"
    assert result["observations"] == {}
    assert result["error_category"] == "missing_required_fields"
    assert result["error_message"]


def test_landing_page_response_is_classified_before_csv_parser() -> None:
    issue = _classify_download_response("text/html; charset=utf-8", "<!doctype html><html><body>download</body></html>", b"x")

    assert issue == ("landing_page", "official source resolved to an HTML landing page, not a stable CSV/text data file")


def test_failed_result_includes_source_specific_error_category() -> None:
    result = _failed_result(
        JGB_SOURCE,
        "jgb_yield_curve",
        JGB_SOURCE["source_url"],
        ValueError("official source resolved to an HTML landing page"),
        error_category="landing_page",
        metadata={"safe_for_context": False, "content_type": "text/html"},
    )

    assert result["status"] == "failed"
    assert result["error_category"] == "landing_page"
    assert result["metadata"]["content_type"] == "text/html"


def test_landing_page_fallback_source_registry_is_non_data() -> None:
    result = _source_reference_result(
        JGB_SOURCE,
        "jgb_yield_curve",
        status="landing_page_reference",
        error_category="landing_page_reference",
        human_action="download_endpoint_discovery_required",
        human_note="official source resolved to a landing page",
    )

    assert result["status"] == "landing_page_reference"
    assert result["source_type"] == "official_landing_page"
    assert result["value"] is None
    assert result["observations"] == {}
    assert result["metadata"]["safe_for_context"] is False


def test_manual_csv_missing_is_structured_non_data(tmp_path) -> None:
    result = _resolve_manual_csv_adapter(
        {
            "source_name": "Local manual Japan CPI CSV",
            "source_url": "",
            "source_group": "japan_cpi",
            "source_type": "local_manual_file",
            "source_kind": "local_manual_file",
        },
        "japan_cpi",
        parse_japan_cpi_csv,
        CPI_MANUAL_FILENAMES,
        manual_dir=tmp_path / "missing",
    )

    assert result["status"] == "manual_file_missing"
    assert result["error_category"] == "manual_file_missing"
    assert result["value"] is None
    assert result["observations"] == {}


def test_cpi_live_source_reports_manual_missing_without_estat_app_id(monkeypatch) -> None:
    monkeypatch.delenv("ESTAT_APP_ID", raising=False)

    result = _resolve_cpi_live_source()

    assert result["status"] == "manual_file_missing"
    assert result["error_category"] == "manual_file_missing"
    assert result["source_name"] == "Local manual Japan CPI CSV"
    assert result["value"] is None
    assert result["observations"] == {}
    assert result["metadata"]["credential_name"] == "ESTAT_APP_ID"


def test_cpi_live_source_with_app_id_still_requires_endpoint_mapping(monkeypatch) -> None:
    monkeypatch.setenv("ESTAT_APP_ID", "test-app-id")

    result = _resolve_cpi_live_source()

    assert result["status"] == "endpoint_not_resolved"
    assert result["error_category"] == "endpoint_not_resolved"
    assert result["metadata"]["credential_configured"] is True
    assert "test-app-id" not in str(result)


def test_boj_live_source_returns_endpoint_not_resolved_registry_entry() -> None:
    result = _resolve_boj_live_source()

    assert result["status"] == "endpoint_not_resolved"
    assert result["source_name"] == BOJ_SHORT_RATE_SOURCE["source_name"]
    assert result["source_type"] == "official_landing_page"
    assert result["value"] is None
    assert result["observations"] == {}


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


def test_build_japan_macro_context_treats_fallback_registry_as_missing_data() -> None:
    context = build_japan_macro_context(
        [
            _source_reference_result(
                JGB_SOURCE,
                "jgb_yield_curve",
                status="endpoint_not_resolved",
                error_category="endpoint_not_resolved",
                human_action="download_endpoint_discovery_required",
                human_note="endpoint not resolved",
            ),
            _resolve_boj_live_source(),
        ]
    )

    assert "jgb_yields" not in context
    assert "domestic_rates" not in context
    assert context["macro_sources"]["jgb_yield_curve"]["status"] == "endpoint_not_resolved"


def test_dry_run_contract_is_safe_without_live_fetch() -> None:
    result = run_official_japan_macro_dry_run(live=False)

    assert result["status"] == "unavailable"
    assert result["mode"] == "contract_only"
    assert set(result["context"]["macro_sources"]) == {"jgb_yield_curve", "japan_cpi", "boj_domestic_short_rate"}
