from __future__ import annotations

from project.buy_unlock_conditions import build_buy_unlock_conditions


def test_buy_unlock_conditions_for_fx_risk() -> None:
    payload = build_buy_unlock_conditions(
        {"primary_blocker": "fx_risk"},
        {
            "risk_lines": {"stage_key": "normal"},
            "japan_risk": {"usd_jpy": {"change_4w": 0.04}},
        },
    )

    assert payload["affects_final_action"] is False
    assert payload["unlock_conditions"][0]["condition"] == "foreign_asset_fx_headwind resolves"
    assert payload["unlock_conditions"][1]["current_value"] == 0.04


def test_buy_unlock_conditions_fallback() -> None:
    payload = build_buy_unlock_conditions({"primary_blocker": None}, {})

    assert payload["primary_blocker"] == "unknown"
    assert payload["unlock_conditions"]
