from __future__ import annotations

import zipfile

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
        ):
            assert required in names
        assert not any(name.startswith("project/cache/") for name in names)
        assert not any(name.startswith("project/manual_sources/") for name in names)
        assert not any(name.startswith("project/reports/history/") for name in names)
        assert not any(name.startswith("project/diagnostics/") for name in names)


def test_chatgpt_diagnostic_bundle_questions_have_no_control_characters(tmp_path) -> None:
    output = tmp_path / "chatgpt_logic_review_test.zip"

    build_chatgpt_diagnostic_bundle(output, version="test")

    with zipfile.ZipFile(output) as archive:
        text = archive.read("logic_review_questions.md").decode("utf-8")

    assert text.startswith("# Logic Review Questions")
    assert all(char in {"\n", "\r", "\t"} or ord(char) >= 32 for char in text)
