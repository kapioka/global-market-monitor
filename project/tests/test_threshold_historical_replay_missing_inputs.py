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
