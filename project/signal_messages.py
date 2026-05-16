from __future__ import annotations

from typing import Any, Mapping


def market_regime_rationale(regime_label: Any) -> str:
    return f"市場レジームは {regime_label} です。"


def cycle_phase_rationale(phase_label: Any) -> str:
    return f"サイクル位相は {phase_label} です。"


def total_score_rationale(total_score: float) -> str:
    return f"合成スコアは {total_score:.2f} です。"


def penalty_summary(regime_label: str, regime_penalty: float, adjusted_score: float) -> str:
    if regime_penalty <= 0:
        return f"レジーム減点はなく、判定用スコアは {adjusted_score:.2f} です。"
    return f"{regime_label} と市場ストレスを踏まえて {regime_penalty:.2f} 点減点し、判定用スコアは {adjusted_score:.2f} です。"


def japan_risk_penalty_summary(penalty: float, japan_risk: Mapping[str, Any] | None) -> str:
    return f"円建て・為替リスクを踏まえて {penalty:.2f} 点減点しています。{str((japan_risk or {}).get('summary', '-'))}"


def risk_lines_summary(risk_lines: Mapping[str, Any]) -> str:
    return f"危険ライン判定は {risk_lines.get('stage_label', '-')} で、{risk_lines.get('summary', '-')}"


def reliability_cap_summary(action: Any) -> str:
    return f"データ品質制限により、最終判断を {action} までに抑制しています。"


def recovery_evidence_summary(grade: str, regime: Mapping[str, Any], cycle: Mapping[str, Any]) -> str:
    if grade == "confirmed":
        return f"レジーム {regime.get('regime_label', '-')} とサイクル {cycle.get('phase_label', '-')} から、上昇再開の証拠は比較的強めです。"
    if grade == "building":
        return f"レジーム {regime.get('regime_label', '-')} とサイクル {cycle.get('phase_label', '-')} から、上昇再開の証拠は改善途中です。"
    return f"レジーム {regime.get('regime_label', '-')} とサイクル {cycle.get('phase_label', '-')} から、上昇再開の証拠はまだ弱めです。"


def sector_adjustment_summary(sector_rotation: Mapping[str, Any] | None, adjustment: float) -> str:
    structure_label = str((sector_rotation or {}).get("internal_structure", {}).get("structure_label", "Noisy / Unclear"))
    direction = "強めています" if adjustment > 0 else "弱めています"
    return f"セクター内部構造 {structure_label} を補助反映し、Spot Investment Window を {abs(adjustment):.2f} 点 {direction}。"


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
