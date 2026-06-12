from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from project.hindenburg_converter import CANONICAL_COLUMNS, normalize_hindenburg_csv, write_blank_template
from project.hindenburg_omen import build_hindenburg_omen_context, parse_hindenburg_breadth_csv
from project.hindenburg_provider import ProviderAttempt, ProviderResult
from project.hindenburg_manual import run


def test_header_only_template_generation(tmp_path: Path) -> None:
    output = tmp_path / "blank.csv"

    result = write_blank_template(output)

    assert result["status"] == "ok"
    assert output.read_bytes() == (",".join(CANONICAL_COLUMNS) + "\n").encode("utf-8")


def test_japanese_column_aliases_normalize_correctly(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text(
        "日付,新52週高値,新52週安値,値上がり銘柄数,値下がり銘柄数,対象銘柄数,NYSE指数,50日前指数,McClellan,メモ\n"
        "2026-01-02,80,75,1200,1200,2600,10000,9800,-5,manual\n",
        encoding="utf-8",
    )

    result = normalize_hindenburg_csv(source, output)

    assert result["status"] == "ok"
    assert result["rows_read"] == 1
    assert result["rows_written"] == 1
    assert output.read_text(encoding="utf-8").splitlines()[1] == "2026-01-02,80,75,1200,1200,2600,10000,9800,-5,manual"


def test_english_column_aliases_normalize_correctly(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text(
        "market_date,highs,lows,advancing,declining,issues,source_note\n"
        "2026-01-02,80,75,1200,1200,2600,english\n",
        encoding="utf-8",
    )

    result = normalize_hindenburg_csv(source, output)

    assert result["status"] == "ok"
    assert output.read_text(encoding="utf-8").splitlines()[1] == "2026-01-02,80,75,1200,1200,2600,,,,english"


def test_required_column_missing(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text("date,new_highs,new_lows,advancers\n2026-01-02,80,75,1200\n", encoding="utf-8")

    result = normalize_hindenburg_csv(source, output)

    assert result["status"] == "error"
    assert "必須列不足" in result["errors"][0]
    assert not output.exists()


def test_ambiguous_duplicate_mapping(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text(
        "date,日付,new_highs,new_lows,advancers,decliners\n"
        "2026-01-02,2026-01-02,80,75,1200,1200\n",
        encoding="utf-8",
    )

    result = normalize_hindenburg_csv(source, output)

    assert result["status"] == "error"
    assert "同じ列に対応する見出し" in result["errors"][0]


def test_invalid_date_rejects_row(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text("date,new_highs,new_lows,advancers,decliners\n2026/01/02,80,75,1200,1200\n", encoding="utf-8")

    result = normalize_hindenburg_csv(source, output)

    assert result["status"] == "ok"
    assert result["rows_written"] == 0
    assert result["rejected_rows"] == 1
    assert "date" in result["errors"][0]


def test_negative_value_rejects_row(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text("date,new_highs,new_lows,advancers,decliners\n2026-01-02,-1,75,1200,1200\n", encoding="utf-8")

    result = normalize_hindenburg_csv(source, output)

    assert result["rows_written"] == 0
    assert result["rejected_rows"] == 1
    assert "負の値" in result["errors"][0]


def test_sample_marker_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text(
        "date,new_highs,new_lows,advancers,decliners,source_note\n"
        "2026-01-02,80,75,1200,1200,EXAMPLE_DO_NOT_IMPORT sample only\n",
        encoding="utf-8",
    )

    result = normalize_hindenburg_csv(source, output)

    assert result["rows_written"] == 0
    assert result["rejected_rows"] == 1
    assert "サンプル行" in result["errors"][0]


def test_output_file_exists_without_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text("date,new_highs,new_lows,advancers,decliners\n2026-01-02,80,75,1200,1200\n", encoding="utf-8")
    output.write_text("existing\n", encoding="utf-8")

    result = normalize_hindenburg_csv(source, output)

    assert result["status"] == "error"
    assert output.read_text(encoding="utf-8") == "existing\n"


def test_overwrite_flag_works(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text("date,new_highs,new_lows,advancers,decliners\n2026-01-02,80,75,1200,1200\n", encoding="utf-8")
    output.write_text("existing\n", encoding="utf-8")

    result = normalize_hindenburg_csv(source, output, overwrite=True)

    assert result["status"] == "ok"
    assert output.read_text(encoding="utf-8").startswith("date,new_highs")


def test_normalized_output_is_utf8_without_bom_and_lf(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text("date,new_highs,new_lows,advancers,decliners\n2026-01-02,80,75,1200,1200\n", encoding="utf-8")

    normalize_hindenburg_csv(source, output)
    raw = output.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")


def test_normalized_csv_can_be_imported_by_hindenburg_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HINDENBURG_OMEN_DB_PATH", str(tmp_path / "hindenburg.sqlite3"))
    monkeypatch.setenv("HINDENBURG_OMEN_DATA_DIR", str(tmp_path / "hindenburg_data"))

    def no_live_builtin_chain(**_kwargs: object) -> ProviderResult:
        return ProviderResult(
            status="failed",
            provider_id="builtin_provider_chain",
            provider_label="Built-in provider chain",
            failure_code="ALL_PROVIDERS_UNAVAILABLE",
            attempts=(ProviderAttempt("barchart_market_momentum", "Barchart Market Momentum", "failed"),),
            limitations=("3候補すべて取得不可",),
        )

    monkeypatch.setattr("project.hindenburg_omen.acquire_builtin_provider_chain", no_live_builtin_chain)
    source = tmp_path / "source.csv"
    output = tmp_path / "hindenburg_breadth.csv"
    source.write_text(
        "日付,新高値,新安値,値上がり,値下がり,NYSE指数,50日前指数\n"
        "2026-01-02,80,75,1200,1200,10000,9800\n",
        encoding="utf-8",
    )
    normalize_hindenburg_csv(source, output)

    parsed = parse_hindenburg_breadth_csv(output)
    payload = build_hindenburg_omen_context(manual_csv_path=output, db_path=tmp_path / "hindenburg.sqlite3", as_of_date="2026-01-02")

    assert parsed["status"] == "ok"
    assert payload["must_not_affect_final_action"] is True
    assert payload["must_not_affect_buy_readiness_score"] is True
    assert payload["current_signal"] != "not_triggered"


def test_cli_normalize_csv_returns_clear_summary(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    output = tmp_path / "out.csv"
    source.write_text("date,new_highs,new_lows,advancers,decliners\n2026-01-02,80,75,1200,1200\n", encoding="utf-8")

    result = run(Namespace(command="normalize-csv", input=str(source), output=str(output), overwrite=False))

    assert result["rows_read"] == 1
    assert result["rows_written"] == 1
    assert result["output_path"] == str(output)
