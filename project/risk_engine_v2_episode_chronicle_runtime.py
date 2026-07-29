from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from project.pipeline import load_risk_engine_v2_episode_chronicle_summary
from project.risk_engine_v2_episode_chronicle import (
    ChronicleBuildError,
    ChronicleBusyError,
    run_risk_engine_v2_episode_chronicle,
)


def refresh_episode_chronicle_for_run(
    reports_dir: str | Path,
    config_path: str | Path,
    logger: Any,
    *,
    enabled: bool = True,
    disabled_reason: str | None = None,
    as_of: str | date | datetime | None = None,
    max_age_days: int = 3,
) -> dict[str, Any]:
    if not enabled:
        reason = disabled_reason or "この実行モードでは市場警戒年代記を更新しません"
        logger.info("Episode Chronicle refresh skipped: %s", reason)
        return _retained_archive_or_unavailable(Path(reports_dir), "unavailable", reason, logger)

    reports_path = Path(reports_dir)
    try:
        generation = run_risk_engine_v2_episode_chronicle(
            reports_dir=reports_path,
            config_path=config_path,
            as_of=as_of,
            max_age_days=max_age_days,
        )
    except ChronicleBusyError as exc:
        reason = f"市場警戒年代記は別の処理が更新中です: {exc}"
        logger.warning("Episode Chronicle refresh busy: %s", exc)
        return _retained_archive_or_unavailable(reports_path, "busy", reason, logger)
    except (ChronicleBuildError, FileNotFoundError) as exc:
        reason = f"市場警戒年代記の入力証拠を検証できないため更新を停止しました: {exc}"
        logger.warning("Episode Chronicle refresh unavailable: %s", exc)
        return _retained_archive_or_unavailable(reports_path, "unavailable", reason, logger)
    except Exception as exc:
        reason = f"市場警戒年代記の更新に失敗しました。既存成果物は保持されています: {exc}"
        logger.exception("Episode Chronicle refresh failed")
        return _retained_archive_or_unavailable(reports_path, "failed", reason, logger)

    refresh_status = str(generation.get("status") or "failed")
    if refresh_status not in {"generated", "no_change"}:
        reason = f"市場警戒年代記の更新結果を確認できません: {refresh_status}"
        logger.error("Episode Chronicle returned an unsupported status: %s", refresh_status)
        return _retained_archive_or_unavailable(reports_path, "failed", reason, logger)

    summary = load_risk_engine_v2_episode_chronicle_summary(reports_path)
    if summary.get("status") != "ready":
        reason = str(summary.get("reason") or "生成後の市場警戒年代記を検証できません")
        logger.error("Episode Chronicle output is not viewable after refresh: %s", reason)
        return _unavailable_result("failed", reason)

    ready_summary = dict(summary)
    ready_summary["refresh_status"] = refresh_status
    logger.info(
        "Episode Chronicle refresh completed (status=%s, episodes=%s).",
        refresh_status,
        ready_summary.get("episode_count", 0),
    )
    return {
        "status": refresh_status,
        "viewable": True,
        "reason": None,
        "summary": ready_summary,
        "source_fingerprint": generation.get("source_fingerprint"),
        "json_path": generation.get("json_path"),
        "html_path": generation.get("html_path"),
    }


def _retained_archive_or_unavailable(
    reports_path: Path,
    refresh_status: str,
    refresh_reason: str,
    logger: Any,
) -> dict[str, Any]:
    summary = load_risk_engine_v2_episode_chronicle_summary(reports_path)
    if summary.get("status") != "ready":
        return _unavailable_result(refresh_status, refresh_reason)

    retained_summary = dict(summary)
    retained_summary.update(
        {
            "refresh_status": refresh_status,
            "archive_status": "retained",
            "freshness_status": "historical",
            "reason": f"{refresh_reason} 保存済みの市場警戒年代記は引き続き閲覧できます。",
        }
    )
    logger.info(
        "Episode Chronicle refresh did not complete, but the validated retained archive remains viewable "
        "(status=%s, episodes=%s).",
        refresh_status,
        retained_summary.get("episode_count", 0),
    )
    return {
        "status": refresh_status,
        "viewable": True,
        "reason": refresh_reason,
        "summary": retained_summary,
    }


def _unavailable_result(status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "viewable": False,
        "reason": reason,
        "summary": {
            "status": status,
            "refresh_status": status,
            "reason": reason,
            "policy_status": "diagnostic_only_not_promoted",
            "affects_final_action": False,
            "promotion_allowed": False,
        },
    }
