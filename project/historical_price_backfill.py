from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


DEFAULT_TICKERS = ["ACWI", "SPY", "HYG", "LQD", "USDJPY=X", "DX-Y.NYB", "^VIX", "^TNX", "CL=F", "BZ=F", "GC=F"]

Downloader = Callable[[str, str, str], pd.DataFrame]


def build_historical_price_backfill(
    start: str,
    end: str,
    tickers: list[str] | None = None,
    downloader: Downloader | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    active_tickers = tickers or DEFAULT_TICKERS
    download = downloader or _download_with_yfinance
    collected: dict[str, pd.Series] = {}
    ticker_summaries: list[dict[str, Any]] = []

    for ticker in active_tickers:
        try:
            raw = download(ticker, start, end)
            series = _extract_close_series(raw, ticker)
            if series.empty:
                raise ValueError("close series is empty")
            collected[ticker] = series
            ticker_summaries.append(
                {
                    "ticker": ticker,
                    "status": "ok",
                    "point_count": int(series.count()),
                    "first_date": series.index.min().date().isoformat(),
                    "last_date": series.index.max().date().isoformat(),
                    "missing_ratio": None,
                    "message": "downloaded",
                }
            )
        except Exception as exc:
            ticker_summaries.append(
                {
                    "ticker": ticker,
                    "status": "failed",
                    "point_count": 0,
                    "first_date": None,
                    "last_date": None,
                    "missing_ratio": None,
                    "message": str(exc).splitlines()[0][:160] or exc.__class__.__name__,
                }
            )

    prices = pd.DataFrame(collected).sort_index()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices.index.name = "date"
    _fill_missing_ratios(ticker_summaries, prices)
    usable_start, usable_end = _usable_date_range(prices)
    summary = {
        "status": "ok" if not prices.empty else "no_data",
        "source": "yfinance",
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "start": start,
        "end": end,
        "usable_start": usable_start,
        "usable_end": usable_end,
        "usable_row_count": int(prices.dropna(how="all").shape[0]),
        "requested_tickers": active_tickers,
        "ok_count": sum(1 for item in ticker_summaries if item["status"] == "ok"),
        "failed_count": sum(1 for item in ticker_summaries if item["status"] == "failed"),
        "ticker_summary": ticker_summaries,
    }
    return {"prices": prices, "summary": summary}


def write_historical_price_backfill(
    payload: dict[str, Any],
    output_path: str | Path,
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    prices: pd.DataFrame = payload["prices"]
    _write_table(prices, output)

    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    summary = dict(payload["summary"])
    summary["output_path"] = str(output)
    json_path = reports_path / "historical_price_backfill_summary.json"
    markdown_path = reports_path / "historical_price_backfill_summary.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_historical_price_backfill_markdown(summary), encoding="utf-8")
    return {
        "status": summary["status"],
        "ok_count": summary["ok_count"],
        "failed_count": summary["failed_count"],
        "output_path": str(output),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def render_historical_price_backfill_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# historical price backfill",
        "",
        f"- status: {summary.get('status')}",
        f"- source: {summary.get('source')}",
        f"- period: {summary.get('start')} to {summary.get('end')}",
        f"- usable range: {summary.get('usable_start') or '-'} to {summary.get('usable_end') or '-'}",
        f"- ok / failed: {summary.get('ok_count', 0)} / {summary.get('failed_count', 0)}",
        f"- output: {summary.get('output_path', '-')}",
        "",
        "## tickers",
    ]
    for item in summary.get("ticker_summary", []):
        lines.append(
            "- {ticker}: {status} / points={points} / missing={missing} / {message}".format(
                ticker=item.get("ticker", "-"),
                status=item.get("status", "-"),
                points=item.get("point_count", 0),
                missing=_fmt_ratio(item.get("missing_ratio")),
                message=item.get("message", "-"),
            )
        )
    return "\n".join(lines) + "\n"


def run_historical_price_backfill(
    start: str,
    end: str,
    output: str | Path,
    tickers: list[str] | None = None,
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    payload = build_historical_price_backfill(start, end, tickers)
    return write_historical_price_backfill(payload, output, reports_dir)


def _download_with_yfinance(ticker: str, start: str, end: str) -> pd.DataFrame:
    if yf is None:
        raise RuntimeError("yfinance is not available")
    return yf.download(
        tickers=ticker,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=False,
    )


def _extract_close_series(raw: pd.DataFrame, ticker: str) -> pd.Series:
    if raw.empty:
        raise ValueError("download returned empty dataset")
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            raise ValueError("Close column missing")
        close = raw["Close"]
        if isinstance(close, pd.DataFrame):
            series = close.iloc[:, 0]
        else:
            series = close
    elif "Close" in raw.columns:
        series = raw["Close"]
    elif ticker in raw.columns:
        series = raw[ticker]
    else:
        raise ValueError("Close column missing")
    series = pd.to_numeric(series, errors="coerce").dropna()
    series.index = pd.to_datetime(series.index).tz_localize(None)
    return series.sort_index().rename(ticker)


def _fill_missing_ratios(ticker_summaries: list[dict[str, Any]], prices: pd.DataFrame) -> None:
    denominator = max(len(prices.index), 1)
    for item in ticker_summaries:
        ticker = item["ticker"]
        if item["status"] == "ok" and ticker in prices.columns:
            item["missing_ratio"] = round(float(prices[ticker].isna().sum() / denominator), 6)
            valid = prices[ticker].dropna()
            item["usable_start"] = valid.index.min().date().isoformat() if not valid.empty else None
            item["usable_end"] = valid.index.max().date().isoformat() if not valid.empty else None


def _usable_date_range(prices: pd.DataFrame) -> tuple[str | None, str | None]:
    if prices.empty:
        return None, None
    usable = prices.dropna(how="all")
    if usable.empty:
        return None, None
    return usable.index.min().date().isoformat(), usable.index.max().date().isoformat()


def _write_table(frame: pd.DataFrame, output: Path) -> None:
    if output.suffix.lower() == ".parquet":
        frame.to_parquet(output)
    else:
        frame.to_csv(output, encoding="utf-8")


def _fmt_ratio(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch historical daily prices for replay diagnostics.")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=datetime.now().date().isoformat())
    parser.add_argument("--output", default="project/cache/historical_prices.csv")
    parser.add_argument("--tickers", default=",".join(DEFAULT_TICKERS), help="Comma separated ticker list.")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    tickers = [item.strip() for item in str(args.tickers).split(",") if item.strip()]
    print(
        json.dumps(
            run_historical_price_backfill(args.start, args.end, args.output, tickers, args.reports_dir),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
