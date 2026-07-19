from __future__ import annotations

from project.risk_engine_v2_event_resolver import resolve_event_weekly_records


def test_event_weekly_resolver_rejects_unknown_and_duplicate_ids() -> None:
    result = resolve_event_weekly_records(
        [
            {
                "event_id": "event-1",
                "event_type": "material_drawdown",
                "event_anchor_date": "2026-01-01",
                "weekly_timeline_record_ids": ["week:2026-01-01", "week:2026-01-01", "week:missing"],
            }
        ],
        [{"record_id": "week:2026-01-01", "date": "2026-01-01", "confirmed_stage": "warning"}],
    )

    assert result["status"] == "blocked"
    assert result["unresolved_event_record_reference_count"] == 1
    assert result["duplicate_event_record_reference_count"] == 1
