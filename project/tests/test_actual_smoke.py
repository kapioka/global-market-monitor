from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from project.data_fetcher import FetchResult
from project.main import run_actual_smoke


def test_actual_smoke_uses_temporary_config_and_disables_writes(tmp_path, monkeypatch) -> None:
    production_reports = tmp_path / "production_reports"
    production_cache = tmp_path / "production_cache"
    config = {
        "app": {"log_level": "INFO"},
        "paths": {
            "logs_dir": str(tmp_path / "production_logs"),
            "reports_dir": str(production_reports),
            "sample_output_dir": str(tmp_path / "production_sample"),
            "cache_dir": str(production_cache),
        },
    }
    fetch = FetchResult(
        prices=pd.DataFrame({"SPY": [100.0]}, index=pd.to_datetime(["2026-06-19"])),
        warnings=[],
        source="mixed",
        acquisition_log=[],
        diagnostics={"summary": {"source": "mixed", "snapshot_observed_at": "2026-06-20T21:07:09"}},
    )
    calls: dict[str, Any] = {}

    monkeypatch.setattr("project.main.load_config", lambda path: config)
    monkeypatch.setattr("project.main.load_latest_fetch_snapshot", lambda cache_dir: fetch)
    monkeypatch.setattr("project.main.setup_logging", lambda logs_dir, level: type("Logger", (), {"info": lambda *a, **k: None, "error": lambda *a, **k: None})())
    def ensure_dirs(paths) -> None:
        for path in paths:
            Path(path).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("project.main.ensure_directories", ensure_dirs)

    def fake_run_monitor(**kwargs):
        calls.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr("project.main.run_monitor", fake_run_monitor)

    run_actual_smoke("project/config.yaml", open_dashboard=False)

    smoke_config_path = Path(str(calls["config_path"]))
    assert ".tmp" in smoke_config_path.parts
    assert production_reports.as_posix() not in smoke_config_path.read_text(encoding="utf-8")
    assert calls["cache_write_allowed"] is False
    assert calls["persistence_policy"].policy_name == "actual_smoke_non_persistent"
    assert calls["fetch_result"].diagnostics["summary"]["data_mode_label"] == "キャッシュ使用"
    assert calls["fetch_result"].diagnostics["summary"]["production_state_write_allowed"] is False
