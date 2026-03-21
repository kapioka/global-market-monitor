from __future__ import annotations

from typing import Any

import pandas as pd

from project.indicators import max_drawdown, momentum
from project.ticker_labels import ticker_label_ja


def build_recovery_candidates(
    prices: pd.DataFrame,
    asset_map: dict[str, str],
    sector_map: dict[str, str],
    availability_map: dict[str, dict[str, Any]],
    regime: dict[str, Any],
    cycle: dict[str, Any],
    reliability: dict[str, Any],
    alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    if not reliability.get("decision_allowed", False):
        return _none("重要系列の live 取得不足により、先回り候補は保留しています。")
    if str(regime.get("regime_label")) in {"credit_stress", "stagflation_warning", "data_unavailable"}:
        return _none("市場ストレスが強いため、先回り候補は見送ります。")
    if any(alert.get("category") == "market" and alert.get("severity") == "high" for alert in alerts):
        return _none("高重要度の市場警告があるため、先回り候補は見送ります。")

    asset_rows = _candidate_rows(prices, asset_map, availability_map, is_sector=False)
    sector_rows = _candidate_rows(prices, sector_map, availability_map, is_sector=True)
    best_asset = max(asset_rows, key=lambda row: row["recovery_score"], default=None)
    best_sector = max(sector_rows, key=lambda row: row["recovery_score"], default=None)
    best_score = max(best_asset["recovery_score"] if best_asset else -1.0, best_sector["recovery_score"] if best_sector else -1.0)

    cycle_label = str(cycle.get("phase_label", ""))
    regime_label = str(regime.get("regime_label", ""))
    supportive_backdrop = regime_label in {"transition", "early_recovery", "risk_off"} and cycle_label in {"recovery", "downswing", "late_cycle"}

    if best_score >= 2.3 and supportive_backdrop:
        return _payload("build", "仕込み候補", "下落後の反転初期として監視したい候補があります。", best_asset, best_sector)
    if best_score >= 1.9:
        return _payload("watch", "先回り観察", "まだ初期段階ですが、弱い状態から改善し始めた候補があります。", best_asset, best_sector)
    return _none("弱かった銘柄の反転初期として十分な条件はまだ揃っていません。")


def _candidate_rows(
    prices: pd.DataFrame,
    ticker_map: dict[str, str],
    availability_map: dict[str, dict[str, Any]],
    *,
    is_sector: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, ticker in ticker_map.items():
        entry = availability_map.get(ticker)
        if entry is not None and entry.get("status") not in {"ok", "proxy_fallback"}:
            continue
        if ticker not in prices.columns:
            continue
        series = prices[ticker].dropna()
        if len(series) < 20:
            continue
        mom_4w = momentum(series, 4)
        mom_12w = momentum(series, 12)
        drawdown = max_drawdown(series)
        if pd.isna(mom_4w) or pd.isna(mom_12w) or pd.isna(drawdown):
            continue
        if not _passes_shape(mom_4w, mom_12w, drawdown, is_sector=is_sector):
            continue
        score = _recovery_score(mom_4w, mom_12w, drawdown, is_sector=is_sector)
        rows.append(
            {
                "label": label,
                "ticker": ticker,
                "ticker_name_ja": ticker_label_ja(ticker),
                "momentum_4w": round(mom_4w, 4),
                "momentum_12w": round(mom_12w, 4),
                "max_drawdown": round(drawdown, 4),
                "recovery_score": round(score, 2),
                "kind": "sector" if is_sector else "asset",
            }
        )
    return sorted(rows, key=lambda row: row["recovery_score"], reverse=True)


def _passes_shape(mom_4w: float, mom_12w: float, drawdown: float, *, is_sector: bool) -> bool:
    deep_drawdown = -0.12 if is_sector else -0.1
    collapse_floor = -0.42 if is_sector else -0.35
    return mom_4w > 0 and mom_12w <= 0.05 and drawdown <= deep_drawdown and drawdown >= collapse_floor


def _recovery_score(mom_4w: float, mom_12w: float, drawdown: float, *, is_sector: bool) -> float:
    score = 0.0
    if mom_4w >= 0.02:
        score += 1.2
    elif mom_4w > 0:
        score += 0.8
    if mom_12w <= -0.05:
        score += 1.0
    elif mom_12w <= 0.02:
        score += 0.6
    if drawdown <= (-0.16 if is_sector else -0.14):
        score += 1.1
    elif drawdown <= (-0.12 if is_sector else -0.1):
        score += 0.7
    if mom_4w - mom_12w >= 0.06:
        score += 0.9
    return score


def _payload(
    tier: str,
    label: str,
    summary: str,
    best_asset: dict[str, Any] | None,
    best_sector: dict[str, Any] | None,
) -> dict[str, Any]:
    selected = [row for row in (best_asset, best_sector) if row is not None]
    rationale: list[str] = []
    if best_asset:
        rationale.append(
            f"資産候補 {best_asset['ticker']} は 4週 {best_asset['momentum_4w']:+.4f}、12週 {best_asset['momentum_12w']:+.4f}、最大DD {best_asset['max_drawdown']:+.4f} です。"
        )
    if best_sector:
        rationale.append(
            f"セクター候補 {best_sector['ticker']} は 4週 {best_sector['momentum_4w']:+.4f}、12週 {best_sector['momentum_12w']:+.4f}、最大DD {best_sector['max_drawdown']:+.4f} です。"
        )
    return {
        "tier": tier,
        "label": label,
        "summary": summary,
        "preferred_asset_class": best_asset,
        "preferred_sector": best_sector,
        "candidate_tickers": [
            {"ticker": row["ticker"], "label": row["ticker_name_ja"], "kind": row["kind"]}
            for row in selected
        ],
        "rationale": rationale,
    }


def _none(reason: str) -> dict[str, Any]:
    return {
        "tier": "none",
        "label": "候補なし",
        "summary": reason,
        "preferred_asset_class": None,
        "preferred_sector": None,
        "candidate_tickers": [],
        "rationale": [reason],
    }
