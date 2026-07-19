from __future__ import annotations

from pathlib import Path

from project.market_data_provider import resolve_market_data_db_path, resolve_market_data_dir


def test_market_data_paths_use_explicit_overrides(monkeypatch, tmp_path: Path) -> None:
    custom_dir = tmp_path / "data"
    custom_db = tmp_path / "custom.sqlite3"
    monkeypatch.setenv("GLOBAL_MARKET_MONITOR_DATA_DIR", str(custom_dir))
    monkeypatch.setenv("GLOBAL_MARKET_MONITOR_DB_PATH", str(custom_db))

    assert resolve_market_data_dir() == custom_dir
    assert resolve_market_data_db_path() == custom_db


def test_market_data_path_defaults_under_local_app_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GLOBAL_MARKET_MONITOR_DATA_DIR", raising=False)
    monkeypatch.delenv("GLOBAL_MARKET_MONITOR_DB_PATH", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert resolve_market_data_dir() == tmp_path / "GlobalMarketMonitor" / "market_data"
    assert resolve_market_data_db_path() == tmp_path / "GlobalMarketMonitor" / "market_data" / "market_data.sqlite3"
