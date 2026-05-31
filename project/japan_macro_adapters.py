from __future__ import annotations

import io
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd

ADAPTER_STATUSES = {"ok", "missing", "partial", "failed", "unavailable"}

JGB_SOURCE = {
    "source_name": "Ministry of Finance Japan JGB yield curve",
    "source_url": "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/",
}
CPI_SOURCE = {
    "source_name": "Statistics Bureau of Japan CPI",
    "source_url": "https://www.stat.go.jp/english/data/cpi/",
}
BOJ_SOURCE = {
    "source_name": "Bank of Japan domestic short-rate statistics",
    "source_url": "https://www.boj.or.jp/en/statistics/",
}


@dataclass(frozen=True)
class JapanMacroSeriesResult:
    source_name: str
    series_name: str
    status: str
    latest_date: str | None
    value: float | str | None
    unit: str
    observations: dict[str, Any]
    metadata: dict[str, Any]
    source_url: str
    error_message: str | None = None

    def as_payload(self, include_error: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if not include_error:
            payload.pop("error_message", None)
        return payload


def parse_jgb_yield_curve_csv(text: str, *, source_url: str = JGB_SOURCE["source_url"]) -> dict[str, Any]:
    try:
        frame = pd.read_csv(io.StringIO(text))
        date_column = _find_column(frame, {"date", "基準日", "年月日"})
        if date_column is None:
            raise ValueError("date column not found")
        latest = _latest_row(frame, date_column)
        observations = {
            "jgb_2y": _column_number(latest, frame, {"2y", "2 year", "2-year", "2年", "2"}),
            "jgb_5y": _column_number(latest, frame, {"5y", "5 year", "5-year", "5年", "5"}),
            "jgb_10y": _column_number(latest, frame, {"10y", "10 year", "10-year", "10年", "10"}),
            "jgb_20y": _column_number(latest, frame, {"20y", "20 year", "20-year", "20年", "20"}),
            "jgb_30y": _column_number(latest, frame, {"30y", "30 year", "30-year", "30年", "30"}),
        }
        observations["jgb_curve_10y_2y"] = _spread(observations.get("jgb_10y"), observations.get("jgb_2y"))
        observations["jgb_curve_30y_10y"] = _spread(observations.get("jgb_30y"), observations.get("jgb_10y"))
        status = "ok" if all(observations.get(key) is not None for key in ("jgb_2y", "jgb_10y", "jgb_30y")) else "partial"
        return JapanMacroSeriesResult(
            source_name=JGB_SOURCE["source_name"],
            series_name="jgb_yield_curve",
            status=status,
            latest_date=_iso_date(latest[date_column]),
            value=observations.get("jgb_10y"),
            unit="percent",
            observations=observations,
            metadata={"required_fields": ["jgb_2y", "jgb_5y", "jgb_10y", "jgb_20y", "jgb_30y"]},
            source_url=source_url,
        ).as_payload()
    except Exception as exc:
        return _failed_result(JGB_SOURCE, "jgb_yield_curve", source_url, exc)


def parse_japan_cpi_csv(text: str, *, source_url: str = CPI_SOURCE["source_url"]) -> dict[str, Any]:
    try:
        frame = pd.read_csv(io.StringIO(text))
        date_column = _find_column(frame, {"date", "month", "年月", "年月日"})
        if date_column is None:
            raise ValueError("date column not found")
        sorted_frame = _sorted_by_date(frame, date_column)
        latest = sorted_frame.iloc[-1]
        previous = sorted_frame.iloc[-2] if len(sorted_frame) > 1 else latest
        cpi_yoy = _column_number(latest, frame, {"cpi yoy", "all items yoy", "jp_cpi_yoy", "総合前年比"})
        core_yoy = _column_number(latest, frame, {"core cpi yoy", "core yoy", "jp_core_cpi_yoy", "生鮮食品を除く総合前年比"})
        prev_core = _column_number(previous, frame, {"core cpi yoy", "core yoy", "jp_core_cpi_yoy", "生鮮食品を除く総合前年比"})
        trend = _cpi_trend(cpi_yoy, core_yoy, prev_core)
        observations = {"jp_cpi_yoy": cpi_yoy, "jp_core_cpi_yoy": core_yoy, "jp_cpi_trend": trend}
        status = "ok" if cpi_yoy is not None or core_yoy is not None else "missing"
        return JapanMacroSeriesResult(
            source_name=CPI_SOURCE["source_name"],
            series_name="japan_cpi",
            status=status,
            latest_date=_iso_date(latest[date_column]),
            value=core_yoy if core_yoy is not None else cpi_yoy,
            unit="percent_yoy",
            observations=observations,
            metadata={"trend_policy": "high>=3, rising when latest core CPI YoY exceeds previous month"},
            source_url=source_url,
        ).as_payload()
    except Exception as exc:
        return _failed_result(CPI_SOURCE, "japan_cpi", source_url, exc)


def parse_boj_domestic_rate_csv(text: str, *, source_url: str = BOJ_SOURCE["source_url"]) -> dict[str, Any]:
    try:
        frame = pd.read_csv(io.StringIO(text))
        date_column = _find_column(frame, {"date", "month", "年月", "年月日"})
        if date_column is None:
            raise ValueError("date column not found")
        sorted_frame = _sorted_by_date(frame, date_column)
        latest = sorted_frame.iloc[-1]
        previous = sorted_frame.iloc[-2] if len(sorted_frame) > 1 else latest
        policy_rate = _column_number(latest, frame, {"policy rate", "boj_policy_rate", "政策金利"})
        call_rate = _column_number(latest, frame, {"call rate", "boj_call_rate", "無担保コール翌日物"})
        prev_call = _column_number(previous, frame, {"call rate", "boj_call_rate", "無担保コール翌日物"})
        context = _domestic_rate_context(policy_rate, call_rate, prev_call)
        observations = {
            "boj_policy_rate": policy_rate,
            "boj_call_rate": call_rate,
            "domestic_rate_context": context,
        }
        status = "ok" if policy_rate is not None or call_rate is not None else "missing"
        return JapanMacroSeriesResult(
            source_name=BOJ_SOURCE["source_name"],
            series_name="boj_domestic_short_rate",
            status=status,
            latest_date=_iso_date(latest[date_column]),
            value=call_rate if call_rate is not None else policy_rate,
            unit="percent",
            observations=observations,
            metadata={"context_policy": "rising when latest call rate exceeds previous; high when short rate >= 0.5"},
            source_url=source_url,
        ).as_payload()
    except Exception as exc:
        return _failed_result(BOJ_SOURCE, "boj_domestic_short_rate", source_url, exc)


def build_japan_macro_context(adapter_results: list[dict[str, Any]]) -> dict[str, Any]:
    context: dict[str, Any] = {"macro_sources": {}}
    for result in adapter_results:
        series_name = str(result.get("series_name") or "")
        observations = result.get("observations") or {}
        context["macro_sources"][series_name] = {key: value for key, value in result.items() if key != "error_message"}
        if result.get("status") not in {"ok", "partial"}:
            continue
        if series_name == "jgb_yield_curve":
            context["jgb_yields"] = dict(observations)
        elif series_name == "japan_cpi":
            context["inflation"] = dict(observations)
        elif series_name == "boj_domestic_short_rate":
            context["domestic_rates"] = dict(observations)
    return context


def unavailable_official_japan_macro_context(reason: str = "official macro live fetch is optional and not configured") -> dict[str, Any]:
    results = [
        _unavailable_result(JGB_SOURCE, "jgb_yield_curve", reason),
        _unavailable_result(CPI_SOURCE, "japan_cpi", reason),
        _unavailable_result(BOJ_SOURCE, "boj_domestic_short_rate", reason),
    ]
    return build_japan_macro_context(results)


def run_official_japan_macro_dry_run(*, live: bool = False, timeout: int = 15) -> dict[str, Any]:
    if not live:
        context = unavailable_official_japan_macro_context("live official macro fetch was not requested")
        return {"status": "unavailable", "mode": "contract_only", "context": context}
    results = [
        _fetch_csv_adapter(JGB_SOURCE, "jgb_yield_curve", parse_jgb_yield_curve_csv, timeout),
        _fetch_csv_adapter(CPI_SOURCE, "japan_cpi", parse_japan_cpi_csv, timeout),
        _fetch_csv_adapter(BOJ_SOURCE, "boj_domestic_short_rate", parse_boj_domestic_rate_csv, timeout),
    ]
    statuses = {str(result.get("status")) for result in results}
    status = "ok" if statuses == {"ok"} else "partial" if statuses & {"ok", "partial"} else "failed"
    return {"status": status, "mode": "live_once", "results": results, "context": build_japan_macro_context(results)}


def _fetch_csv_adapter(source: dict[str, str], series_name: str, parser: Any, timeout: int) -> dict[str, Any]:
    url = source["source_url"]
    try:
        request = Request(url, headers={"User-Agent": "CodexMarketMonitor/1.0", "Accept": "text/csv,text/plain,*/*"})
        with urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
        return parser(text, source_url=url)
    except (OSError, URLError, ValueError) as exc:
        return _failed_result(source, series_name, url, exc)


def _latest_row(frame: pd.DataFrame, date_column: str) -> pd.Series:
    return _sorted_by_date(frame, date_column).iloc[-1]


def _sorted_by_date(frame: pd.DataFrame, date_column: str) -> pd.DataFrame:
    working = frame.copy()
    working[date_column] = pd.to_datetime(working[date_column], errors="coerce")
    working = working.dropna(subset=[date_column]).sort_values(date_column)
    if working.empty:
        raise ValueError("no dated rows found")
    return working


def _find_column(frame: pd.DataFrame, candidates: set[str]) -> str | None:
    normalized = {_normalize_column(column): str(column) for column in frame.columns}
    for candidate in candidates:
        key = _normalize_column(candidate)
        if key in normalized:
            return normalized[key]
    for column in frame.columns:
        normalized_column = _normalize_column(column)
        if any(_normalize_column(candidate) in normalized_column for candidate in candidates):
            return str(column)
    return None


def _column_number(row: pd.Series, frame: pd.DataFrame, candidates: set[str]) -> float | None:
    column = _find_column(frame, candidates)
    if column is None:
        return None
    return _number(row[column])


def _normalize_column(value: Any) -> str:
    return str(value).strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def _number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(str(value).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _spread(long_value: float | None, short_value: float | None) -> float | None:
    if long_value is None or short_value is None:
        return None
    return round(long_value - short_value, 6)


def _cpi_trend(cpi_yoy: float | None, core_yoy: float | None, prev_core_yoy: float | None) -> str:
    level = core_yoy if core_yoy is not None else cpi_yoy
    if level is None:
        return "missing"
    if level >= 3.0:
        return "high"
    if prev_core_yoy is not None and core_yoy is not None and core_yoy > prev_core_yoy:
        return "rising"
    if prev_core_yoy is not None and core_yoy is not None and core_yoy < prev_core_yoy:
        return "falling"
    return "stable"


def _domestic_rate_context(policy_rate: float | None, call_rate: float | None, prev_call_rate: float | None) -> str:
    level = call_rate if call_rate is not None else policy_rate
    if level is None:
        return "missing"
    if level >= 0.5:
        return "high"
    if prev_call_rate is not None and call_rate is not None and call_rate > prev_call_rate:
        return "rising"
    if prev_call_rate is not None and call_rate is not None and call_rate < prev_call_rate:
        return "falling"
    return "stable"


def _iso_date(value: Any) -> str | None:
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        if isinstance(parsed, pd.Timestamp):
            return parsed.date().isoformat()
        if isinstance(parsed, date):
            return parsed.isoformat()
    except (TypeError, ValueError):
        return None
    return None


def _failed_result(source: dict[str, str], series_name: str, source_url: str, exc: Exception) -> dict[str, Any]:
    return JapanMacroSeriesResult(
        source_name=source["source_name"],
        series_name=series_name,
        status="failed",
        latest_date=None,
        value=None,
        unit="",
        observations={},
        metadata={"safe_for_context": False},
        source_url=source_url,
        error_message=str(exc).splitlines()[0][:200],
    ).as_payload(include_error=True)


def _unavailable_result(source: dict[str, str], series_name: str, reason: str) -> dict[str, Any]:
    return JapanMacroSeriesResult(
        source_name=source["source_name"],
        series_name=series_name,
        status="unavailable",
        latest_date=None,
        value=None,
        unit="",
        observations={},
        metadata={"safe_for_context": True, "reason": reason},
        source_url=source["source_url"],
    ).as_payload()
