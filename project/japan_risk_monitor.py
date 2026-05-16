from __future__ import annotations

from typing import Any

import pandas as pd

from project.indicators import max_drawdown, rate_of_change, rolling_zscore
from project.ticker_labels import ticker_label_ja


DEFAULT_FOREIGN_ASSET_KEYS = {
    "US_Stocks",
    "Intl_Stocks",
    "Gold",
    "Bonds",
    "Inflation_Bonds",
    "REITs",
}


def build_japan_risk_monitor(
    prices: pd.DataFrame,
    asset_map: dict[str, str],
    japan_map: dict[str, str] | None,
    windows: dict[str, int],
    zscore_window: int,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = settings or {}
    usd_jpy_ticker = str((japan_map or {}).get("usd_jpy", "USDJPY=X"))
    if usd_jpy_ticker not in prices.columns:
        return _unavailable_result(usd_jpy_ticker)

    usd_jpy = prices[usd_jpy_ticker].dropna().astype(float)
    if usd_jpy.empty:
        return _unavailable_result(usd_jpy_ticker)

    fx_row = _fx_row(usd_jpy, usd_jpy_ticker, windows, zscore_window, settings)
    exposure_rows = _exposure_rows(prices, asset_map, usd_jpy, windows, settings)
    summary = _summary(fx_row, exposure_rows)
    level, flags = _risk_level(fx_row, exposure_rows)

    return {
        "available": True,
        "level": level,
        "flags": flags,
        "summary": summary,
        "usd_jpy": fx_row,
        "foreign_assets": exposure_rows,
        "settings": {
            "yen_shock_4w": float(settings.get("yen_shock_4w", 0.05)),
            "yen_reversal_4w": float(settings.get("yen_reversal_4w", -0.05)),
            "fx_dependency_ratio": float(settings.get("fx_dependency_ratio", 0.5)),
        },
    }


def _unavailable_result(usd_jpy_ticker: str) -> dict[str, Any]:
    return {
        "available": False,
        "level": "unknown",
        "flags": ["usd_jpy_unavailable"],
        "summary": f"{usd_jpy_ticker} が不足しているため、円建てリスク判定は保留しています。",
        "usd_jpy": {
            "ticker": usd_jpy_ticker,
            "ticker_name_ja": ticker_label_ja(usd_jpy_ticker),
            "signal_label": "判定保留",
        },
        "foreign_assets": [],
        "settings": {},
    }


def _fx_row(
    usd_jpy: pd.Series,
    ticker: str,
    windows: dict[str, int],
    zscore_window: int,
    settings: dict[str, Any],
) -> dict[str, Any]:
    change_1w = rate_of_change(usd_jpy, int(windows.get("short", 1)))
    change_4w = rate_of_change(usd_jpy, int(windows.get("medium", 4)))
    change_12w = rate_of_change(usd_jpy, int(windows.get("long", 12)))
    zscore = rolling_zscore(usd_jpy, zscore_window)
    yen_shock_4w = float(settings.get("yen_shock_4w", 0.05))
    yen_reversal_4w = float(settings.get("yen_reversal_4w", -0.05))

    if _is_number(change_4w) and change_4w >= yen_shock_4w:
        signal = "円安急進"
    elif _is_number(change_4w) and change_4w <= yen_reversal_4w:
        signal = "円高急進"
    elif _is_number(change_12w) and change_12w >= yen_shock_4w:
        signal = "円安進行"
    elif _is_number(change_12w) and change_12w <= yen_reversal_4w:
        signal = "円高進行"
    else:
        signal = "中立"

    return {
        "ticker": ticker,
        "ticker_name_ja": ticker_label_ja(ticker),
        "current": round(float(usd_jpy.iloc[-1]), 4),
        "change_1w": _rounded(change_1w),
        "change_4w": _rounded(change_4w),
        "change_12w": _rounded(change_12w),
        "zscore": _rounded(zscore),
        "signal_label": signal,
    }


def _exposure_rows(
    prices: pd.DataFrame,
    asset_map: dict[str, str],
    usd_jpy: pd.Series,
    windows: dict[str, int],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    foreign_asset_keys = set(settings.get("foreign_asset_classes", DEFAULT_FOREIGN_ASSET_KEYS))
    for asset_class, ticker in asset_map.items():
        if ticker not in prices.columns or asset_class not in foreign_asset_keys:
            continue
        usd_series = prices[ticker].dropna().astype(float)
        aligned = pd.concat([usd_series, usd_jpy], axis=1, join="inner").dropna()
        if aligned.empty:
            continue
        usd_clean = aligned.iloc[:, 0]
        jpy_series = aligned.iloc[:, 0] * aligned.iloc[:, 1]
        usd_4w = rate_of_change(usd_clean, int(windows.get("medium", 4)))
        jpy_4w = rate_of_change(jpy_series, int(windows.get("medium", 4)))
        fx_contribution_4w = jpy_4w - usd_4w if _is_number(jpy_4w) and _is_number(usd_4w) else float("nan")
        rows.append(
            {
                "asset_class": asset_class,
                "ticker": ticker,
                "ticker_name_ja": ticker_label_ja(ticker),
                "usd_return_4w": _rounded(usd_4w),
                "jpy_return_4w": _rounded(jpy_4w),
                "fx_contribution_4w": _rounded(fx_contribution_4w),
                "jpy_return_12w": _rounded(rate_of_change(jpy_series, int(windows.get("long", 12)))),
                "jpy_max_drawdown": _rounded(max_drawdown(jpy_series)),
                "signal_label": _asset_signal(usd_4w, jpy_4w, fx_contribution_4w, settings),
            }
        )
    return sorted(rows, key=lambda row: abs(float(row.get("fx_contribution_4w", 0.0) or 0.0)), reverse=True)


def _asset_signal(usd_4w: float, jpy_4w: float, fx_contribution_4w: float, settings: dict[str, Any]) -> str:
    dependency = float(settings.get("fx_dependency_ratio", 0.5))
    if not _is_number(fx_contribution_4w) or not _is_number(jpy_4w):
        return "判定保留"
    if jpy_4w > 0 and abs(fx_contribution_4w) >= abs(jpy_4w) * dependency and fx_contribution_4w > 0:
        return "円安寄与が大きい"
    if _is_number(usd_4w) and usd_4w >= 0 and jpy_4w < 0 and fx_contribution_4w < 0:
        return "円高で円建て悪化"
    if jpy_4w < 0:
        return "円建て下落"
    return "中立"


def _risk_level(fx_row: dict[str, Any], exposure_rows: list[dict[str, Any]]) -> tuple[str, list[str]]:
    signal = str(fx_row.get("signal_label", "中立"))
    flags: list[str] = []
    if signal in {"円安急進", "円高急進"}:
        flags.append("fx_shock")
    if signal in {"円安急進", "円安進行"}:
        flags.append("yen_weakness")
    if signal in {"円高急進", "円高進行"}:
        flags.append("yen_strength")
    if any(row.get("signal_label") == "円安寄与が大きい" for row in exposure_rows):
        flags.append("foreign_asset_fx_dependency")
    if any(row.get("signal_label") == "円高で円建て悪化" for row in exposure_rows):
        flags.append("foreign_asset_fx_headwind")

    if "fx_shock" in flags and ("foreign_asset_fx_dependency" in flags or "foreign_asset_fx_headwind" in flags):
        return "high", flags
    if flags:
        return "moderate", flags
    return "low", []


def _summary(fx_row: dict[str, Any], exposure_rows: list[dict[str, Any]]) -> str:
    signal = str(fx_row.get("signal_label", "中立"))
    if not exposure_rows:
        return f"USDJPY は {signal} ですが、円建て換算できる外貨資産データが不足しています。"
    primary = exposure_rows[0]
    return (
        f"USDJPY は {signal} です。外貨資産では {primary.get('ticker', '-')} の4週円建てリターンが "
        f"{primary.get('jpy_return_4w', '-')}、為替寄与が {primary.get('fx_contribution_4w', '-')} です。"
    )


def _rounded(value: float) -> float | None:
    if not _is_number(value):
        return None
    return round(float(value), 4)


def _is_number(value: Any) -> bool:
    return value is not None and pd.notna(value)
