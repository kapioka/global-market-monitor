from __future__ import annotations

from typing import Any


def build_buy_unlock_conditions(blocker_breakdown: dict[str, Any], report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = report or {}
    primary = blocker_breakdown.get("primary_blocker") or "unknown"
    conditions = _conditions_for(primary, report)
    return {
        "unlock_conditions": conditions,
        "condition_priority": [row["condition"] for row in conditions],
        "primary_blocker": primary,
        "affects_final_action": False,
        "policy_status": "explanatory_only",
    }


def _conditions_for(primary: str, report: dict[str, Any]) -> list[dict[str, Any]]:
    if primary == "fx_risk":
        return [
            _condition("外貨建て資産の為替逆風が解消する", "foreign_asset_fx_headwind", "逆風なし", "為替逆風が主な買い判断の阻害要因です。"),
            _condition(
                "USDJPYの4週変化が落ち着く", _usdjpy_change(report), "警戒帯の内側", "資産自体の強さと円安・円高の影響を分けて確認します。"
            ),
            _condition(
                "市場ストレス段階が通常または警戒内に収まる",
                _risk_stage(report),
                "通常または警戒",
                "市場全体のストレスが強い間は、為替だけを理由に判断を緩めません。",
            ),
        ]
    if primary == "risk_line":
        return [
            _condition(
                "市場ストレス段階が改善する",
                _risk_stage(report),
                "通常または警戒",
                "危険ラインの条件が解消してから、より強い買い候補表示を確認します。",
            ),
            _condition(
                "VIX・信用・金利の危険トリガーが解消する", _risk_reasons(report), "有効な危険トリガーなし", "危険ラインが買い判断の阻害要因です。"
            ),
        ]
    if primary == "credit_stress":
        return [_condition("信用市場の代理指標が改善する", "credit_stress", "中立または改善", "信用ストレスが買い候補化を妨げています。")]
    if primary == "rate_shock":
        return [_condition("金利ショックが弱まる", "rate_shock", "発生していない", "長期検証では金利ショック局面の買い候補は弱めでした。")]
    if primary == "data_quality":
        return [
            _condition(
                "データ信頼性が改善する",
                _reliability(report),
                "中または高、かつ判断許可あり",
                "データ品質により最終判断に上限がかかっています。",
            )
        ]
    if primary == "sample_only":
        return [
            _condition(
                "実データがサンプル代替を置き換える",
                _reliability(report),
                "サンプル代替による上限なし",
                "サンプルのみの出力を買いシグナルとして扱いません。",
            )
        ]
    if primary == "recovery_evidence_weak":
        return [
            _condition(
                "回復証拠が形成中以上になる",
                _recovery_grade(report),
                "形成中または確認済み",
                "回復証拠がまだ十分ではありません。",
            )
        ]
    if primary == "score_shortfall":
        return [
            _condition(
                "市場スコアが買い候補の目安に近づく",
                _score(report),
                "候補化の目安付近",
                "市場スコアが買い判断の目安を下回っています。",
            )
        ]
    if primary == "drawdown_guard":
        return [_condition("ドローダウン文脈が改善する", "drawdown_guard", "ガード非発動", "ドローダウンガードは診断専用です。")]
    return [
        _condition("市場スコア・ストレス段階・為替・データ品質を確認する", "-", "すべて問題なし", "単独で支配的な阻害要因は分類されていません。")
    ]


def _condition(condition: str, current: Any, target: str, reason: str) -> dict[str, Any]:
    return {
        "condition": condition,
        "current_value": current,
        "target_state": target,
        "reason": reason,
        "caveat": "これは説明用の確認条件であり、自動的な買い指示ではありません。",
    }


def _risk_stage(report: dict[str, Any]) -> str:
    return str((report.get("risk_lines") or {}).get("stage_key", "-"))


def _risk_reasons(report: dict[str, Any]) -> list[str]:
    return [str(reason) for reason in (report.get("risk_lines") or {}).get("reasons", [])[:3]]


def _reliability(report: dict[str, Any]) -> str:
    reliability = report.get("data_reliability") or {}
    return f"{_reliability_label(reliability.get('level', '-'))}, 判断許可={reliability.get('decision_allowed', '-')}"


def _recovery_grade(report: dict[str, Any]) -> str:
    return str(((report.get("spot_signal") or {}).get("recovery_evidence") or {}).get("grade", "-"))


def _score(report: dict[str, Any]) -> Any:
    return (report.get("score") or {}).get("total_score", ((report.get("spot_signal") or {}).get("score", "-")))


def _usdjpy_change(report: dict[str, Any]) -> Any:
    return ((report.get("japan_risk") or {}).get("usd_jpy") or {}).get("change_4w", "-")


def _reliability_label(value: Any) -> str:
    return {"high": "高", "medium": "中", "low": "低", "diagnostic": "診断用"}.get(str(value), str(value))
