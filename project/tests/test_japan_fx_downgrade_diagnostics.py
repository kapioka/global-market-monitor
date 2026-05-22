from __future__ import annotations

from project.japan_fx_downgrade_diagnostics import build_japan_fx_downgrade_diagnostics, render_japan_fx_downgrade_markdown


def test_japan_fx_downgrade_tracks_fx_downgraded_buy_window():
    history = [
        {
            "generated_at": "2026-01-01T07:30:00",
            "japan_risk": {"level": "moderate", "flags": ["foreign_asset_fx_headwind"]},
            "risk_lines": {"stage_key": "normal"},
            "spot_signal": {
                "action_layers": {
                    "market_raw_action": "buy_window",
                    "risk_adjusted_action": "watch",
                    "final_action": "watch",
                },
                "blocker_assessment": {"flags": ["japan_fx_risk_moderate", "foreign_asset_fx_headwind"]},
            },
        }
    ]
    prices = [
        {"date": "2026-01-01T00:00:00", "price": 100.0},
        {"date": "2026-04-03T00:00:00", "price": 110.0},
    ]

    payload = build_japan_fx_downgrade_diagnostics(history, prices)

    assert payload["raw_buy_window_downgraded_by_fx_count"] == 1
    assert payload["japan_fx_risk_moderate_count"] == 1
    assert payload["foreign_asset_fx_headwind_count"] == 1
    assert payload["cases"][0]["generated_at"] == "2026-01-01T07:30:00"
    assert "raw buy_window downgraded by FX: 1" in render_japan_fx_downgrade_markdown(payload)


def test_japan_fx_downgrade_handles_no_cases():
    payload = build_japan_fx_downgrade_diagnostics([], [])

    assert payload["status"] == "ok"
    assert payload["cases"] == []
    assert "降格ケースはありません" in render_japan_fx_downgrade_markdown(payload)
