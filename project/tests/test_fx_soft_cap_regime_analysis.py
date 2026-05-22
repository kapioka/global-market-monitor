from __future__ import annotations

from pathlib import Path

from project.fx_soft_cap_regime_analysis import build_fx_soft_cap_regime_analysis, run_fx_soft_cap_regime_analysis


def test_regime_analysis_summarizes_candidate_stability() -> None:
    long_range = {
        "replay_start": "2020-01-03",
        "replay_end": "2026-05-15",
        "regime_breakdown": {
            "2020_crash_recovery": [
                _row("without_equity_trend_guard", 3, 1, 0, 0.01, -0.04),
                _row("fx_soft_cap", 4, 1, 1, -0.02, -0.12),
            ],
            "2022_rate_shock": [
                _row("without_equity_trend_guard", 2, 0, 0, 0.02, -0.05),
                _row("fx_soft_cap", 3, 0, 1, -0.01, -0.11),
            ],
        },
    }

    payload = build_fx_soft_cap_regime_analysis(long_range)

    assert payload["status"] == "ok"
    assert payload["best_candidate"] == "without_equity_trend_guard"
    assert payload["candidate_stability"][0]["candidate"] == "without_equity_trend_guard"


def test_regime_analysis_writes_reports(tmp_path: Path) -> None:
    source = tmp_path / "long.json"
    source.write_text(
        """
        {
          "replay_start": "2024-01-01",
          "replay_end": "2026-05-21",
          "regime_breakdown": {
            "2024_2026_recent": [
              {
                "candidate": "without_equity_trend_guard",
                "buy_candidate_count": 1,
                "correctly_blocked_count": 0,
                "missed_good_candidate_count": 0,
                "return_summary": {"13w": {"mean_excess_return": 0.01, "worst_max_drawdown": -0.03}}
              }
            ]
          }
        }
        """,
        encoding="utf-8",
    )

    result = run_fx_soft_cap_regime_analysis(source, tmp_path)

    assert result["status"] == "ok"
    assert (tmp_path / "fx_soft_cap_regime_analysis.json").exists()
    assert (tmp_path / "fx_soft_cap_regime_analysis.md").exists()


def _row(candidate: str, count: int, overblocked: int, blocked: int, excess: float, worst_dd: float) -> dict[str, object]:
    return {
        "candidate": candidate,
        "buy_candidate_count": count,
        "overblocked_by_current_count": overblocked,
        "correctly_blocked_count": blocked,
        "missed_good_candidate_count": 0,
        "return_summary": {"13w": {"mean_excess_return": excess, "worst_max_drawdown": worst_dd}},
    }
