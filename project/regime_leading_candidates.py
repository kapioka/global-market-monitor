from __future__ import annotations

from typing import Any

import pandas as pd

from project.indicators import momentum
from project.ticker_labels import ticker_label_ja


REGIME_THEMES: dict[str, dict[str, dict[str, float]]] = {
    "risk_off": {
        "sector": {
            "XLU": 1.25,
            "XLP": 1.0,
            "XLV": 0.8,
            "XLRE": 0.35,
        },
        "region": {
            "EWJ": 0.75,
            "VEA": 0.55,
            "SPY": 0.35,
        },
        "asset": {
            "AGG": 1.15,
            "GLD": 0.95,
            "TIP": 0.7,
            "VNQ": 0.2,
        },
    },
    "transition": {
        "sector": {
            "XLU": 1.2,
            "XLB": 1.15,
            "XLI": 0.8,
            "XLP": 0.65,
            "XLV": 0.45,
        },
        "region": {
            "EWJ": 0.9,
            "VEA": 0.8,
            "VWO": 0.55,
            "SPY": 0.45,
        },
        "asset": {
            "GLD": 0.95,
            "TIP": 0.9,
            "VNQ": 0.75,
            "SPY": 0.65,
        },
    },
    "early_recovery": {
        "sector": {
            "XLB": 1.2,
            "XLI": 1.0,
            "XLF": 0.85,
            "XLK": 0.55,
        },
        "region": {
            "VWO": 1.0,
            "VEA": 0.8,
            "EWJ": 0.65,
            "SPY": 0.55,
        },
        "asset": {
            "SPY": 1.0,
            "VNQ": 0.85,
            "TIP": 0.5,
        },
    },
    "inflation_shock": {
        "sector": {
            "XLB": 1.15,
            "XLE": 1.0,
            "XLU": 0.6,
            "XLP": 0.45,
        },
        "region": {
            "VWO": 0.8,
            "EWJ": 0.45,
            "SPY": 0.4,
        },
        "asset": {
            "GLD": 1.15,
            "TIP": 0.95,
            "SPY": 0.25,
        },
    },
}


def build_regime_leading_candidates(
    prices: pd.DataFrame,
    sector_map: dict[str, str],
    region_map: dict[str, str],
    asset_map: dict[str, str],
    sector_rotation: dict[str, Any],
    availability_map: dict[str, dict[str, Any]],
    regime: dict[str, Any],
    reliability: dict[str, Any],
    alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    if not reliability.get("decision_allowed", False):
        return _none("重要系列の live 取得不足により、レジーム先回り候補は保留しています。")

    regime_label = str(regime.get("regime_label", ""))
    if regime_label in {"credit_stress", "stagflation_warning", "data_unavailable"}:
        return _none("市場ストレスが強いため、レジーム先回り候補は見送ります。")

    if any(alert.get("category") == "market" and alert.get("severity") == "high" for alert in alerts):
        return _none("高重要度の市場警告があるため、レジーム先回り候補は見送ります。")

    theme = REGIME_THEMES.get(regime_label, {})
    if not theme:
        return _none("現レジームでは先回りしたいテーマがまだ定まりません。")

    sector_rows = _build_rows(
        prices=prices,
        ticker_map=sector_map,
        availability_map=availability_map,
        theme=theme.get("sector", {}),
        kind="sector",
        sector_rotation=sector_rotation,
    )
    region_rows = _build_rows(
        prices=prices,
        ticker_map=region_map,
        availability_map=availability_map,
        theme=theme.get("region", {}),
        kind="region",
        sector_rotation=None,
    )
    asset_rows = _build_rows(
        prices=prices,
        ticker_map=asset_map,
        availability_map=availability_map,
        theme=theme.get("asset", {}),
        kind="asset",
        sector_rotation=None,
    )

    best_sector = sector_rows[0] if sector_rows else None
    best_region = region_rows[0] if region_rows else None
    best_asset = asset_rows[0] if asset_rows else None
    best_score = max(
        best_sector["regime_score"] if best_sector else -1.0,
        best_region["regime_score"] if best_region else -1.0,
        best_asset["regime_score"] if best_asset else -1.0,
    )

    candidate_rows = [*(sector_rows[:2]), *(region_rows[:2]), *(asset_rows[:2])]
    candidate_rows = sorted(candidate_rows, key=lambda row: row["regime_score"], reverse=True)[:5]
    if not candidate_rows:
        return _none("現レジームで先回り評価できる live データがありません。")

    if best_score >= 2.15:
        return _payload(
            "priority",
            "レジーム先回り候補",
            "次のレジームで効きやすい資産・地域・セクターの候補があります。",
            regime_label,
            best_sector,
            best_region,
            best_asset,
            candidate_rows,
        )
    if best_score >= 1.45:
        return _payload(
            "watch",
            "レジーム観察",
            "まだ先回り段階ですが、次の地合いで効きやすい候補があります。",
            regime_label,
            best_sector,
            best_region,
            best_asset,
            candidate_rows,
        )
    return _none("レジームに対して先回りしたい資産・地域・セクターの条件はまだ十分ではありません。")


def _build_rows(
    *,
    prices: pd.DataFrame,
    ticker_map: dict[str, str],
    availability_map: dict[str, dict[str, Any]],
    theme: dict[str, float],
    kind: str,
    sector_rotation: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not theme:
        return []

    rotation_table = {
        str(row.get("ticker")): row
        for row in (sector_rotation.get("table", []) if isinstance(sector_rotation, dict) else [])
    }

    rows: list[dict[str, Any]] = []
    for label, ticker in ticker_map.items():
        if ticker not in theme:
            continue
        availability = availability_map.get(ticker)
        if availability is not None and availability.get("status") not in {"ok", "proxy_fallback"}:
            continue
        if ticker not in prices.columns:
            continue

        series = prices[ticker].dropna()
        if len(series) < 20:
            continue

        mom_4w = momentum(series, 4)
        mom_12w = momentum(series, 12)
        if pd.isna(mom_4w) or pd.isna(mom_12w):
            continue

        rotation = rotation_table.get(ticker, {})
        phase = str(rotation.get("rotation_phase", ""))
        rank = int(rotation.get("rank", 999) or 999)
        score = _score_row(
            ticker=ticker,
            kind=kind,
            theme_weight=theme[ticker],
            momentum_4w=float(mom_4w),
            momentum_12w=float(mom_12w),
            phase=phase,
            rank=rank,
        )
        if score < 0.95:
            continue
        rows.append(
            {
                "kind": kind,
                "label": label,
                "ticker": ticker,
                "ticker_name_ja": ticker_label_ja(ticker),
                "momentum_4w": round(float(mom_4w), 4),
                "momentum_12w": round(float(mom_12w), 4),
                "rotation_phase": phase or None,
                "rotation_phase_ja": rotation.get("rotation_phase_ja", phase or None),
                "rank": rank if rank != 999 else None,
                "theme_weight": round(float(theme[ticker]), 2),
                "regime_score": round(float(score), 2),
                "short_reason": _short_reason(
                    kind=kind,
                    ticker=ticker,
                    momentum_4w=float(mom_4w),
                    momentum_12w=float(mom_12w),
                    phase=rotation.get("rotation_phase_ja"),
                ),
            }
        )
    return sorted(rows, key=lambda row: row["regime_score"], reverse=True)


def _score_row(
    *,
    ticker: str,
    kind: str,
    theme_weight: float,
    momentum_4w: float,
    momentum_12w: float,
    phase: str,
    rank: int,
) -> float:
    score = theme_weight

    if momentum_4w >= 0.03:
        score += 0.95
    elif momentum_4w > 0:
        score += 0.65
    elif momentum_4w >= -0.01:
        score += 0.25
    else:
        score -= 0.25

    if momentum_12w <= -0.06:
        score += 0.75
    elif momentum_12w <= 0.04:
        score += 0.55
    elif momentum_12w <= 0.12:
        score += 0.2
    else:
        score -= 0.25

    if momentum_4w - momentum_12w >= 0.05:
        score += 0.7
    elif momentum_4w - momentum_12w >= 0.02:
        score += 0.4

    if kind == "sector":
        if phase == "improving":
            score += 0.65
        elif phase == "lagging":
            score += 0.45
        elif phase == "weakening":
            score -= 0.1
        elif phase == "leading":
            score -= 0.2
        if rank <= 2:
            score -= 0.15
        elif 3 <= rank <= 6:
            score += 0.1
        if ticker == "XLU" and phase in {"improving", "lagging"}:
            score += 0.2
        if ticker == "XLB" and phase in {"improving", "lagging"}:
            score += 0.22

    if ticker in {"XLU", "XLB", "EWJ", "GLD", "TIP"} and momentum_4w > 0:
        score += 0.15

    return score


def _short_reason(
    *,
    kind: str,
    ticker: str,
    momentum_4w: float,
    momentum_12w: float,
    phase: str | None,
) -> str:
    if kind == "sector":
        phase_text = f"{phase}で" if phase else ""
        return f"{phase_text}4週改善、12週は過熱前"
    if kind == "region":
        if momentum_4w > 0 and momentum_12w <= 0.04:
            return "地域全体で短期改善、まだ過熱前"
        return "次の地合いに合いやすい地域"
    if momentum_4w > 0 and momentum_12w <= 0.04:
        return "資産クラスで短期改善、まだ過熱前"
    return f"{ticker} はレジーム相性が良い"


def _payload(
    tier: str,
    label: str,
    summary: str,
    regime_label: str,
    best_sector: dict[str, Any] | None,
    best_region: dict[str, Any] | None,
    best_asset: dict[str, Any] | None,
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    rationale: list[str] = []
    if best_sector:
        rationale.append(
            f"セクターでは {best_sector['ticker']} が有力です。4週 {best_sector['momentum_4w']:+.4f}、12週 {best_sector['momentum_12w']:+.4f}、短評: {best_sector['short_reason']}。"
        )
    if best_region:
        rationale.append(
            f"地域では {best_region['ticker']} が有力です。4週 {best_region['momentum_4w']:+.4f}、12週 {best_region['momentum_12w']:+.4f}、短評: {best_region['short_reason']}。"
        )
    if best_asset:
        rationale.append(
            f"資産では {best_asset['ticker']} が有力です。4週 {best_asset['momentum_4w']:+.4f}、12週 {best_asset['momentum_12w']:+.4f}、短評: {best_asset['short_reason']}。"
        )
    rationale.insert(0, f"現レジーム {regime_label} に対して、次に効きやすいテーマを資産・地域・セクターで再整理しています。")
    return {
        "tier": tier,
        "label": label,
        "summary": summary,
        "preferred_sector": best_sector,
        "preferred_region": best_region,
        "preferred_asset_class": best_asset,
        "candidate_tickers": [
            {"ticker": row["ticker"], "label": row["ticker_name_ja"], "kind": row["kind"], "reason": row["short_reason"]}
            for row in candidate_rows
        ],
        "rationale": rationale,
    }


def _none(reason: str) -> dict[str, Any]:
    return {
        "tier": "none",
        "label": "候補なし",
        "summary": reason,
        "preferred_sector": None,
        "preferred_region": None,
        "preferred_asset_class": None,
        "candidate_tickers": [],
        "rationale": [reason],
    }
