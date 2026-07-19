from __future__ import annotations

import zipfile
from pathlib import Path

from project.chatgpt_diagnostic_bundle import build_chatgpt_diagnostic_bundle


def test_chatgpt_diagnostic_bundle_includes_transitive_review_dependencies(tmp_path) -> None:
    output = tmp_path / "chatgpt_logic_review_test.zip"

    result = build_chatgpt_diagnostic_bundle(output, version="test")

    assert result.zip_path == output.resolve()
    assert result.size_bytes > 0
    assert result.entry_count > 20
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        for required in (
            "DIAGNOSTIC_MANIFEST.md",
            "logic_review_questions.md",
            "project/indicators.py",
            "project/threshold_metadata.py",
            "project/threshold_certainty.py",
            "project/risk_line_thresholds_active.json",
            "project/risk_line_thresholds_proposed.json",
            "project/scoring.py",
            "project/asset_compare.py",
            "project/credit_monitor.py",
            "project/inflation_monitor.py",
            "project/chatgpt_diagnostic_bundle.py",
            "project/tests/test_chatgpt_diagnostic_bundle.py",
            "project/risk_engine_v2_replay.py",
            "project/risk_engine_v2_artifact_freshness.py",
            "project/risk_engine_v2_root_cause.py",
            "project/risk_engine_v2_holdout_primary_coverage_audit.py",
            "project/risk_engine_v2_official_series_regeneration_comparison.py",
            "project/risk_engine_v2_official_series.py",
            "project/tests/test_risk_engine_v2_root_cause.py",
            "project/tests/test_risk_engine_v2_production_invariance.py",
            "project/tests/test_risk_engine_v2_artifact_freshness.py",
            "project/tests/test_risk_engine_v2_holdout_primary_coverage_audit.py",
            "project/tests/test_risk_engine_v2_official_series_regeneration_comparison.py",
            "project/tests/test_risk_engine_v2_official_series.py",
            "project/hindenburg_omen.py",
            "project/tests/test_hindenburg_omen.py",
            "docs/risk_engine_v2_current_state.md",
            "docs/v0.8.54_diagnostic_bundle_completeness_polish.md",
            "docs/v0.8.57_hindenburg_omen_display_monitor.md",
            "docs/v0.8.60_rc_final_polish.md",
        ):
            assert required in names
        assert not any(name.startswith("project/cache/") for name in names)
        assert not any(name.startswith("project/manual_sources/") for name in names)
        assert not any(name.startswith("project/reports/history/") for name in names)
        assert not any(name.startswith("project/diagnostics/") for name in names)


def test_chatgpt_diagnostic_bundle_questions_have_no_control_characters(tmp_path) -> None:
    output = tmp_path / "chatgpt_logic_review_test.zip"

    build_chatgpt_diagnostic_bundle(output, version="v0.8.59")

    with zipfile.ZipFile(output) as archive:
        text = archive.read("logic_review_questions.md").decode("utf-8")

    assert text.startswith("# Logic Review Questions v0.8.59")
    assert all(char in {"\n", "\r", "\t"} or ord(char) >= 32 for char in text)


def test_chatgpt_diagnostic_bundle_default_output_uses_requested_version() -> None:
    result = build_chatgpt_diagnostic_bundle(version="v0.8.60")

    try:
        assert result.zip_path == (Path.cwd() / "project" / "diagnostics" / "chatgpt_logic_review_v0.8.60.zip").resolve()
    finally:
        result.zip_path.unlink(missing_ok=True)
