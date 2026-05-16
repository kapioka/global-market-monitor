from __future__ import annotations

import json
from pathlib import Path

from project.risk_line_threshold_store import (
    ACTIVE_THRESHOLDS_PATH,
    PROPOSED_THRESHOLDS_PATH,
    build_threshold_diff,
    default_active_threshold_payload,
    load_threshold_definitions,
)


def test_threshold_store_loads_active_definitions():
    definitions = load_threshold_definitions(ACTIVE_THRESHOLDS_PATH)
    assert "SPY" in definitions
    assert definitions["SPY"]["thresholds"]["warning"]["feature"] == "drawdown_13w"


def test_threshold_diff_detects_changed_stage():
    active = default_active_threshold_payload()
    proposed = json.loads(json.dumps(active))
    proposed["threshold_set"]["version"] = "proposed-test"
    proposed["indicators"]["SPY"]["thresholds"]["warning"]["threshold"] = -0.03

    diff = build_threshold_diff(active, proposed)

    changed = [row for row in diff["changes"] if row["ticker"] == "SPY" and row["stage"] == "warning"]
    assert changed
    assert changed[0]["change_type"] == "changed"


def test_threshold_files_exist():
    assert Path(ACTIVE_THRESHOLDS_PATH).exists()
    assert Path(PROPOSED_THRESHOLDS_PATH).exists()
