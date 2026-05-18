from __future__ import annotations

import json
from pathlib import Path

from project.run_action_validation import main, run_action_validation


def _history_payload(action: str = "buy_window") -> dict:
    return {
        "generated_at": "2026-01-02T07:30:00",
        "spot_signal": {
            "action": action,
            "action_decision": {"action": action, "reliability_cap_applied": False},
        },
        "data_reliability": {"level": "high", "max_action": "buy_window"},
    }


def test_run_action_validation_writes_reports(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    reports_dir = tmp_path / "reports"
    history_dir.mkdir()
    (history_dir / "report_2026-01-02_073000.json").write_text(
        json.dumps(_history_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    prices_path = tmp_path / "prices.json"
    prices_path.write_text(
        json.dumps(
            [
                {"date": "2026-01-02", "price": 100.0},
                {"date": "2026-04-06", "price": 110.0},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_action_validation(history_dir, prices_path, reports_dir)

    assert result["status"] == "ok"
    assert result["history_count"] == 1
    assert (reports_dir / "action_validation.json").exists()
    assert (reports_dir / "action_validation.md").exists()


def test_run_action_validation_accepts_benchmark_price_points(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    reports_dir = tmp_path / "reports"
    history_dir.mkdir()
    (history_dir / "report_2026-01-02_073000.json").write_text(json.dumps(_history_payload(), ensure_ascii=False), encoding="utf-8")
    prices_path = tmp_path / "prices.json"
    prices_path.write_text(json.dumps([{"date": "2026-01-02", "price": 100.0}, {"date": "2026-04-06", "price": 110.0}]), encoding="utf-8")
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(json.dumps([{"date": "2026-01-02", "price": 200.0}, {"date": "2026-04-06", "price": 220.0}]), encoding="utf-8")

    result = run_action_validation(history_dir, prices_path, reports_dir, benchmark_path)

    assert result["status"] == "ok"
    assert result["benchmark_price_point_count"] == 2
    payload = json.loads((reports_dir / "action_validation.json").read_text(encoding="utf-8"))
    assert payload["benchmark_source"] == "external"


def test_run_action_validation_reports_missing_benchmark_without_traceback(tmp_path: Path) -> None:
    history_dir = tmp_path / "history"
    reports_dir = tmp_path / "reports"
    history_dir.mkdir()
    prices_path = tmp_path / "prices.json"
    prices_path.write_text(json.dumps([{"date": "2026-01-02", "price": 100.0}, {"date": "2026-04-06", "price": 110.0}]), encoding="utf-8")

    result = run_action_validation(history_dir, prices_path, reports_dir, tmp_path / "missing.json")

    assert result["status"] == "missing_benchmark_price_points"
    assert "benchmark validation price file is missing" in result["message"]


def test_main_accepts_price_points_json_object(tmp_path: Path, capsys) -> None:
    history_dir = tmp_path / "history"
    reports_dir = tmp_path / "reports"
    history_dir.mkdir()
    (history_dir / "report_2026-01-02_073000.json").write_text(
        json.dumps(_history_payload("watch"), ensure_ascii=False),
        encoding="utf-8",
    )
    prices_path = tmp_path / "prices.json"
    prices_path.write_text(
        json.dumps(
            {
                "prices": [
                    {"date": "2026-01-02", "price": 100.0},
                    {"date": "2026-04-06", "price": 101.0},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert main(["--history-dir", str(history_dir), "--price-points-json", str(prices_path), "--reports-dir", str(reports_dir)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "ok"
    assert printed["price_point_count"] == 2


def test_main_uses_default_price_points_path(tmp_path: Path, capsys, monkeypatch) -> None:
    reports_dir = tmp_path / "project" / "reports"
    history_dir = reports_dir / "history"
    history_dir.mkdir(parents=True)
    (history_dir / "report_2026-01-02_073000.json").write_text(
        json.dumps(_history_payload("wait"), ensure_ascii=False),
        encoding="utf-8",
    )
    (reports_dir / "validation_prices.json").write_text(
        json.dumps(
            [
                {"date": "2026-01-02", "price": 100.0},
                {"date": "2026-04-06", "price": 101.0},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert main([]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "ok"
    assert (reports_dir / "action_validation_summary.csv").exists()


def test_main_reports_missing_default_price_points_without_traceback(tmp_path: Path, capsys, monkeypatch) -> None:
    reports_dir = tmp_path / "project" / "reports"
    (reports_dir / "history").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    assert main([]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "missing_price_points"
    assert "Run project/validation_price_export.py first" in printed["message"]
    assert printed["price_point_count"] == 0
