from __future__ import annotations

import json
from pathlib import Path

from project.risk_engine_v2_replay import (
    build_risk_engine_v2_replay,
    render_risk_engine_v2_replay_markdown,
    run_risk_engine_v2_replay,
)


def _row(ticker: str, level: str = "normal", pressure: float = 0.0, change_4w: float = 0.0) -> dict:
    return {
        "ticker": ticker,
        "line_level": level,
        "pressure_score": pressure,
        "change_1w": change_4w / 4,
        "change_4w": change_4w,
        "change_12w": change_4w,
        "quality_flags": ["valid"],
        "stage_eligible": True,
        "limitations": [],
    }


def _history(generated_at: str, oil_change: float = 0.0) -> dict:
    return {
        "generated_at": generated_at,
        "risk_lines": {"stage_key": "normal", "composite_risk_score": 10.0},
        "buy_decision_card": {"final_action": "watch"},
        "risk_monitor": [
            _row("SPY", "normal", 0.0, 0.02),
            _row("^VIX", "normal", 0.0),
            _row("^MOVE", "normal", 0.0),
            _row("HYG/LQD", "normal", 0.0),
            _row("^TNX", "warning" if oil_change > 0 else "normal", 0.4 if oil_change > 0 else 0.0),
            _row("DX-Y.NYB", "normal", 0.0),
            _row("CL=F", "normal", 0.0, oil_change),
        ],
        "credit_monitor": [],
        "inflation_monitor": [],
    }


def _config() -> dict:
    return {
        "paths": {"reports_dir": "project/reports"},
        "risk_engine_v2": {
            "mode": "shadow",
            "minimum_eligible_domain_coverage": 0.75,
            "oil": {"inflation_shock_return_4w": 0.08, "demand_collapse_return_4w": -0.12},
            "persistence": {
                "warning_entry_observations": 2,
                "warning_entry_window": 3,
                "danger_entry_consecutive": 2,
                "exit_consecutive": 2,
            },
        },
    }


def _prices() -> list[dict]:
    return [
        {"date": "2026-01-01", "price": 100.0},
        {"date": "2026-01-29", "price": 104.0},
        {"date": "2026-04-02", "price": 92.0},
        {"date": "2026-07-02", "price": 110.0},
    ]


def test_build_risk_engine_v2_replay_keeps_policy_diagnostic_only():
    payload = build_risk_engine_v2_replay(
        [_history("2026-01-01T07:30:00", 0.06), _history("2026-01-08T07:30:00", 0.07)],
        _config(),
        price_points=_prices(),
    )

    assert payload["status"] == "ok"
    assert payload["affects_final_action"] is False
    assert payload["policy_status"] == "diagnostic_only_not_promoted"
    assert payload["decision"]["promotion_allowed"] is False
    assert payload["summary"]["total_cases"] == 2
    assert payload["summary"]["outcome_summary"]["status"] == "ok"
    assert payload["summary"]["outcome_summary"]["usable_cases"] == 2
    oil_counts = payload["summary"]["oil_status_counts"]
    assert oil_counts.get("inflation_watch", 0) + oil_counts.get("inflation_stress", 0) == 2
    assert payload["cases"][1]["domain_confirmed_stage"] == "warning"
    assert payload["cases"][1]["domain_persistence_gap_reset"] is False
    assert payload["cases"][0]["domain_evidence_schema_version"] == "risk_engine_v2.domain_evidence.v1"
    assert {row["domain_id"] for row in payload["cases"][0]["domain_evidence"]} == {
        "equity",
        "equity_volatility",
        "bond_volatility",
        "credit",
        "rates",
        "usd_funding",
        "commodity_inflation",
    }
    assert payload["cases"][0]["global_policy_evidence"]["resulting_confirmed_stage"] == payload["cases"][0]["domain_confirmed_stage"]
    assert payload["cases"][0]["outcome"]["forward_returns"]["4w"] == 0.04
    path_13w = payload["cases"][0]["outcome"]["drawdown_paths"]["13w"]
    assert path_13w[0]["date"] == "2026-01-01"
    assert any(point["date"] == "2026-04-02" and point["drawdown_from_anchor"] == -0.08 for point in path_13w)
    assert "diagnostic only" in render_risk_engine_v2_replay_markdown(payload)


def test_domain_evidence_records_suppressed_and_fallback_reasons():
    payload = build_risk_engine_v2_replay(
        [_history("2026-01-01T07:30:00", 0.0)],
        _config(),
        price_points=_prices(),
    )

    credit = next(row for row in payload["cases"][0]["domain_evidence"] if row["domain_id"] == "credit")

    assert credit["primary_fallback_status"] == "fallback"
    assert credit["quality_flags"]
    assert "confidence=fallback" in credit["reasons"]
    assert "official OAS unavailable; HYG/LQD is a proxy fallback" in credit["limitations"]


def test_sparse_replay_dates_do_not_count_as_persistence_confirmation():
    payload = build_risk_engine_v2_replay(
        [_history("2026-01-01T07:30:00", 0.06), _history("2026-04-02T07:30:00", 0.07)],
        _config(),
        price_points=_prices(),
    )

    assert payload["cases"][1]["domain_candidate_stage"] == "warning"
    assert payload["cases"][1]["domain_confirmed_stage"] == "normal"
    assert payload["cases"][1]["domain_persistence_gap_reset"] is True
    assert payload["cases"][1]["domain_persistence_gap_days"] == 91


def test_run_risk_engine_v2_replay_writes_json_and_markdown(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    reports_dir = tmp_path / "reports"
    history_dir = reports_dir / "history"
    history_dir.mkdir(parents=True)
    config_path.write_text(
        """
paths:
  logs_dir: logs
  reports_dir: reports
  sample_output_dir: sample_output
  cache_dir: cache
schema_version: 1
app:
  report_title: Test
  log_level: INFO
data:
  period_years: 1
  interval: 1wk
  min_history_points: 5
  max_analogue_results: 1
  use_sample_on_failure: true
  monitor_windows_weeks:
    short: 1
    medium: 4
    long: 12
  zscore_window_weeks: 20
tickers:
  asset_classes:
    Global: ACWI
    Stocks: SPY
  fx:
    USDJPY: USDJPY=X
  credit:
    HYG: HYG
    LQD: LQD
  inflation:
    Oil: CL=F
    Gold: GC=F
    Dollar: DX-Y.NYB
  risk_indicators:
    SPY: SPY
    HYG: HYG
    LQD: LQD
    VIX: ^VIX
    MOVE: ^MOVE
    WTI: CL=F
    Brent: BZ=F
    DXY: DX-Y.NYB
    US10Y: ^TNX
thresholds:
  spot_score_buy: 0.65
  spot_score_watch: 0.45
weights:
  regime: 1.0
risk_engine_v2:
  mode: shadow
  minimum_eligible_domain_coverage: 0.75
  persistence:
    warning_entry_observations: 2
    warning_entry_window: 3
    danger_entry_consecutive: 2
    exit_consecutive: 2
  oil:
    inflation_shock_return_4w: 0.08
    demand_collapse_return_4w: -0.12
""",
        encoding="utf-8",
    )
    (history_dir / "report_2026-01-01_073000.json").write_text(json.dumps(_history("2026-01-01T07:30:00")), encoding="utf-8")
    (reports_dir / "validation_prices.json").write_text(json.dumps({"prices": _prices()}), encoding="utf-8")

    result = run_risk_engine_v2_replay(config_path=config_path, reports_dir=reports_dir)

    assert result["status"] == "ok"
    assert result["outcome_status"] == "ok"
    assert result["affects_final_action"] is False
    assert (reports_dir / "risk_engine_v2_replay.json").exists()
    assert (reports_dir / "risk_engine_v2_replay.md").exists()
