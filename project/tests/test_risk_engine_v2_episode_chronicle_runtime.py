from __future__ import annotations

import logging

from project.risk_engine_v2_episode_chronicle import ChronicleBuildError, ChronicleBusyError
from project.risk_engine_v2_episode_chronicle_runtime import refresh_episode_chronicle_for_run


def _ready_summary() -> dict[str, object]:
    return {
        "status": "ready",
        "freshness_status": "current",
        "episode_count": 18,
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "promotion_allowed": False,
        "page_filename": "risk_engine_v2_episode_chronicle.html",
    }


def test_refresh_returns_validated_ready_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.run_risk_engine_v2_episode_chronicle",
        lambda **_kwargs: {
            "status": "generated",
            "source_fingerprint": "abc",
            "json_path": "chronicle.json",
            "html_path": "chronicle.html",
        },
    )
    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.load_risk_engine_v2_episode_chronicle_summary",
        lambda _path: _ready_summary(),
    )

    result = refresh_episode_chronicle_for_run(tmp_path, tmp_path / "config.yaml", logging.getLogger("test"))

    assert result["status"] == "generated"
    assert result["publishable"] is True
    assert result["summary"]["status"] == "ready"
    assert result["summary"]["refresh_status"] == "generated"
    assert result["source_fingerprint"] == "abc"


def test_refresh_no_change_uses_same_validated_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.run_risk_engine_v2_episode_chronicle",
        lambda **_kwargs: {"status": "no_change", "source_fingerprint": "same"},
    )
    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.load_risk_engine_v2_episode_chronicle_summary",
        lambda _path: _ready_summary(),
    )

    result = refresh_episode_chronicle_for_run(tmp_path, tmp_path / "config.yaml", logging.getLogger("test"))

    assert result["status"] == "no_change"
    assert result["publishable"] is True
    assert result["summary"]["refresh_status"] == "no_change"


def test_disabled_refresh_never_calls_generator(monkeypatch, tmp_path) -> None:
    def fail_if_called(**_kwargs):
        raise AssertionError("generator must not run")

    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.run_risk_engine_v2_episode_chronicle",
        fail_if_called,
    )

    result = refresh_episode_chronicle_for_run(
        tmp_path,
        tmp_path / "config.yaml",
        logging.getLogger("test"),
        enabled=False,
        disabled_reason="sample-only skip",
    )

    assert result["status"] == "unavailable"
    assert result["publishable"] is False
    assert result["summary"]["affects_final_action"] is False
    assert "sample-only" in result["summary"]["reason"]


def test_busy_refresh_is_non_publishable_and_does_not_load_old_output(monkeypatch, tmp_path) -> None:
    def raise_busy(**_kwargs):
        raise ChronicleBusyError("already active")

    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.run_risk_engine_v2_episode_chronicle",
        raise_busy,
    )
    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.load_risk_engine_v2_episode_chronicle_summary",
        lambda _path: (_ for _ in ()).throw(AssertionError("old output must not be presented as current")),
    )

    result = refresh_episode_chronicle_for_run(tmp_path, tmp_path / "config.yaml", logging.getLogger("test"))

    assert result["status"] == "busy"
    assert result["publishable"] is False
    assert result["summary"]["status"] == "busy"


def test_invalid_source_isolated_from_parent_run(monkeypatch, tmp_path) -> None:
    def raise_invalid(**_kwargs):
        raise ChronicleBuildError("freshness snapshot is stale")

    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.run_risk_engine_v2_episode_chronicle",
        raise_invalid,
    )

    result = refresh_episode_chronicle_for_run(tmp_path, tmp_path / "config.yaml", logging.getLogger("test"))

    assert result["status"] == "unavailable"
    assert result["publishable"] is False
    assert result["summary"]["policy_status"] == "diagnostic_only_not_promoted"
    assert result["summary"]["promotion_allowed"] is False


def test_unexpected_failure_isolated_and_reported(monkeypatch, tmp_path) -> None:
    def raise_unexpected(**_kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.run_risk_engine_v2_episode_chronicle",
        raise_unexpected,
    )

    result = refresh_episode_chronicle_for_run(tmp_path, tmp_path / "config.yaml", logging.getLogger("test"))

    assert result["status"] == "failed"
    assert result["publishable"] is False
    assert "既存成果物は保持" in result["reason"]


def test_generated_output_must_pass_summary_loader(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.run_risk_engine_v2_episode_chronicle",
        lambda **_kwargs: {"status": "generated"},
    )
    monkeypatch.setattr(
        "project.risk_engine_v2_episode_chronicle_runtime.load_risk_engine_v2_episode_chronicle_summary",
        lambda _path: {"status": "invalid", "reason": "contract mismatch"},
    )

    result = refresh_episode_chronicle_for_run(tmp_path, tmp_path / "config.yaml", logging.getLogger("test"))

    assert result["status"] == "failed"
    assert result["publishable"] is False
    assert result["summary"]["status"] == "failed"
