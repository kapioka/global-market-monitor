from __future__ import annotations

import json
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "multi_asset_signal_cases_v0.8.23.json"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_multi_asset_signal_fixture_has_required_cases() -> None:
    data = _fixture()

    case_ids = {case["case_id"] for case in data["cases"]}
    assert case_ids == {
        "gold_available",
        "gold_missing",
        "bond_available",
        "bond_missing",
        "cash_wait",
        "mixed_partial_data",
    }


def test_multi_asset_signal_fixture_missing_data_policy_is_explicit() -> None:
    data = _fixture()

    expectations = data["global_expectations"]
    assert expectations["must_not_affect_final_action"] is True
    assert expectations["must_not_affect_buy_readiness_score"] is True
    assert expectations["must_not_mix_with_equity_buy_readiness"] is True
    assert expectations["no_fake_confidence_when_missing"] is True
    assert expectations["no_forced_candidate_when_source_data_unavailable"] is True

    cases = {case["case_id"]: case for case in data["cases"]}
    assert cases["gold_missing"]["expected_status"] == "not_available"
    assert cases["bond_missing"]["expected_status"] == "not_available"
    assert cases["mixed_partial_data"]["expected_status"] == "informational"
    assert cases["cash_wait"]["expected_status"] == "wait"


def test_multi_asset_signal_fixture_uses_non_advice_wording() -> None:
    data = _fixture()

    rendered_cases = json.dumps(data["cases"], ensure_ascii=False)
    for forbidden in data["forbidden_wording"]:
        assert forbidden not in rendered_cases

    for case in data["cases"]:
        assert case["expected_caution_required"] is True
        assert case["must_not_affect_final_action"] is True
        assert case["must_not_affect_buy_readiness_score"] is True
