from __future__ import annotations

from collections import Counter
from typing import Any


def resolve_event_weekly_records(events: list[dict[str, Any]], weekly_timeline: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("record_id")): row for row in weekly_timeline if isinstance(row, dict) and row.get("record_id")}
    resolved_events: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    duplicate_refs: list[dict[str, Any]] = []
    all_ids: list[str] = []
    for event in events:
        seen: set[str] = set()
        records: list[dict[str, Any]] = []
        missing: list[str] = []
        duplicates: list[str] = []
        for raw_id in event.get("weekly_timeline_record_ids", []) or []:
            record_id = str(raw_id)
            if record_id in seen:
                duplicates.append(record_id)
                continue
            seen.add(record_id)
            if record_id not in by_id:
                missing.append(record_id)
                continue
            records.append(by_id[record_id])
            all_ids.append(record_id)
        records = sorted(records, key=lambda row: (str(row.get("date") or ""), str(row.get("record_id") or "")))
        row = {
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "event_anchor_date": event.get("event_anchor_date"),
            "records": records,
            "record_ids": [str(record.get("record_id")) for record in records],
            "missing_record_ids": missing,
            "duplicate_record_ids": duplicates,
            "resolution_status": "resolved" if not missing and not duplicates else "blocked",
        }
        resolved_events.append(row)
        if missing:
            unresolved.append({"event_id": event.get("event_id"), "missing_record_ids": missing})
        if duplicates:
            duplicate_refs.append({"event_id": event.get("event_id"), "duplicate_record_ids": duplicates})
    counts = Counter(all_ids)
    shared_ids = sorted(record_id for record_id, count in counts.items() if count > 1)
    unique_records = sorted((by_id[record_id] for record_id in set(all_ids) if record_id in by_id), key=lambda row: str(row.get("date") or ""))
    return {
        "status": "resolved" if not unresolved and not duplicate_refs else "blocked",
        "event_count": len(events),
        "weekly_timeline_count": len(weekly_timeline),
        "unique_resolved_weekly_count": len(unique_records),
        "unresolved_event_record_reference_count": sum(len(row["missing_record_ids"]) for row in unresolved),
        "duplicate_event_record_reference_count": sum(len(row["duplicate_record_ids"]) for row in duplicate_refs),
        "shared_weekly_record_reference_count": len(shared_ids),
        "unresolved": unresolved,
        "duplicates": duplicate_refs,
        "shared_record_ids": shared_ids,
        "events": resolved_events,
        "unique_records": unique_records,
    }
