from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "verify_risk_engine_v2_artifacts.py"
SPEC = importlib.util.spec_from_file_location("verify_risk_engine_v2_artifacts", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _valid_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "ok",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "decision": {"promotion_allowed": False},
    }
    payload.update(updates)
    return payload


def test_verify_artifact_accepts_valid_diagnostic_contract(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(_valid_payload()), encoding="utf-8")

    assert MODULE.verify_artifact(path, {"status": "ok"}) == []


def test_verify_artifact_rejects_promotion_and_final_action_impact(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    path.write_text(
        json.dumps(
            _valid_payload(
                policy_status="promoted",
                affects_final_action=True,
                decision={"promotion_allowed": True},
            )
        ),
        encoding="utf-8",
    )

    violations = MODULE.verify_artifact(path, {"status": "ok"})

    assert any("policy_status" in violation for violation in violations)
    assert any("affects_final_action" in violation for violation in violations)
    assert any("promotion_allowed" in violation for violation in violations)


def test_verify_artifact_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    path.write_text("not-json", encoding="utf-8")

    violations = MODULE.verify_artifact(path, {"status": "ok"})

    assert len(violations) == 1
    assert violations[0].startswith("invalid JSON:")


def test_verifier_requires_episode_chronicle_shadow_contract() -> None:
    expected = MODULE.ARTIFACT_CONTRACTS["risk_engine_v2_episode_chronicle.json"]

    assert expected["status"] == "ready"
    assert expected["freshness_status"] == "current"
    assert expected["promotion_allowed"] is False
