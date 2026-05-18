import json

import pandas as pd

from project.threshold_historical_replay import run_threshold_historical_replay


def test_threshold_historical_replay_missing_price_points(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    result = run_threshold_historical_replay(reports_dir=reports_dir)

    assert result["status"] == "missing_price_points"
    assert "python -m project.validation_price_export" in result["message"]
    assert result["price_points_json"].endswith("validation_prices.json")


def test_threshold_historical_replay_missing_history(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "validation_prices.json").write_text('{"prices": []}', encoding="utf-8")

    result = run_threshold_historical_replay(reports_dir=reports_dir)

    assert result["status"] == "missing_history"
    assert result["history_dir"].endswith("history")


def test_threshold_historical_replay_max_history_and_no_trigger_path_diff(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    history_dir = reports_dir / "history"
    cache_dir = tmp_path / "cache"
    snapshot_dir = cache_dir / "market_snapshots"
    history_dir.mkdir(parents=True)
    snapshot_dir.mkdir(parents=True)
    (reports_dir / "validation_prices.json").write_text(json.dumps({"prices": [{"date": "2026-01-01", "price": 100}]}), encoding="utf-8")
    (snapshot_dir / "market_snapshot_20260101.csv").write_text("date,SPY\n2026-01-01,100\n", encoding="utf-8")
    for day in range(3):
        (history_dir / f"report_2026-01-0{day + 1}_073000.json").write_text(
            json.dumps({"generated_at": f"2026-01-0{day + 1}T07:30:00"}),
            encoding="utf-8",
        )
    active_path = tmp_path / "active.json"
    proposed_path = tmp_path / "proposed.json"
    active_path.write_text(json.dumps({"threshold_set": {"version": "active"}, "indicators": {}}), encoding="utf-8")
    proposed_path.write_text(json.dumps({"threshold_set": {"version": "proposed"}, "indicators": {}}), encoding="utf-8")

    seen_counts = []

    def fake_run_set(label, config, prices, history_entries, price_points, threshold_payload, candidate=None, **kwargs):
        seen_counts.append(len(history_entries))
        cases = [
            {
                "date": "2026-01-03",
                "final_action": "wait",
                "risk_stage_key": "normal",
                "risk_stage_label": "通常",
                "indicators": [],
                "trigger_path": [{"type": "composite_score", "score": 10}],
            }
        ]
        return {
            "label": label,
            "threshold_set": threshold_payload.get("threshold_set", {}),
            "total_history_count": len(history_entries),
            "replayed_count": len(cases),
            "action_counts": {"wait": 1},
            "risk_stage_counts": {"normal": 1},
            "validation": {"cases": [{"date": "2026-01-03", "forward_returns": {}, "max_drawdowns": {}}], "action_summary": {}},
            "cases": cases,
        }

    monkeypatch.setattr(
        "project.threshold_historical_replay.load_config",
        lambda path: {
            "paths": {"reports_dir": str(reports_dir), "cache_dir": str(cache_dir)},
            "data": {"monitor_windows_weeks": {"short": 1, "medium": 4, "long": 12}, "zscore_window_weeks": 52},
        },
    )
    monkeypatch.setattr(
        "project.threshold_historical_replay._load_prices",
        lambda path: pd.DataFrame({"SPY": [100.0]}, index=pd.to_datetime(["2026-01-01"])),
    )
    monkeypatch.setattr("project.threshold_historical_replay._build_monitor_feature_cache", lambda config, prices, history_entries: {})
    monkeypatch.setattr("project.threshold_historical_replay._run_set", fake_run_set)

    result = run_threshold_historical_replay(
        active_thresholds_path=active_path,
        proposed_thresholds_path=proposed_path,
        reports_dir=reports_dir,
        max_history=1,
        skip_candidate_details=True,
        no_trigger_path_diff=True,
    )

    assert result["status"] == "ok"
    assert seen_counts == [1, 1]
    assert result["runtime_diagnostics"]["history_count"] == 1
    assert result["runtime_diagnostics"]["trigger_path_diff_enabled"] is False
    changed_cases = json.loads((reports_dir / "threshold_changed_cases.json").read_text(encoding="utf-8"))
    assert changed_cases["cases"] == []


def test_threshold_historical_replay_timeout_returns_json_status(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    history_dir = reports_dir / "history"
    cache_dir = tmp_path / "cache"
    snapshot_dir = cache_dir / "market_snapshots"
    history_dir.mkdir(parents=True)
    snapshot_dir.mkdir(parents=True)
    (reports_dir / "validation_prices.json").write_text(json.dumps({"prices": [{"date": "2026-01-01", "price": 100}]}), encoding="utf-8")
    (snapshot_dir / "market_snapshot_20260101.csv").write_text("date,SPY\n2026-01-01,100\n", encoding="utf-8")
    (history_dir / "report_2026-01-01_073000.json").write_text(json.dumps({"generated_at": "2026-01-01T07:30:00"}), encoding="utf-8")
    active_path = tmp_path / "active.json"
    proposed_path = tmp_path / "proposed.json"
    active_path.write_text(json.dumps({"threshold_set": {"version": "active"}, "indicators": {}}), encoding="utf-8")
    proposed_path.write_text(json.dumps({"threshold_set": {"version": "proposed"}, "indicators": {}}), encoding="utf-8")
    monkeypatch.setattr(
        "project.threshold_historical_replay.load_config",
        lambda path: {
            "paths": {"reports_dir": str(reports_dir), "cache_dir": str(cache_dir)},
            "data": {"monitor_windows_weeks": {"short": 1, "medium": 4, "long": 12}, "zscore_window_weeks": 52},
        },
    )
    monkeypatch.setattr(
        "project.threshold_historical_replay._load_prices",
        lambda path: pd.DataFrame({"SPY": [100.0]}, index=pd.to_datetime(["2026-01-01"])),
    )

    result = run_threshold_historical_replay(
        active_thresholds_path=active_path,
        proposed_thresholds_path=proposed_path,
        reports_dir=reports_dir,
        timeout_seconds=0.001,
    )

    assert result["status"] == "timeout"
    assert "timeout_seconds=0.001" in result["message"]
    assert result["runtime_diagnostics"]["timeout_seconds"] == 0.001
