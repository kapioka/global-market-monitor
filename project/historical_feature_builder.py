from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

HORIZON_PERIODS = {"1w": 1, "4w": 4, "13w": 13, "26w": 26}


def build_historical_features(prices: pd.DataFrame) -> dict[str, Any]:
    weekly = _weekly_prices(prices)
    features = pd.DataFrame(index=weekly.index)
    for ticker in weekly.columns:
        safe = _safe_name(ticker)
        features[f"price_{safe}"] = weekly[ticker]
        for label, periods in HORIZON_PERIODS.items():
            features[f"{safe}_return_{label}"] = weekly[ticker].pct_change(periods)
        features[f"{safe}_drawdown_13w"] = _rolling_drawdown(weekly[ticker], 13)

    if {"HYG", "LQD"}.issubset(weekly.columns):
        ratio = weekly["HYG"] / weekly["LQD"]
        features["hyg_lqd_ratio"] = ratio
        features["hyg_lqd_ratio_return_4w"] = ratio.pct_change(4)
    if "ACWI" in weekly.columns and "SPY" in weekly.columns:
        features["acwi_spy_relative_13w"] = weekly["ACWI"].pct_change(13) - weekly["SPY"].pct_change(13)
    if "USDJPY=X" in weekly.columns:
        features["usdjpy_change_4w"] = weekly["USDJPY=X"].pct_change(4)
        features["usdjpy_change_13w"] = weekly["USDJPY=X"].pct_change(13)
    if "^VIX" in weekly.columns:
        features["vix_level"] = weekly["^VIX"]
        features["vix_change_4w"] = weekly["^VIX"].pct_change(4)
    if "^TNX" in weekly.columns:
        features["tnx_change_4w"] = weekly["^TNX"].pct_change(4)
    if "CL=F" in weekly.columns and "BZ=F" in weekly.columns:
        features["oil_family_return_4w"] = weekly[["CL=F", "BZ=F"]].pct_change(4).mean(axis=1)
    if "GC=F" in weekly.columns:
        features["gold_return_4w"] = weekly["GC=F"].pct_change(4)

    features = features.sort_index()
    features.index.name = "date"
    missing = {column: round(float(features[column].isna().mean()), 6) for column in features.columns}
    summary = {
        "status": "ok" if not features.empty else "no_data",
        "row_count": len(features),
        "feature_count": len(features.columns),
        "start_date": features.index.min().date().isoformat() if not features.empty else None,
        "end_date": features.index.max().date().isoformat() if not features.empty else None,
        "missing_feature_ratios": missing,
    }
    return {"features": features, "summary": summary}


def write_historical_features(
    payload: dict[str, Any],
    output_path: str | Path,
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    features: pd.DataFrame = payload["features"]
    _write_table(features, output)

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    summary = dict(payload["summary"])
    summary["output_path"] = str(output)
    json_path = reports_path / "historical_feature_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": summary["status"],
        "row_count": summary["row_count"],
        "feature_count": summary["feature_count"],
        "output_path": str(output),
        "json_path": str(json_path),
    }


def run_historical_feature_builder(
    input_path: str | Path,
    output_path: str | Path,
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    prices = _read_table(Path(input_path))
    payload = build_historical_features(prices)
    return write_historical_features(payload, output_path, reports_dir)


def _weekly_prices(prices: pd.DataFrame) -> pd.DataFrame:
    clean = prices.copy()
    clean.index = pd.to_datetime(clean.index).tz_localize(None)
    clean = clean.apply(pd.to_numeric, errors="coerce").sort_index()
    return clean.resample("W-FRI").last().ffill()


def _rolling_drawdown(series: pd.Series, periods: int) -> pd.Series:
    rolling_peak = series.rolling(periods, min_periods=1).max()
    return (series / rolling_peak) - 1.0


def _safe_name(ticker: str) -> str:
    return ticker.lower().replace("=", "").replace("^", "").replace("-", "_").replace(".", "_").replace("/", "_")


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date")
    else:
        frame.index = pd.to_datetime(frame.index)
    return frame


def _write_table(frame: pd.DataFrame, output: Path) -> None:
    if output.suffix.lower() == ".parquet":
        frame.to_parquet(output)
    else:
        frame.to_csv(output, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build weekly historical features from backfilled prices.")
    parser.add_argument("--input", default="project/cache/historical_prices.csv")
    parser.add_argument("--output", default="project/cache/historical_features.csv")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_historical_feature_builder(args.input, args.output, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
