from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

from project.hindenburg_provider import (
    ProviderAttempt,
    ProviderResult,
    acquire_builtin_provider_chain,
    acquire_configured_static_csv,
    parse_barchart_market_momentum_html,
)


class FixtureHandler(BaseHTTPRequestHandler):
    payload: ClassVar[bytes] = b""
    status_code: ClassVar[int] = 200

    def do_GET(self) -> None:
        self.send_response(self.status_code)
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def _serve(payload: bytes, status_code: int = 200) -> tuple[HTTPServer, str]:
    FixtureHandler.payload = payload
    FixtureHandler.status_code = status_code
    server = HTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/breadth.csv?query_param=redacted-fixture"


def test_configured_static_csv_downloads_to_cache_and_redacts_url(tmp_path: Path) -> None:
    server, url = _serve(b"date,new_highs,new_lows,advancers,decliners\n2026-01-02,1,1,10,9\n")
    try:
        result = acquire_configured_static_csv(url, cache_dir=tmp_path)
    finally:
        server.shutdown()

    assert result.status == "ok"
    assert result.source_path is not None
    assert Path(result.source_path).exists()
    assert "query_param" not in str(result.source_label)
    assert "redacted-fixture" not in str(result.source_label)
    assert result.attempts[0].status == "ok"


def test_configured_static_csv_preserves_previous_cache_after_http_error(tmp_path: Path) -> None:
    server, url = _serve(b"date,new_highs,new_lows,advancers,decliners\n2026-01-02,1,1,10,9\n")
    try:
        first = acquire_configured_static_csv(url, cache_dir=tmp_path)
        FixtureHandler.payload = b"error"
        FixtureHandler.status_code = 500
        second = acquire_configured_static_csv(url, cache_dir=tmp_path)
    finally:
        server.shutdown()

    assert first.status == "ok"
    assert second.status == "cache_fallback"
    assert second.source_path == first.source_path


def test_configured_static_csv_rejects_oversized_response(tmp_path: Path) -> None:
    server, url = _serve(b"x" * 128)
    try:
        result = acquire_configured_static_csv(url, cache_dir=tmp_path, max_response_bytes=16)
    finally:
        server.shutdown()

    assert result.status == "failed"
    assert result.failure_code == "OVERSIZED_RESPONSE"


def test_builtin_provider_chain_reports_all_candidates_unavailable() -> None:
    result = acquire_builtin_provider_chain(total_budget_seconds=0)

    assert result.status == "failed"
    assert result.failure_code == "ALL_PROVIDERS_UNAVAILABLE"
    assert result.attempts[0].failure_code == "TOTAL_BUDGET_EXCEEDED"


BARCHART_FIXTURE = """
<html><body>
<h1>Thu, Jun 11th, 2026</h1>
<script type="application/json">
{"dailyStockActivity":[
  {"exchange":"NYSE","high52w":115,"low52w":47,"advancingIssues":1620,"decliningIssues":1180,"unchangedIssues":73,"totalIssues":2873}
]}
</script>
</body></html>
"""


def test_parse_barchart_market_momentum_fixture() -> None:
    parsed = parse_barchart_market_momentum_html(BARCHART_FIXTURE, acquired_at="2026-06-12T00:00:00+00:00")

    assert parsed["status"] == "ok"
    assert parsed["provider_id"] == "barchart_market_momentum"
    assert parsed["universe_id"] == "nyse_legacy_compat"
    assert parsed["market_date"] == "2026-06-11"
    assert parsed["new_highs"] == 115
    assert parsed["new_lows"] == 47
    assert parsed["advancers"] == 1620
    assert parsed["decliners"] == 1180
    assert parsed["parser_version"]


def test_barchart_structure_changed_missing_json() -> None:
    parsed = parse_barchart_market_momentum_html("<html><body>Thu, Jun 11th, 2026</body></html>")

    assert parsed["status"] == "failed"
    assert parsed["failure_code"] == "MANDATORY_FIELD_MISSING"


def test_barchart_rejects_missing_mandatory_fields() -> None:
    payload = """
    <html><body>Thu, Jun 11th, 2026
    <script>{"dailyStockActivity":[{"exchange":"NYSE","high52w":115,"low52w":47,"advancingIssues":1620}]}</script>
    </body></html>
    """
    parsed = parse_barchart_market_momentum_html(payload)

    assert parsed["status"] == "failed"
    assert parsed["failure_code"] == "MANDATORY_FIELD_MISSING"


def test_barchart_does_not_confuse_volume_with_issue_counts() -> None:
    payload = """
    <html><body>Thu, Jun 11th, 2026
    <script>{"dailyStockActivity":[{"exchange":"NYSE","high52w":115,"low52w":47,"advancingVolume":1000000,"decliningVolume":900000}]}</script>
    </body></html>
    """
    parsed = parse_barchart_market_momentum_html(payload)

    assert parsed["status"] == "failed"
    assert parsed["failure_code"] == "ISSUE_COUNTS_NOT_AVAILABLE"


def test_builtin_provider_chain_first_provider_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_acquire(provider_id: str, provider_label: str, source_url: str, cache_dir: Path, **_kwargs: object) -> ProviderResult:
        path = cache_dir / "first.csv"
        path.write_text("date,new_highs,new_lows,advancers,decliners\n2026-06-11,1,1,10,9\n", encoding="utf-8")
        return ProviderResult(
            status="ok",
            provider_id=provider_id,
            provider_label=provider_label,
            source_path=str(path),
            source_label=source_url,
            attempts=(ProviderAttempt(provider_id, provider_label, "ok"),),
        )

    monkeypatch.setattr("project.hindenburg_provider._acquire_builtin_provider", fake_acquire)

    result = acquire_builtin_provider_chain(cache_dir=tmp_path)

    assert result.status == "ok"
    assert result.provider_id == "barchart_market_momentum"
    assert len(result.attempts) == 1


def test_builtin_provider_chain_first_fail_second_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_acquire(provider_id: str, provider_label: str, source_url: str, cache_dir: Path, **_kwargs: object) -> ProviderResult:
        if provider_id == "barchart_market_momentum":
            return ProviderResult(
                status="failed",
                provider_id=provider_id,
                provider_label=provider_label,
                failure_code="MANDATORY_FIELD_MISSING",
                attempts=(ProviderAttempt(provider_id, provider_label, "failed", "MANDATORY_FIELD_MISSING"),),
            )
        path = cache_dir / "second.csv"
        path.write_text("date,new_highs,new_lows,advancers,decliners\n2026-06-11,1,1,10,9\n", encoding="utf-8")
        return ProviderResult(
            status="ok",
            provider_id=provider_id,
            provider_label=provider_label,
            source_path=str(path),
            source_label=source_url,
            attempts=(ProviderAttempt(provider_id, provider_label, "ok"),),
        )

    monkeypatch.setattr("project.hindenburg_provider._acquire_builtin_provider", fake_acquire)

    result = acquire_builtin_provider_chain(cache_dir=tmp_path)

    assert result.status == "ok"
    assert result.provider_id == "marketwatch_us_market_data"
    assert [attempt.provider_id for attempt in result.attempts] == ["barchart_market_momentum", "marketwatch_us_market_data"]


def test_builtin_provider_chain_first_two_fail_third_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_acquire(provider_id: str, provider_label: str, source_url: str, cache_dir: Path, **_kwargs: object) -> ProviderResult:
        if provider_id != "wsj_market_diary":
            return ProviderResult(
                status="failed",
                provider_id=provider_id,
                provider_label=provider_label,
                failure_code="MANDATORY_FIELD_MISSING",
                attempts=(ProviderAttempt(provider_id, provider_label, "failed", "MANDATORY_FIELD_MISSING"),),
            )
        path = cache_dir / "third.csv"
        path.write_text("date,new_highs,new_lows,advancers,decliners\n2026-06-11,1,1,10,9\n", encoding="utf-8")
        return ProviderResult(
            status="ok",
            provider_id=provider_id,
            provider_label=provider_label,
            source_path=str(path),
            source_label=source_url,
            attempts=(ProviderAttempt(provider_id, provider_label, "ok"),),
        )

    monkeypatch.setattr("project.hindenburg_provider._acquire_builtin_provider", fake_acquire)

    result = acquire_builtin_provider_chain(cache_dir=tmp_path)

    assert result.status == "ok"
    assert result.provider_id == "wsj_market_diary"
    assert [attempt.provider_id for attempt in result.attempts] == [
        "barchart_market_momentum",
        "marketwatch_us_market_data",
        "wsj_market_diary",
    ]
