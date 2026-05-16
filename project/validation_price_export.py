from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from project.config_loader import load_config
from project.data_fetcher import FetchResult, fetch_market_data


FetchMarketData = Callable[[list[str], int, str, logging.Logger, bool, str | Path | None, bool], FetchResult]


def export_validation_prices(
    ticker: str,
    output_path: str | Path,
    period_years: int,
    interval: str,
    cache_dir: str | Path | None = None,
    allow_proxy: bool = False,
    fetcher: FetchMarketData = fetch_market_data,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    active_logger = logger or logging.getLogger(__name__)
    result = fetcher([ticker], period_years, interval, active_logger, False, cache_dir, False)
    entry = result.acquisition_log[0] if result.acquisition_log else {}
    status = entry.get("status", result.source)
    if status == "proxy_fallback" and not allow_proxy:
        raise RuntimeError(f"{ticker} was fetched via proxy fallback. Re-run with --allow-proxy if this is acceptable.")
    if status not in {"ok", "proxy_fallback"}:
        raise RuntimeError(f"{ticker} could not be fetched as live validation data. status={status}")
    if ticker not in result.prices.columns:
        raise RuntimeError(f"{ticker} was not present in fetched prices.")

    points = series_to_price_points(result.prices[ticker])
    if len(points) < 2:
        raise RuntimeError(f"{ticker} did not produce enough validation price points.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ticker": ticker,
        "used_ticker": entry.get("used_ticker", ticker),
        "status": status,
        "period_years": period_years,
        "interval": interval,
        "point_count": len(points),
        "prices": points,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ticker": ticker,
        "used_ticker": payload["used_ticker"],
        "status": status,
        "point_count": len(points),
        "output_path": str(output),
    }


def series_to_price_points(series: pd.Series) -> list[dict[str, Any]]:
    clean = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    points = []
    for stamp, value in clean.items():
        date_value = pd.Timestamp(stamp).date().isoformat()
        points.append({"date": date_value, "price": round(float(value), 6)})
    return points


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export benchmark price points for action validation.")
    parser.add_argument("--ticker", default="ACWI", help="Benchmark ticker to validate against.")
    parser.add_argument("--output", default="project/reports/validation_prices.json", help="Output JSON path.")
    parser.add_argument("--config", default="project/config.yaml", help="Config path used for default period, interval, and cache dir.")
    parser.add_argument("--period-years", type=int, default=None, help="Override config data.period_years.")
    parser.add_argument("--interval", default=None, help="Override config data.interval.")
    parser.add_argument("--allow-proxy", action="store_true", help="Allow yfinance proxy fallback in validation price data.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    logging.basicConfig(level=getattr(logging, str(config.get("app", {}).get("log_level", "INFO")).upper(), logging.INFO))
    result = export_validation_prices(
        ticker=args.ticker,
        output_path=args.output,
        period_years=args.period_years or int(config["data"]["period_years"]),
        interval=args.interval or str(config["data"]["interval"]),
        cache_dir=config.get("paths", {}).get("cache_dir"),
        allow_proxy=bool(args.allow_proxy),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
