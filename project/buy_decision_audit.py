from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project.buy_decision_card import build_buy_decision_card


def build_buy_decision_audit(report: dict[str, Any]) -> dict[str, Any]:
    card = report.get("buy_decision_card") or build_buy_decision_card(report)
    spot_signal = report.get("spot_signal") or {}
    return {
        "status": "ok",
        "generated_at": report.get("generated_at"),
        "policy_status": "explanatory_only",
        "affects_final_action": False,
        "action_layers": spot_signal.get("action_layers", {}),
        "buy_decision_card": card,
        "buy_readiness_score": card.get("buy_readiness_score"),
        "readiness_level": card.get("readiness_level"),
        "blocker_breakdown": card.get("blocker_breakdown", {}),
        "unlock_conditions": card.get("unlock_conditions", []),
        "historical_evidence_summary": {
            "buy_window_diagnostics": report.get("buy_window_diagnostics", {}),
            "action_validation": report.get("action_validation", {}),
        },
        "fx_diagnostics_summary": {
            "fx_policy_diagnostics": report.get("fx_policy_diagnostics", {}),
            "fx_soft_cap_watchlist": report.get("fx_soft_cap_watchlist", {}),
            "fx_soft_cap_historical_replay": report.get("fx_soft_cap_historical_replay", {}),
        },
        "regime_aware_diagnostics_summary": report.get("regime_aware_fx_policy_replay", {}),
        "why_not_buy_window": _why_not_buy_window(card),
        "caveats": [
            "buy_readiness_score is explanatory only.",
            "unlock_conditions are not automatic buy instructions.",
            "final_action remains controlled by active thresholds and reliability_policy.",
        ],
    }


def write_buy_decision_audit(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "buy_decision_audit.json"
    md_path = reports_path / "buy_decision_audit.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_buy_decision_audit_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_buy_decision_audit_markdown(payload: dict[str, Any]) -> str:
    card = payload.get("buy_decision_card") or {}
    blockers = (payload.get("blocker_breakdown") or {}).get("blockers") or []
    unlock = payload.get("unlock_conditions") or []
    lines = [
        "# Buy Decision Audit",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- affects_final_action: {payload.get('affects_final_action')}",
        f"- final_action: {card.get('final_action')}",
        f"- market_raw_action: {card.get('market_raw_action')}",
        f"- risk_adjusted_action: {card.get('risk_adjusted_action')}",
        f"- buy_readiness_score: {card.get('buy_readiness_score')} / 100",
        f"- readiness_level: {card.get('readiness_level')}",
        f"- primary_blocker: {card.get('primary_blocker')}",
        "",
        "## blockers",
    ]
    lines.extend(f"- {row.get('blocker')}: {row.get('severity')} / {', '.join(row.get('reasons', []))}" for row in blockers)
    if not blockers:
        lines.append("- none")
    lines.append("")
    lines.append("## unlock conditions")
    lines.extend(f"- {row.get('condition')}: current={row.get('current_value')} -> target={row.get('target_state')}" for row in unlock)
    if not unlock:
        lines.append("- none")
    lines.append("")
    lines.append("## why not buy_window")
    lines.extend(f"- {reason}" for reason in payload.get("why_not_buy_window", []))
    return "\n".join(lines) + "\n"


def run_buy_decision_audit(
    report_json: str | Path = "project/reports/report_summary.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    report_path = Path(report_json)
    if not report_path.exists():
        return {"status": "missing_report", "report_json": str(report_path)}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    payload = build_buy_decision_audit(report)
    json_path, md_path = write_buy_decision_audit(payload, reports_dir)
    return {
        "status": payload["status"],
        "buy_readiness_score": payload.get("buy_readiness_score"),
        "primary_blocker": (payload.get("buy_decision_card") or {}).get("primary_blocker"),
        "json_path": str(json_path),
        "markdown_path": str(md_path),
    }


def _why_not_buy_window(card: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if card.get("final_action") != "buy_window":
        reasons.append(f"final_action is {card.get('final_action')}, not buy_window")
    if card.get("market_raw_action") != card.get("risk_adjusted_action"):
        reasons.append(f"risk adjustment changed {card.get('market_raw_action')} to {card.get('risk_adjusted_action')}")
    if card.get("primary_blocker"):
        reasons.append(f"primary blocker is {card.get('primary_blocker')}")
    if not reasons:
        reasons.append("no blocker summary available")
    return reasons


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build buy decision audit report.")
    parser.add_argument("--report-json", default="project/reports/report_summary.json")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_buy_decision_audit(args.report_json, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
