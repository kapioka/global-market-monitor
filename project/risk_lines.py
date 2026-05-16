from __future__ import annotations

from typing import Any


STAGE_LABELS = {
    "normal": "通常",
    "caution": "警戒",
    "credit_spillover_initial": "信用波及初期",
    "danger_line_reached": "危険ライン到達",
    "extreme_danger_line_reached": "非常に危険ライン到達",
    "data_unavailable": "判定保留",
}

STAGE_PENALTIES = {
    "normal": 0.0,
    "caution": 0.02,
    "credit_spillover_initial": 0.04,
    "danger_line_reached": 0.08,
    "extreme_danger_line_reached": 0.14,
    "data_unavailable": 0.0,
}

REQUIRED_INDICATORS = ("SPY", "HYG", "LQD", "HYG/LQD", "^VIX", "^MOVE", "CL=F", "BZ=F", "DX-Y.NYB", "^TNX")
STRICT_CORE_INDICATORS = ("SPY", "HYG/LQD", "^VIX", "^MOVE", "BZ=F", "^TNX", "DX-Y.NYB")


def evaluate_risk_lines(
    regime: dict[str, Any],
    cycle: dict[str, Any],
    credit_monitor: list[dict[str, Any]],
    inflation_monitor: list[dict[str, Any]],
    stress_monitor: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = [dict(row) for row in stress_monitor]
    by_ticker = {str(row.get("ticker")): row for row in rows}
    missing_indicators = [ticker for ticker in REQUIRED_INDICATORS if ticker not in by_ticker]
    strict_missing = [ticker for ticker in STRICT_CORE_INDICATORS if ticker not in by_ticker]
    warning_hits = [row for row in rows if _level_rank(row.get("line_level")) >= 1]
    danger_hits = [row for row in rows if _level_rank(row.get("line_level")) >= 2]
    extreme_hits = [row for row in rows if _level_rank(row.get("line_level")) >= 3]
    composite_risk_score = _composite_risk_score(rows)
    credit_flag = str(regime.get("credit_regime_flag", "neutral"))
    inflation_flag = str(regime.get("inflation_regime_flag", "neutral"))
    regime_label = str(regime.get("regime_label", ""))
    cycle_label = str(cycle.get("phase_label", ""))

    vix = by_ticker.get("^VIX")
    move = by_ticker.get("^MOVE")
    tnx = by_ticker.get("^TNX")
    wti = by_ticker.get("CL=F")
    brent = by_ticker.get("BZ=F")
    dxy = by_ticker.get("DX-Y.NYB")
    spy = by_ticker.get("SPY")
    ratio = by_ticker.get("HYG/LQD")
    hyg = by_ticker.get("HYG")
    lqd = by_ticker.get("LQD")

    oil_row = _worse_row(wti, brent)
    oil_warning = _at_least(oil_row, "warning")
    oil_danger = _at_least(oil_row, "danger")
    vix_persist_danger = _persisted_at_least(vix, "danger", 2)
    vix_persist_extreme = _persisted_at_least(vix, "danger", 3) or _persisted_at_least(vix, "extreme", 1)

    credit_initial = (
        _at_least(vix, "warning")
        and _at_least(tnx, "warning")
        and _at_least(spy, "warning")
        and (_at_least(ratio, "warning") or credit_flag in {"credit_stress_moderate", "credit_stress_severe"})
        and (oil_warning or _at_least(dxy, "warning") or inflation_flag in {"inflation_shock_broad", "inflation_shock_oil_only", "stagflation_warning"})
    )
    danger_line = (
        composite_risk_score >= 62
        or len(danger_hits) >= 3
        or vix_persist_danger
        or (_at_least(vix, "danger") and _at_least(tnx, "danger") and oil_danger)
        or (_at_least(ratio, "danger") and (_at_least(vix, "danger") or _at_least(move, "danger")))
    )
    extreme_line = (
        composite_risk_score >= 78
        or len(extreme_hits) >= 2
        or vix_persist_extreme
        or (_at_least(ratio, "extreme") and _at_least(vix, "danger") and _at_least(move, "danger"))
        or (credit_flag == "credit_stress_severe" and (_at_least(vix, "extreme") or _at_least(move, "extreme")) and oil_danger)
    )
    caution = (
        composite_risk_score >= 35
        or len(warning_hits) >= 3
        or (_at_least(vix, "warning") and _at_least(spy, "warning"))
        or (_at_least(tnx, "warning") and oil_warning)
    )

    if extreme_line:
        stage_key = "extreme_danger_line_reached"
    elif danger_line:
        stage_key = "danger_line_reached"
    elif credit_initial:
        stage_key = "credit_spillover_initial"
    elif caution:
        stage_key = "caution"
    else:
        stage_key = "normal"

    reasons = _build_reasons(
        credit_flag=credit_flag,
        inflation_flag=inflation_flag,
        regime_label=regime_label,
        cycle_label=cycle_label,
        vix=vix,
        move=move,
        tnx=tnx,
        oil_row=oil_row,
        dxy=dxy,
        spy=spy,
        ratio=ratio,
        hyg=hyg,
        lqd=lqd,
        danger_hits=danger_hits,
        extreme_hits=extreme_hits,
        composite_risk_score=composite_risk_score,
        strict_missing=strict_missing,
        missing_indicators=missing_indicators,
        vix_persist_danger=vix_persist_danger,
    )
    summary = _summary_for_stage(stage_key, reasons, strict_missing)
    strict_judgement_available = len(strict_missing) == 0
    precision_label = "厳密判定可" if strict_judgement_available else "厳密判定不可"
    decision_level, decision_flags, decision_summary = _decision_overlay(
        stage_key=stage_key,
        credit_flag=credit_flag,
        vix=vix,
        move=move,
        ratio=ratio,
        tnx=tnx,
        dxy=dxy,
        oil_row=oil_row,
    )

    return {
        "stage_key": stage_key,
        "stage_label": STAGE_LABELS[stage_key],
        "summary": summary,
        "reasons": reasons,
        "composite_risk_score": composite_risk_score,
        "warning_count": len(warning_hits),
        "danger_count": len(danger_hits),
        "extreme_count": len(extreme_hits),
        "danger_lines": [_line_name(row) for row in danger_hits],
        "extreme_lines": [_line_name(row) for row in extreme_hits],
        "penalty_hint": STAGE_PENALTIES[stage_key],
        "indicators": rows,
        "coverage_ratio": round(len(rows) / len(REQUIRED_INDICATORS), 4),
        "missing_indicators": missing_indicators,
        "strict_missing_indicators": strict_missing,
        "strict_judgement_available": strict_judgement_available,
        "precision_label": precision_label,
        "decision_level": decision_level,
        "decision_flags": decision_flags,
        "decision_summary": decision_summary,
    }


def _build_reasons(
    credit_flag: str,
    inflation_flag: str,
    regime_label: str,
    cycle_label: str,
    vix: dict[str, Any] | None,
    move: dict[str, Any] | None,
    tnx: dict[str, Any] | None,
    oil_row: dict[str, Any] | None,
    dxy: dict[str, Any] | None,
    spy: dict[str, Any] | None,
    ratio: dict[str, Any] | None,
    hyg: dict[str, Any] | None,
    lqd: dict[str, Any] | None,
    danger_hits: list[dict[str, Any]],
    extreme_hits: list[dict[str, Any]],
    composite_risk_score: float,
    strict_missing: list[str],
    missing_indicators: list[str],
    vix_persist_danger: bool,
) -> list[str]:
    reasons: list[str] = []
    if strict_missing:
        reasons.append(f"{', '.join(strict_missing)} が未取得のため、厳密な危険ライン判定はできていません。利用可能データでの暫定判定です。")
    elif missing_indicators:
        reasons.append(f"{', '.join(missing_indicators)} が未取得のため、一部補助指標を欠いた判定です。")
    if _at_least(hyg, "warning") and _at_least(lqd, "warning") and not _at_least(ratio, "danger"):
        reasons.append("HYG だけでなく LQD も重く、ハイイールド単独崩れより金利上昇の影響が社債全体に波及している形です。")
    if _at_least(ratio, "danger"):
        reasons.append("HYG/LQD の悪化が危険ラインに達しており、金利ショックだけでなく信用スプレッド拡大も意識すべき局面です。")
    elif _at_least(ratio, "warning"):
        reasons.append("HYG/LQD は悪化していますが、まだ信用危機本番を断定するより、信用波及の入口として扱う方が妥当です。")
    if _at_least(vix, "warning") and _at_least(tnx, "warning") and _at_least(spy, "warning") and (_at_least(oil_row, "warning") or _at_least(dxy, "warning") or inflation_flag in {"inflation_shock_broad", "stagflation_warning"}):
        reasons.append("インフレショック、金利上昇、株安の組み合わせが同時進行しており、二段下げリスクを押し上げています。")
    if vix_persist_danger:
        reasons.append("VIX の危険ライン到達が一時的ではなく、直近でも継続しているため、ボラティリティ上昇は定着寄りです。")
    if _at_least(move, "danger"):
        reasons.append("MOVE が高く、債券市場側のボラティリティも危険ラインに入っています。")
    if len(extreme_hits) >= 2:
        reasons.append("複数の重要指標が非常に危険ラインに入っており、局所的なノイズではなく複合ストレスとして扱うべき状態です。")
    elif len(danger_hits) >= 3:
        reasons.append("危険ライン到達の指標が複数あり、単一要因ではなく複合的な市場ストレスが発生しています。")
    if composite_risk_score >= 70:
        reasons.append(f"総合ストレス指数は {composite_risk_score:.1f} で、かなり高い領域です。")
    elif composite_risk_score >= 45:
        reasons.append(f"総合ストレス指数は {composite_risk_score:.1f} で、通常より明確に高い状態です。")
    if regime_label in {"risk_off", "credit_stress", "inflation_shock", "stagflation_warning"}:
        reasons.append(f"市場レジーム {regime_label} とサイクル {cycle_label} が、守り優先の判断を補強しています。")
    return reasons or ["主要指標はまだ危険ラインの手前で、複合ストレスは限定的です。"]


def _summary_for_stage(stage_key: str, reasons: list[str], strict_missing: list[str]) -> str:
    summaries = {
        "normal": "主要指標はまだ危険ラインの手前で、強い複合ストレスは確認されていません。",
        "caution": "警戒ラインに入った指標が増えており、通常モードより防御的に見るべき状態です。",
        "credit_spillover_initial": "かなり悪化したが、まだ全面的な信用危機本番ではなく、金利・原油ショックが信用へ波及し始めた段階です。",
        "danger_line_reached": "危険ライン到達の指標が複数あり、軽く見る段階は過ぎています。",
        "extreme_danger_line_reached": "非常に危険ラインが複数点灯しており、急速なストレス拡大を前提に扱うべき状態です。",
        "data_unavailable": "必要な主要指標が不足しているため、危険ライン判定を保留しています。",
    }
    summary = summaries.get(stage_key, reasons[0] if reasons else "-")
    if strict_missing:
        summary += f" ただし {', '.join(strict_missing)} が不足しているため、厳密な判定ではありません。"
    return summary


def _decision_overlay(
    stage_key: str,
    credit_flag: str,
    vix: dict[str, Any] | None,
    move: dict[str, Any] | None,
    ratio: dict[str, Any] | None,
    tnx: dict[str, Any] | None,
    dxy: dict[str, Any] | None,
    oil_row: dict[str, Any] | None,
) -> tuple[str, list[str], str]:
    flags: list[str] = []
    if stage_key == "extreme_danger_line_reached":
        flags.append("extreme_market_stress")
    elif stage_key == "danger_line_reached":
        flags.append("danger_market_stress")
    elif stage_key == "credit_spillover_initial":
        flags.append("credit_spillover_initial")
    elif stage_key == "caution":
        flags.append("broad_market_caution")

    if credit_flag == "credit_stress_severe":
        flags.append("credit_stress_severe")
    elif credit_flag == "credit_stress_moderate":
        flags.append("credit_stress_moderate")

    if _at_least(vix, "danger"):
        flags.append("vix_danger")
    elif _at_least(vix, "warning"):
        flags.append("vix_warning")
    if _at_least(move, "danger"):
        flags.append("move_danger")
    elif _at_least(move, "warning"):
        flags.append("move_warning")
    if _at_least(ratio, "danger"):
        flags.append("credit_ratio_danger")
    elif _at_least(ratio, "warning"):
        flags.append("credit_ratio_warning")
    if _at_least(tnx, "warning"):
        flags.append("rates_warning")
    if _at_least(dxy, "warning"):
        flags.append("dollar_warning")
    if _at_least(oil_row, "warning"):
        flags.append("oil_warning")

    if stage_key in {"extreme_danger_line_reached", "danger_line_reached"} or credit_flag == "credit_stress_severe":
        level = "block"
        summary = "市場ストレスが強く、追加投資判断はブロックすべき状態です。"
    elif stage_key in {"credit_spillover_initial", "caution"} or credit_flag == "credit_stress_moderate":
        level = "caution"
        summary = "改善が見えても、まだ騙し上昇を警戒して買い判断を抑えるべき状態です。"
    elif any(flag in flags for flag in {"rates_warning", "dollar_warning", "oil_warning", "vix_warning", "move_warning"}):
        level = "caution"
        summary = "強いブロックではありませんが、追加投資は慎重に監視したい状態です。"
    else:
        level = "none"
        summary = "大きな blocker は確認されておらず、上昇再開の証拠を素直に評価しやすい状態です。"
    return level, flags, summary


def _composite_risk_score(rows: list[dict[str, Any]]) -> float:
    weighted = 0.0
    total_weight = 0.0
    for row in rows:
        weight = float(row.get("weight", 1.0) or 1.0)
        pressure = float(row.get("pressure_score", 0.5) or 0.5)
        weighted += weight * pressure
        total_weight += weight
    if total_weight <= 0:
        return 50.0
    return round((weighted / total_weight) * 100, 2)


def _worse_row(*rows: dict[str, Any] | None) -> dict[str, Any] | None:
    present = [row for row in rows if row is not None]
    if not present:
        return None
    return max(present, key=lambda row: (_level_rank(row.get("line_level")), float(row.get("pressure_score", 0.0))))


def _at_least(row: dict[str, Any] | None, level: str) -> bool:
    if row is None:
        return False
    return _level_rank(row.get("line_level")) >= _level_rank(level)


def _persisted_at_least(row: dict[str, Any] | None, level: str, hits: int) -> bool:
    if row is None:
        return False
    key = f"recent_{level}_hits"
    try:
        return int(row.get(key, 0) or 0) >= hits
    except (TypeError, ValueError):
        return False


def _level_rank(level: Any) -> int:
    order = {"normal": 0, "warning": 1, "danger": 2, "extreme": 3}
    return order.get(str(level), 0)


def _line_name(row: dict[str, Any]) -> str:
    return f"{row.get('ticker_name_ja', row.get('ticker', '-'))} ({row.get('line_level_label', '-')})"
