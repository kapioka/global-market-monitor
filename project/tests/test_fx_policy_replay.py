from __future__ import annotations

from project.fx_policy_replay import build_fx_policy_replay, render_fx_policy_replay_markdown


def test_fx_policy_replay_compares_candidates_and_target_case():
    history = [
        {
            "generated_at": "2026-05-07T07:30:00",
            "japan_risk": {"level": "moderate", "flags": ["foreign_asset_fx_headwind"]},
            "spot_signal": {
                "legacy_action": "buy_window",
                "action": "watch",
                "blocker_assessment": {"flags": ["japan_fx_risk_moderate", "foreign_asset_fx_headwind"]},
            },
        }
    ]
    prices = [
        {"date": "2026-05-07T00:00:00", "price": 100.0},
        {"date": "2026-08-08T00:00:00", "price": 100.0},
    ]

    payload = build_fx_policy_replay(history, prices, {"spot_score_watch": 0.45, "spot_score_buy": 0.65})

    soft = next(row for row in payload["candidates"] if row["candidate"] == "fx_soft_cap")
    note = next(row for row in payload["candidates"] if row["candidate"] == "fx_note_only")
    assert soft["final_buy_candidate_count"] == 1
    assert note["final_buy_window_count"] == 1
    assert payload["target_case"]["candidate_actions"]["fx_soft_cap"]["final_action"] == "buy_candidate"
    assert "FX policy replay" in render_fx_policy_replay_markdown(payload)
