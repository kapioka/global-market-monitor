from __future__ import annotations

from typing import Any

from project.action_schema import action_label_ja


def data_quality_markdown_lines(report: dict[str, Any]) -> list[str]:
    reliability = report.get("data_reliability", {})
    action_decision = report.get("spot_signal", {}).get("action_decision", {})
    return [
        f"- live 取得率: {_display_percent(reliability.get('live_ratio'))}",
        f"- データ品質上限: {action_label_ja(str(reliability.get('max_action', 'buy_window')))} / confidence 上限 {_display_compact_number(reliability.get('confidence_cap'), digits=2)}",
        f"- 代替取得内訳: proxy={reliability.get('proxy_fallback_count', 0)} / sample={reliability.get('sample_fallback_count', 0)} / unavailable={reliability.get('unavailable_count', 0)}",
        f"- 重要系列不足: {', '.join(reliability.get('critical_failures', [])) or 'なし'}",
        f"- データ品質による降格: {'あり' if action_decision.get('reliability_cap_applied') else 'なし'} / 理由 {', '.join(action_decision.get('cap_reason', [])) or reliability.get('reason_code', '-')}",
    ]


def data_quality_html_rows(report: dict[str, Any]) -> list[tuple[str, str]]:
    reliability = report.get("data_reliability", {})
    action_decision = report.get("spot_signal", {}).get("action_decision", {})
    return [
        ("判定信頼性", _jp_reliability(str(reliability.get("level", "high")))),
        ("live 取得率", _display_percent(reliability.get("live_ratio"))),
        (
            "データ品質上限",
            f"{action_label_ja(str(reliability.get('max_action', 'buy_window')))} / confidence {_display_compact_number(reliability.get('confidence_cap'), digits=2)}",
        ),
        (
            "代替取得内訳",
            f"proxy={reliability.get('proxy_fallback_count', 0)} / sample={reliability.get('sample_fallback_count', 0)} / unavailable={reliability.get('unavailable_count', 0)}",
        ),
        ("重要系列不足", ", ".join(reliability.get("critical_failures", [])) or "なし"),
        (
            "データ品質による降格",
            f"{'あり' if action_decision.get('reliability_cap_applied') else 'なし'} / {', '.join(action_decision.get('cap_reason', [])) or reliability.get('reason_code', '-')}",
        ),
    ]


def _jp_reliability(value: str) -> str:
    return {"high": "高", "medium": "中", "low": "低", "diagnostic": "診断用"}.get(value, value)


def _display_percent(value: Any) -> str:
    if value is None:
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{numeric:.0%}"


def _display_compact_number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)
