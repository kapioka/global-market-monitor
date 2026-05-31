from __future__ import annotations

import contextlib
import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd

from project.sample_data import build_sample_prices
from project.ticker_labels import ticker_label_ja

try:
    import yfinance as yf
    from yfinance import cache as yf_cache
except Exception:  # pragma: no cover
    yf = None
    yf_cache = None


FALLBACK_TICKERS: dict[str, list[str]] = {
    "ACWI": ["VT"],
    "VT": ["ACWI"],
    "SPY": ["VOO", "IVV"],
    "VEA": ["IEFA"],
    "VWO": ["IEMG"],
    "XLF": ["VFH"],
    "XLE": ["VDE"],
    "XLV": ["VHT"],
    "XLY": ["VCR"],
    "XLP": ["VDC"],
    "XLI": ["VIS"],
    "XLB": ["VAW"],
    "XLU": ["VPU"],
    "XLRE": ["VNQ"],
    "GLD": ["IAU"],
    "AGG": ["BND"],
    "TIP": ["SCHP"],
    "VNQ": ["REET"],
    "^VIX": ["VIXY"],
    "^MOVE": [],
    "CL=F": ["USO"],
    "BZ=F": ["BNO"],
    "GC=F": ["GLD", "IAU"],
    "DX-Y.NYB": ["UUP"],
    "ZW=F": ["WEAT"],
    "ZC=F": ["CORN"],
    "USDJPY=X": ["JPY=X"],
    "EURJPY=X": [],
    "^TNX": [],
    "1306.T": ["^TOPX"],
    "1321.T": [],
    "2510.T": [],
    "1343.T": [],
    "1540.T": ["GLD", "IAU"],
    "^SOX": ["SOXX"],
    "SOXX": ["^SOX"],
}

FREDDIE_MAC_PMMS_CSV_URL = "https://www.freddiemac.com/pmms/docs/PMMS_history.csv"


@dataclass
class FetchResult:
    prices: pd.DataFrame
    warnings: list[str]
    source: str
    acquisition_log: list[dict[str, Any]]
    diagnostics: dict[str, Any]


def fetch_market_data(
    tickers: list[str],
    period_years: int,
    interval: str,
    logger: logging.Logger,
    use_sample_on_failure: bool = True,
    cache_dir: str | Path | None = None,
    force_sample: bool = False,
) -> FetchResult:
    warnings: list[str] = []
    acquisition_log: list[dict[str, Any]] = []
    period = f"{period_years}y"
    sample = build_sample_prices()
    collected: dict[str, pd.Series] = {}

    if force_sample:
        logger.info("Fetching market data in sample-only mode for %d tickers.", len(tickers))
        for ticker in tickers:
            acquisition_log.append(_sample_log_entry(ticker, sample, reason="sample-only mode"))
            if ticker in sample.columns:
                collected[ticker] = sample[ticker].copy()
        return _build_result(collected, warnings, acquisition_log)

    if yf is None:
        warnings.append("yfinance が利用できないため、yfinance 系列はサンプルデータを使用します。")
        logger.warning(warnings[-1])

    if yf is not None:
        _configure_yfinance_cache(cache_dir, logger, warnings)

    logger.info("Starting market data fetch for %d tickers (interval=%s, period=%s).", len(tickers), interval, period)
    for index, ticker in enumerate(tickers, start=1):
        logger.info("Fetching [%d/%d] %s", index, len(tickers), ticker)
        series, entry = _fetch_single_ticker(
            ticker=ticker,
            period=period,
            interval=interval,
            logger=logger,
            sample=sample,
            use_sample_on_failure=use_sample_on_failure,
        )
        acquisition_log.append(entry)
        if series is not None:
            collected[ticker] = series
        if entry["status"] in {"unavailable", "sample_fallback"}:
            warnings.append(f"{ticker}: {entry['message']}")
            logger.warning("%s: %s", ticker, entry["message"])
        else:
            logger.info("Fetched [%d/%d] %s via %s (%s)", index, len(tickers), ticker, entry["provider"], entry["status"])

    return _build_result(collected, warnings, acquisition_log)


def _fetch_single_ticker(
    ticker: str,
    period: str,
    interval: str,
    logger: logging.Logger,
    sample: pd.DataFrame,
    use_sample_on_failure: bool,
) -> tuple[pd.Series | None, dict[str, Any]]:
    attempts: list[dict[str, str]] = []
    if _is_fred_ticker(ticker):
        series, entry = _fetch_fred_ticker(
            ticker=ticker,
            logger=logger,
            sample=sample,
            use_sample_on_failure=use_sample_on_failure,
        )
        return series, entry
    candidates = [ticker] + [candidate for candidate in FALLBACK_TICKERS.get(ticker, []) if candidate != ticker]

    for candidate in candidates:
        stderr_buffer = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buffer):
                raw = yf.download(
                    tickers=candidate,
                    period=period,
                    interval=interval,
                    auto_adjust=True,
                    progress=False,
                    group_by="column",
                    threads=False,
                )
            if raw.empty:
                raise ValueError("download returned empty dataset")

            prices = _extract_close_frame(raw, [candidate])
            if candidate not in prices.columns:
                raise ValueError("close series missing from dataset")

            series = prices[candidate].dropna()
            if series.empty:
                raise ValueError("close series contained only missing values")

            status = "ok" if candidate == ticker else "proxy_fallback"
            attempts.append({"symbol": candidate, "status": "ok", "detail": "downloaded"})
            return series.rename(ticker), {
                "requested_ticker": ticker,
                "requested_ticker_name_ja": ticker_label_ja(ticker),
                "used_ticker": candidate,
                "used_ticker_name_ja": ticker_label_ja(candidate),
                "status": status,
                "provider": "yfinance",
                "message": "主系列で取得成功" if candidate == ticker else f"主系列が取れず、代替ティッカー {candidate} を使用しました。",
                "alternatives": FALLBACK_TICKERS.get(ticker, []),
                "alternatives_name_ja": [ticker_label_ja(item) for item in FALLBACK_TICKERS.get(ticker, [])],
                "attempts": attempts,
            }
        except Exception as exc:
            detail = _compose_attempt_detail(exc, stderr_buffer.getvalue())
            attempts.append({"symbol": candidate, "status": "failed", "detail": detail})
            logger.debug("Fetch failed for %s via %s: %s", ticker, candidate, detail)

    if use_sample_on_failure and ticker in sample.columns:
        return sample[ticker].copy(), {
            "requested_ticker": ticker,
            "requested_ticker_name_ja": ticker_label_ja(ticker),
            "used_ticker": ticker,
            "used_ticker_name_ja": ticker_label_ja(ticker),
            "status": "sample_fallback",
            "provider": "synthetic_sample",
            "message": "ライブ取得に失敗したため、サンプルデータで代替しました。",
            "alternatives": FALLBACK_TICKERS.get(ticker, []),
            "alternatives_name_ja": [ticker_label_ja(item) for item in FALLBACK_TICKERS.get(ticker, [])],
            "attempts": attempts,
        }

    return None, {
        "requested_ticker": ticker,
        "requested_ticker_name_ja": ticker_label_ja(ticker),
        "used_ticker": None,
        "used_ticker_name_ja": "-",
        "status": "unavailable",
        "provider": "none",
        "message": "ライブ取得に失敗し、利用可能な代替データもありませんでした。",
        "alternatives": FALLBACK_TICKERS.get(ticker, []),
        "alternatives_name_ja": [ticker_label_ja(item) for item in FALLBACK_TICKERS.get(ticker, [])],
        "attempts": attempts,
    }


def _is_fred_ticker(ticker: str) -> bool:
    return ticker.startswith("FRED:")


def _fetch_fred_ticker(
    ticker: str,
    logger: logging.Logger,
    sample: pd.DataFrame,
    use_sample_on_failure: bool,
) -> tuple[pd.Series | None, dict[str, Any]]:
    attempts: list[dict[str, str]] = []
    fred_series = ticker.split(":", 1)[1]
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fred_series}"

    try:
        raw = _read_csv_from_url(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CodexMarketMonitor/1.0",
                "Accept": "text/csv,text/plain,*/*",
            },
        )
        if "DATE" not in raw.columns or fred_series not in raw.columns:
            raise ValueError("fred csv schema mismatch")
        series = pd.Series(raw[fred_series].values, index=pd.to_datetime(raw["DATE"]), name=ticker)
        series = pd.to_numeric(series, errors="coerce").dropna()
        if series.empty:
            raise ValueError("fred series contained only missing values")
        attempts.append({"symbol": fred_series, "status": "ok", "detail": "downloaded from FRED"})
        return series, {
            "requested_ticker": ticker,
            "requested_ticker_name_ja": ticker_label_ja(ticker),
            "used_ticker": ticker,
            "used_ticker_name_ja": ticker_label_ja(ticker),
            "status": "ok",
            "provider": "fred",
            "message": "FRED 系列で取得成功",
            "alternatives": FALLBACK_TICKERS.get(ticker, []),
            "alternatives_name_ja": [ticker_label_ja(item) for item in FALLBACK_TICKERS.get(ticker, [])],
            "attempts": attempts,
        }
    except Exception as exc:
        detail = _short_error(exc)
        if isinstance(exc, URLError):
            detail = f"FRED network error: {detail}"
        attempts.append({"symbol": fred_series, "status": "failed", "detail": detail})
        logger.debug("Fetch failed for %s via FRED: %s", ticker, detail)

    if fred_series == "MORTGAGE30US":
        logger.info("FRED fetch failed for %s; trying Freddie Mac PMMS fallback.", ticker)
        freddie_series, freddie_attempt = _fetch_freddie_mac_pmms_series(ticker)
        attempts.append(freddie_attempt)
        if freddie_series is not None:
            return freddie_series, {
                "requested_ticker": ticker,
                "requested_ticker_name_ja": ticker_label_ja(ticker),
                "used_ticker": ticker,
                "used_ticker_name_ja": ticker_label_ja(ticker),
                "status": "ok",
                "provider": "freddie_mac",
                "message": "FRED 取得に失敗したため、Freddie Mac PMMS の公式 CSV で代替しました。",
                "alternatives": FALLBACK_TICKERS.get(ticker, []),
                "alternatives_name_ja": [ticker_label_ja(item) for item in FALLBACK_TICKERS.get(ticker, [])],
                "attempts": attempts,
            }

    if use_sample_on_failure and ticker in sample.columns:
        fallback_message = "FRED 取得に失敗したため、サンプルデータで代替しました。"
        if fred_series == "MORTGAGE30US":
            fallback_message = "FRED と Freddie Mac 取得に失敗したため、サンプルデータで代替しました。"
        return sample[ticker].copy(), {
            "requested_ticker": ticker,
            "requested_ticker_name_ja": ticker_label_ja(ticker),
            "used_ticker": ticker,
            "used_ticker_name_ja": ticker_label_ja(ticker),
            "status": "sample_fallback",
            "provider": "synthetic_sample",
            "message": fallback_message,
            "alternatives": FALLBACK_TICKERS.get(ticker, []),
            "alternatives_name_ja": [ticker_label_ja(item) for item in FALLBACK_TICKERS.get(ticker, [])],
            "attempts": attempts,
        }

    return None, {
        "requested_ticker": ticker,
        "requested_ticker_name_ja": ticker_label_ja(ticker),
        "used_ticker": None,
        "used_ticker_name_ja": "-",
        "status": "unavailable",
        "provider": "none",
        "message": "FRED 取得に失敗し、利用可能な代替データもありませんでした。",
        "alternatives": FALLBACK_TICKERS.get(ticker, []),
        "alternatives_name_ja": [ticker_label_ja(item) for item in FALLBACK_TICKERS.get(ticker, [])],
        "attempts": attempts,
    }


def _fetch_freddie_mac_pmms_series(ticker: str) -> tuple[pd.Series | None, dict[str, str]]:
    try:
        raw = _read_csv_from_url(
            FREDDIE_MAC_PMMS_CSV_URL,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CodexMarketMonitor/1.0",
                "Accept": "text/csv,text/plain,*/*",
            },
        )
        date_column = _find_date_column(raw.columns)
        value_column = _find_mortgage_30y_column(raw.columns)
        if date_column is None or value_column is None:
            raise ValueError("freddie mac csv schema mismatch")

        series = pd.Series(raw[value_column].values, index=pd.to_datetime(raw[date_column]), name=ticker)
        series = (
            pd.to_numeric(
                series.astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False),
                errors="coerce",
            )
            .dropna()
            .sort_index()
        )
        if series.empty:
            raise ValueError("freddie mac csv contained only missing values")
        return series, {"symbol": "PMMS_history.csv", "status": "ok", "detail": "downloaded from Freddie Mac PMMS"}
    except Exception as exc:
        return None, {"symbol": "PMMS_history.csv", "status": "failed", "detail": _short_error(exc)}


def _read_csv_from_url(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
) -> pd.DataFrame:
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return pd.read_csv(io.StringIO(payload))


def _find_date_column(columns: pd.Index) -> str | None:
    lowered = {str(column).strip().lower(): str(column) for column in columns}
    for candidate in ("date", "week", "weekdate"):
        if candidate in lowered:
            return lowered[candidate]
    for column in columns:
        value = str(column).strip().lower()
        if "date" in value:
            return str(column)
    return None


def _find_mortgage_30y_column(columns: pd.Index) -> str | None:
    normalized = [(str(column), str(column).strip().lower().replace("-", "").replace("_", "").replace(" ", "")) for column in columns]
    for original, value in normalized:
        if "30" in value and ("frm" in value or "rate" in value or "year" in value):
            return original
    for original, value in normalized:
        if "30" in value:
            return original
    return None


def _sample_log_entry(ticker: str, sample: pd.DataFrame, reason: str) -> dict[str, Any]:
    if ticker in sample.columns:
        return {
            "requested_ticker": ticker,
            "requested_ticker_name_ja": ticker_label_ja(ticker),
            "used_ticker": ticker,
            "used_ticker_name_ja": ticker_label_ja(ticker),
            "status": "sample_fallback",
            "provider": "synthetic_sample",
            "message": (
                "サンプル固定モードのため、サンプルデータを使用しました。"
                if reason == "sample-only mode"
                else "ライブ取得が使えないため、サンプルデータで代替しました。"
            ),
            "alternatives": FALLBACK_TICKERS.get(ticker, []),
            "alternatives_name_ja": [ticker_label_ja(item) for item in FALLBACK_TICKERS.get(ticker, [])],
            "attempts": [],
        }
    return {
        "requested_ticker": ticker,
        "requested_ticker_name_ja": ticker_label_ja(ticker),
        "used_ticker": None,
        "used_ticker_name_ja": "-",
        "status": "unavailable",
        "provider": "none",
        "message": (
            "サンプル固定モードですが、この系列のサンプルデータはありません。"
            if reason == "sample-only mode"
            else "ライブ取得もサンプル代替も使えませんでした。"
        ),
        "alternatives": FALLBACK_TICKERS.get(ticker, []),
        "alternatives_name_ja": [ticker_label_ja(item) for item in FALLBACK_TICKERS.get(ticker, [])],
        "attempts": [],
    }


def _build_result(
    collected: dict[str, pd.Series],
    warnings: list[str],
    acquisition_log: list[dict[str, Any]],
) -> FetchResult:
    if collected:
        prices = pd.DataFrame(collected).sort_index()
    else:
        prices = pd.DataFrame()

    providers = {entry["provider"] for entry in acquisition_log if entry["provider"] != "none"}
    if providers == {"yfinance"}:
        source = "yfinance"
    elif providers == {"synthetic_sample"}:
        source = "sample"
    elif providers:
        source = "mixed"
    else:
        source = "unavailable"

    diagnostics = _build_diagnostics(source=source, warnings=warnings, acquisition_log=acquisition_log)
    return FetchResult(
        prices=prices,
        warnings=warnings,
        source=source,
        acquisition_log=acquisition_log,
        diagnostics=diagnostics,
    )


def _configure_yfinance_cache(
    cache_dir: str | Path | None,
    logger: logging.Logger,
    warnings: list[str],
) -> None:
    if cache_dir is None or yf_cache is None:
        return

    cache_path = Path(cache_dir)
    try:
        cache_path.mkdir(parents=True, exist_ok=True)
        yf_cache.set_cache_location(str(cache_path))
    except Exception as exc:
        message = f"yfinance のキャッシュディレクトリを設定できませんでした: {exc}"
        warnings.append(message)
        logger.warning(message)


def _extract_close_frame(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            prices = raw["Close"].copy()
        elif "Adj Close" in raw.columns.get_level_values(0):
            prices = raw["Adj Close"].copy()
        else:
            raise ValueError("Close or Adj Close columns not found in yfinance output.")
    else:
        prices = raw.rename(columns={"Close": tickers[0]}).copy()

    if isinstance(prices, pd.Series):
        prices = prices.to_frame(name=tickers[0])
    prices.index = pd.to_datetime(prices.index)
    return prices.sort_index()


def _short_error(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return exc.__class__.__name__
    return message.splitlines()[0][:160]


def _compose_attempt_detail(exc: Exception, stderr_text: str) -> str:
    base = _short_error(exc)
    stderr_compact = " ".join(line.strip() for line in stderr_text.splitlines() if line.strip())
    if stderr_compact:
        stderr_compact = stderr_compact[:320]
        if base and base.lower() not in stderr_compact.lower():
            return f"{base} | stderr: {stderr_compact}"
        return stderr_compact
    return base


def _build_diagnostics(
    source: str,
    warnings: list[str],
    acquisition_log: list[dict[str, Any]],
) -> dict[str, Any]:
    failure_attempts: list[dict[str, str]] = []
    for entry in acquisition_log:
        for attempt in entry.get("attempts", []):
            if attempt.get("status") == "failed":
                failure_attempts.append(
                    {
                        "requested_ticker": entry.get("requested_ticker", "-"),
                        "symbol": attempt.get("symbol", "-"),
                        "detail": attempt.get("detail", ""),
                    }
                )

    hosts = sorted({host for item in failure_attempts for host in _extract_hosts(item["detail"])})
    failure_samples = [item["detail"] for item in failure_attempts[:5]]
    network_keywords = (
        "failed to connect",
        "could not connect",
        "connectionerror",
        "timed out",
        "name or service not known",
        "temporary failure",
    )
    network_issue_count = sum(1 for item in failure_attempts if any(keyword in item["detail"].lower() for keyword in network_keywords))

    return {
        "summary": {
            "source": source,
            "requested_count": len(acquisition_log),
            "ok_count": sum(1 for item in acquisition_log if item.get("status") == "ok"),
            "proxy_fallback_count": sum(1 for item in acquisition_log if item.get("status") == "proxy_fallback"),
            "sample_fallback_count": sum(1 for item in acquisition_log if item.get("status") == "sample_fallback"),
            "unavailable_count": sum(1 for item in acquisition_log if item.get("status") == "unavailable"),
            "warning_count": len(warnings),
            "failed_attempt_count": len(failure_attempts),
            "suspected_network_issue": network_issue_count > 0,
            "suspected_network_issue_count": network_issue_count,
        },
        "suspected_hosts": hosts,
        "failure_samples": failure_samples,
    }


def _extract_hosts(detail: str) -> list[str]:
    pattern = re.compile(r"([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?::\d+)?")
    return [match.group(1) for match in pattern.finditer(detail)]
