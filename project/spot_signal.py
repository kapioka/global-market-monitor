from __future__ import annotations

from typing import Any


def evaluate_spot_signal(
    score: dict[str, float],
    regime: dict[str, Any],
    cycle: dict[str, Any],
    credit_monitor: list[dict[str, Any]],
    inflation_monitor: list[dict[str, Any]],
    thresholds: dict[str, float],
    risk_lines: dict[str, Any] | None = None,
) -> dict[str, object]:
    total = score["total_score"]
    risk_off_relief_applied = _risk_off_relief_applied(regime, total, thresholds)
    regime_penalty = _regime_penalty(regime, total, thresholds, risk_lines)
    adjusted_score = max(total - regime_penalty, 0.0)
    action = _action_for_state(adjusted_score, regime, thresholds, risk_lines)
    second_leg_risk = _second_leg_risk(regime, cycle, risk_lines)
    credit_summary = summarize_credit_monitor(credit_monitor)
    inflation_summary = summarize_inflation_monitor(inflation_monitor)
    rationale = [
        f"市場レジームは {regime['regime_label']} です。",
        f"サイクル位相は {cycle['phase_label']} です。",
        f"合成スコアは {total:.2f} です。",
        _penalty_summary(regime["regime_label"], regime_penalty, adjusted_score),
        credit_summary,
        inflation_summary,
    ]
    if risk_lines:
        rationale.append(f"危険ライン判定は {risk_lines.get('stage_label', '-')} で、{risk_lines.get('summary', '-')}")
        rationale.extend(str(reason) for reason in risk_lines.get("reasons", [])[:3])
    return {
        "action": action,
        "score": total,
        "adjusted_score": round(adjusted_score, 4),
        "regime_penalty": round(regime_penalty, 4),
        "risk_off_relief_applied": risk_off_relief_applied,
        "credit_stress_score": score.get("credit_stress_component"),
        "credit_summary": credit_summary,
        "second_leg_risk": second_leg_risk,
        "rationale": rationale,
    }


def _action_for_state(adjusted_score: float, regime: dict[str, Any], thresholds: dict[str, float], risk_lines: dict[str, Any] | None) -> str:
    stage_key = str((risk_lines or {}).get("stage_key", "normal"))
    blocked_regimes = {"risk_off", "credit_stress", "stagflation_warning"}
    if stage_key == "extreme_danger_line_reached":
        return "wait"
    if adjusted_score >= thresholds["spot_score_buy"] and regime["regime_label"] not in blocked_regimes and stage_key not in {"credit_spillover_initial", "danger_line_reached"}:
        return "buy_window"
    if adjusted_score >= thresholds["spot_score_watch"]:
        return "watch"
    return "wait"


def _second_leg_risk(regime: dict[str, Any], cycle: dict[str, Any], risk_lines: dict[str, Any] | None) -> str:
    stage_key = str((risk_lines or {}).get("stage_key", "normal"))
    credit_flag = str(regime.get("credit_regime_flag", ""))
    if stage_key == "extreme_danger_line_reached":
        return "extreme"
    if stage_key == "danger_line_reached":
        return "high"
    if credit_flag == "credit_stress_severe":
        return "high"
    if regime["max_drawdown"] <= -0.12 and cycle["phase_label"] == "downswing":
        return "high"
    if stage_key in {"credit_spillover_initial", "caution"} or credit_flag == "credit_stress_moderate":
        return "moderate"
    return "low"


def _regime_penalty(regime: dict[str, Any], total_score: float, thresholds: dict[str, float], risk_lines: dict[str, Any] | None) -> float:
    regime_label = str(regime.get("regime_label", ""))
    credit_flag = str(regime.get("credit_regime_flag", ""))
    inflation_flag = str(regime.get("inflation_regime_flag", ""))
    if _risk_off_relief_applied(regime, total_score, thresholds):
        base = float(thresholds.get("penalty_risk_off_relief", 0.02))
    elif credit_flag == "credit_stress_severe":
        base = float(thresholds.get("penalty_credit_stress_severe", thresholds.get("penalty_credit_stress", 0.18)))
    elif credit_flag == "credit_stress_moderate":
        base = float(thresholds.get("penalty_credit_stress_moderate", thresholds.get("penalty_credit_stress", 0.18)))
    elif inflation_flag == "inflation_shock_broad":
        base = float(thresholds.get("penalty_inflation_shock_broad", thresholds.get("penalty_inflation_shock", 0.12)))
    elif inflation_flag == "inflation_shock_oil_only":
        base = float(thresholds.get("penalty_inflation_shock_oil_only", thresholds.get("penalty_inflation_shock", 0.12)))
    else:
        penalties = {
            "credit_stress": thresholds.get("penalty_credit_stress", 0.18),
            "inflation_shock": thresholds.get("penalty_inflation_shock", 0.12),
            "stagflation_warning": thresholds.get("penalty_stagflation_warning", 0.2),
            "risk_off": thresholds.get("penalty_risk_off", 0.08),
            "early_recovery": 0.0,
            "transition": thresholds.get("penalty_transition", 0.03),
            "risk_on": 0.0,
        }
        base = float(penalties.get(regime_label, 0.0))
    stress_penalty = float((risk_lines or {}).get("penalty_hint", 0.0) or 0.0)
    return min(base + stress_penalty, 0.35)


def _risk_off_relief_applied(regime: dict[str, Any], total_score: float, thresholds: dict[str, float]) -> bool:
    regime_label = str(regime.get("regime_label", ""))
    return regime_label == "risk_off" and total_score >= thresholds.get("penalty_risk_off_relief_score_min", 0.47)


def _penalty_summary(regime_label: str, regime_penalty: float, adjusted_score: float) -> str:
    if regime_penalty <= 0:
        return f"レジーム減点はなく、判定用スコアは {adjusted_score:.2f} です。"
    return f"{regime_label} と市場ストレスを踏まえて {regime_penalty:.2f} 点減点し、判定用スコアは {adjusted_score:.2f} です。"


def summarize_credit_monitor(credit_monitor: list[dict[str, Any]]) -> str:
    if not credit_monitor:
        return "信用面の補助データは不足しています。"
    by_ticker = {row["ticker"]: row for row in credit_monitor}
    ratio = by_ticker.get("HYG/LQD")
    hyg = by_ticker.get("HYG")
    lqd = by_ticker.get("LQD")
    if ratio and ratio.get("signal_label") == "信用収縮警戒" and hyg and hyg.get("signal_label") == "弱含み":
        return "信用面では HYG/LQD 比率悪化とハイイールド債の弱含みが重なっており、信用悪化が広がっている局面です。"
    if ratio and ratio.get("signal_label") == "信用収縮警戒" and lqd and float(lqd.get("change_4w", 0.0) or 0.0) <= -0.02:
        return "信用面では HYG/LQD 比率が悪化しつつ LQD も重く、信用危機というより金利上昇が社債全体を圧迫している局面です。"
    if ratio and ratio.get("signal_label") == "信用収縮警戒":
        return "信用面では HYG/LQD 比率が悪化しており、信用収縮を警戒する局面です。"
    if ratio and ratio.get("signal_label") == "信用改善":
        return "信用面では HYG/LQD 比率が改善しており、信用環境は持ち直し寄りです。"
    if hyg and hyg.get("signal_label") == "弱含み":
        return "信用面ではハイイールド債が弱含みで、株式の見た目より地合いが重い可能性があります。"
    if lqd and lqd.get("signal_label") == "改善":
        return "信用面では投資適格社債が安定しており、全面的な信用不安にはまだ傾いていません。"
    return "信用面では大きな崩れはまだ見えず、継続監視の段階です。"


def summarize_inflation_monitor(inflation_monitor: list[dict[str, Any]]) -> str:
    if not inflation_monitor:
        return "インフレ面の補助データは不足しています。"
    by_ticker = {row["ticker"]: row for row in inflation_monitor}
    oil = by_ticker.get("CL=F")
    gold = by_ticker.get("GC=F")
    dollar = by_ticker.get("DX-Y.NYB")
    tnx = by_ticker.get("^TNX")
    oil_signal = oil.get("signal_label") if oil else None
    gold_signal = gold.get("signal_label") if gold else None
    dollar_signal = dollar.get("signal_label") if dollar else None
    tnx_signal = tnx.get("signal_label") if tnx else None
    if oil_signal == "インフレ圧力上昇" and dollar_signal == "ドル高進行" and gold_signal == "安全資産選好":
        return "インフレ面では原油高、ドル高、金上昇が重なっており、スタグフレーション警戒を伴う局面です。"
    if oil_signal == "インフレ圧力上昇" and dollar_signal == "ドル高進行" and tnx_signal == "住宅ローン負担上昇":
        return "インフレ面では原油高、ドル高、長期金利上昇が重なり、割引率とコストの両面で逆風が強まっています。"
    if oil_signal == "インフレ圧力上昇" and dollar_signal == "ドル高進行":
        return "インフレ面では原油高とドル高が重なっており、割引率とコストの両面で逆風になりやすい局面です。"
    if oil_signal == "インフレ圧力上昇":
        return "インフレ面では原油主導の物価圧力が上がっており、コスト面の警戒が必要です。"
    if oil_signal == "インフレ圧力鈍化":
        return "インフレ面では原油圧力がやや鈍化しており、物価面の逆風は一服気味です。"
    return "インフレ面では大きな加速はまだ見えず、継続監視の段階です。"
