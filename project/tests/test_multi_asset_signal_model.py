from __future__ import annotations

import json
from pathlib import Path

from project.multi_asset_signal_model import ALLOWED_STATUSES, build_multi_asset_signal, build_multi_asset_signals


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "multi_asset_signal_cases_v0.8.23.json"


def _cases() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


def test_multi_asset_signal_model_covers_fixture_cases() -> None:
    signals = build_multi_asset_signals(_cases())

    by_case = {case["case_id"]: signal for case, signal in zip(_cases(), signals, strict=True)}
    assert by_case["gold_available"]["status"] == "watch"
    assert by_case["gold_missing"]["status"] == "unavailable"
    assert by_case["bond_available"]["status"] == "watch"
    assert by_case["bond_missing"]["status"] == "unavailable"
    assert by_case["cash_wait"]["status"] == "wait"
    assert by_case["mixed_partial_data"]["status"] == "informational"


def test_multi_asset_signal_output_contract_matches_fixture_policy() -> None:
    for case in _cases():
        signal = build_multi_asset_signal(case)

        assert set(signal) == {
            "asset_class",
            "symbol",
            "display_name",
            "source_data_available",
            "status",
            "role",
            "reason_category",
            "caution_required",
            "caution",
            "must_not_affect_final_action",
            "must_not_affect_buy_readiness_score",
        }
        assert signal["status"] in ALLOWED_STATUSES
        assert signal["caution_required"] is True
        assert signal["must_not_affect_final_action"] is True
        assert signal["must_not_affect_buy_readiness_score"] is True


def test_missing_or_partial_data_never_creates_strong_candidate_status() -> None:
    for case in _cases():
        signal = build_multi_asset_signal(case)
        assert signal["status"] not in {"buy", "safe", "recommended", "certain", "candidate"}

        if not case["source_data_available"] or case["expected_missing_data_representation"] == "partial_data_only":
            assert signal["status"] in {"unavailable", "informational", "wait"}


def test_multi_asset_signal_model_avoids_forbidden_advice_phrases() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    rendered = json.dumps(build_multi_asset_signals(fixture["cases"]), ensure_ascii=False)

    for forbidden in fixture["forbidden_wording"]:
        assert forbidden not in rendered
