from __future__ import annotations

from typing import Any


def evaluate_spot_signal(
    score: dict[str, float],
    regime: dict[str, Any],
    cycle: dict[str, Any],
    credit_monitor: list[dict[str, Any]],
    inflation_monitor: list[dict[str, Any]],
    thresholds: dict[str, float],
) -> dict[str, object]:
    total = score["total_score"]
    risk_off_relief_applied = _risk_off_relief_applied(regime, total, thresholds)
    regime_penalty = _regime_penalty(regime, total, thresholds)
    adjusted_score = max(total - regime_penalty, 0.0)
    if adjusted_score >= thresholds["spot_score_buy"] and regime["regime_label"] not in {"risk_off", "credit_stress", "stagflation_warning"}:
        action = "buy_window"
    elif adjusted_score >= thresholds["spot_score_watch"]:
        action = "watch"
    else:
        action = "wait"

    second_leg_risk = "high" if regime["max_drawdown"] <= thresholds["drawdown_alert"] and cycle["phase_label"] == "downswing" else "moderate"
    credit_summary = summarize_credit_monitor(credit_monitor)
    inflation_summary = summarize_inflation_monitor(inflation_monitor)
    return {
        "action": action,
        "score": total,
        "adjusted_score": round(adjusted_score, 4),
        "regime_penalty": round(regime_penalty, 4),
        "risk_off_relief_applied": risk_off_relief_applied,
        "credit_stress_score": score.get("credit_stress_component"),
        "credit_summary": credit_summary,
        "second_leg_risk": second_leg_risk,
        "rationale": [
            f"市場レジームは {regime['regime_label']} です。",
            f"サイクル位相は {cycle['phase_label']} です。",
            f"合成スコアは {total:.2f} です。",
            _penalty_summary(regime["regime_label"], regime_penalty, adjusted_score),
            credit_summary,
            inflation_summary,
        ],
    }


def _regime_penalty(regime: dict[str, Any], total_score: float, thresholds: dict[str, float]) -> float:
    regime_label = str(regime.get("regime_label", ""))
    credit_flag = str(regime.get("credit_regime_flag", ""))
    inflation_flag = str(regime.get("inflation_regime_flag", ""))
    if _risk_off_relief_applied(regime, total_score, thresholds):
        return float(thresholds.get("penalty_risk_off_relief", 0.02))
    if credit_flag == "credit_stress_severe":
        return float(thresholds.get("penalty_credit_stress_severe", thresholds.get("penalty_credit_stress", 0.18)))
    if credit_flag == "credit_stress_moderate":
        return float(thresholds.get("penalty_credit_stress_moderate", thresholds.get("penalty_credit_stress", 0.18)))
    if inflation_flag == "inflation_shock_broad":
        return float(thresholds.get("penalty_inflation_shock_broad", thresholds.get("penalty_inflation_shock", 0.12)))
    if inflation_flag == "inflation_shock_oil_only":
        return float(thresholds.get("penalty_inflation_shock_oil_only", thresholds.get("penalty_inflation_shock", 0.12)))
    penalties = {
        "credit_stress": thresholds.get("penalty_credit_stress", 0.18),
        "inflation_shock": thresholds.get("penalty_inflation_shock", 0.12),
        "stagflation_warning": thresholds.get("penalty_stagflation_warning", 0.2),
        "risk_off": thresholds.get("penalty_risk_off", 0.08),
        "early_recovery": 0.0,
        "transition": thresholds.get("penalty_transition", 0.03),
        "risk_on": 0.0,
    }
    return penalties.get(regime_label, 0.0)


def _risk_off_relief_applied(regime: dict[str, Any], total_score: float, thresholds: dict[str, float]) -> bool:
    regime_label = str(regime.get("regime_label", ""))
    return regime_label == "risk_off" and total_score >= thresholds.get("penalty_risk_off_relief_score_min", 0.47)


def _penalty_summary(regime_label: str, regime_penalty: float, adjusted_score: float) -> str:
    if regime_penalty <= 0:
        return f"レジーム減点はなく、判定用スコアは {adjusted_score:.2f} です。"
    return f"{regime_label} を踏まえて {regime_penalty:.2f} 点減点し、判定用スコアは {adjusted_score:.2f} です。"


def summarize_credit_monitor(credit_monitor: list[dict[str, Any]]) -> str:
    if not credit_monitor:
        return "信用面の補助データは不足しています。"

    by_ticker = {row["ticker"]: row for row in credit_monitor}
    ratio = by_ticker.get("HYG/LQD")
    hyg = by_ticker.get("HYG")
    lqd = by_ticker.get("LQD")

    if ratio and ratio.get("signal_label") == "信用収縮警戒" and hyg and hyg.get("signal_label") == "弱含み":
        return "信用面では HYG/LQD 比率悪化とハイイールド債の弱含みが重なっており、信用悪化が広がっている局面です。"
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

    oil_signal = oil.get("signal_label") if oil else None
    gold_signal = gold.get("signal_label") if gold else None
    dollar_signal = dollar.get("signal_label") if dollar else None

    if oil_signal == "インフレ圧力上昇" and dollar_signal == "ドル高進行" and gold_signal == "安全資産選好":
        return "インフレ面では原油高、ドル高、金上昇が重なっており、スタグフレーション警戒を伴う局面です。"
    if oil_signal == "インフレ圧力上昇" and dollar_signal == "ドル高進行":
        return "インフレ面では原油高とドル高が重なっており、割引率とコストの両面で逆風になりやすい局面です。"
    if oil_signal == "インフレ圧力上昇":
        return "インフレ面では原油主導の物価圧力が上がっており、コスト面の警戒が必要です。"
    if oil_signal == "インフレ圧力鈍化":
        return "インフレ面では原油圧力がやや鈍化しており、物価面の逆風は一服気味です。"
    return "インフレ面では大きな加速はまだ見えず、継続監視の段階です。"
