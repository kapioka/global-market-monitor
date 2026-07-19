from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

try:
    import requests  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - stdlib fallback
    requests = None

DEFAULT_CONNECT_TIMEOUT_SECONDS = 5
DEFAULT_READ_TIMEOUT_SECONDS = 6
DEFAULT_RETRY_COUNT = 1
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_TOTAL_BUDGET_SECONDS = 30
USER_AGENT = "GlobalMarketMonitor-Hindenburg/1.0"
PARSER_VERSION = "builtin_market_breadth_v1"
BARCHART_URL = "https://www.barchart.com/stocks/momentum"
MARKETWATCH_URL = "https://www.marketwatch.com/market-data/us"
WSJ_URL = "https://www.wsj.com/market-data/stocks/marketsdiary"


@dataclass(frozen=True)
class ProviderAttempt:
    provider_id: str
    provider_label: str
    status: str
    failure_code: str | None = None
    source_label: str | None = None
    limitations: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_label": self.provider_label,
            "status": self.status,
            "failure_code": self.failure_code,
            "source_label": self.source_label,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class ProviderResult:
    status: str
    provider_id: str
    provider_label: str
    source_path: str | None = None
    source_label: str | None = None
    failure_code: str | None = None
    attempts: tuple[ProviderAttempt, ...] = ()
    limitations: tuple[str, ...] = ()


BUILTIN_PROVIDER_LABELS = {
    "barchart_market_momentum": "Barchart Market Momentum",
    "marketwatch_us_market_data": "MarketWatch U.S. Market Data",
    "wsj_market_diary": "WSJ Markets Diary",
}
BUILTIN_PROVIDER_URLS = {
    "barchart_market_momentum": BARCHART_URL,
    "marketwatch_us_market_data": MARKETWATCH_URL,
    "wsj_market_diary": WSJ_URL,
}


def resolve_hindenburg_data_dir() -> Path:
    override = os.getenv("HINDENBURG_OMEN_DATA_DIR", "").strip()
    if override:
        return Path(override)
    base = os.getenv("LOCALAPPDATA", "").strip()
    if base:
        return Path(base) / "GlobalMarketMonitor" / "hindenburg_omen"
    return Path.home() / ".global_market_monitor" / "hindenburg_omen"


def resolve_hindenburg_db_path() -> Path:
    override = os.getenv("HINDENBURG_OMEN_DB_PATH", "").strip()
    if override:
        return Path(override)
    return resolve_hindenburg_data_dir() / "hindenburg_omen.sqlite3"


def acquire_configured_static_csv(
    source_url: str | Path | None,
    *,
    cache_dir: str | Path | None = None,
    connect_timeout_seconds: int = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    read_timeout_seconds: int = DEFAULT_READ_TIMEOUT_SECONDS,
    retry_count: int = DEFAULT_RETRY_COUNT,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> ProviderResult:
    if source_url is None or not str(source_url).strip():
        return ProviderResult(
            status="not_configured",
            provider_id="configured_static_csv",
            provider_label="Configured static CSV",
            failure_code="NOT_CONFIGURED",
            limitations=("利用者指定CSV URLは未設定です。",),
        )
    source_text = str(source_url).strip()
    parsed = urlsplit(source_text)
    if parsed.scheme in {"http", "https"}:
        return _download_static_csv(
            source_text,
            cache_dir=Path(cache_dir) if cache_dir else resolve_hindenburg_data_dir() / "cache",
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
            retry_count=retry_count,
            max_response_bytes=max_response_bytes,
        )
    return ProviderResult(
        status="ok",
        provider_id="configured_static_csv",
        provider_label="Configured static CSV",
        source_path=source_text,
        source_label=_redact_source_label(source_text),
        attempts=(
            ProviderAttempt(
                provider_id="configured_static_csv",
                provider_label="Configured static CSV",
                status="ok",
                source_label=_redact_source_label(source_text),
            ),
        ),
    )


def acquire_builtin_provider_chain(
    *,
    provider_priority: list[str] | None = None,
    last_successful_provider: str | None = None,
    cache_dir: str | Path | None = None,
    read_timeout_seconds: int = DEFAULT_READ_TIMEOUT_SECONDS,
    total_budget_seconds: int = DEFAULT_TOTAL_BUDGET_SECONDS,
) -> ProviderResult:
    priority = provider_priority or list(BUILTIN_PROVIDER_LABELS)
    ordered: list[str] = []
    if last_successful_provider in priority:
        ordered.append(str(last_successful_provider))
    ordered.extend(provider for provider in priority if provider not in ordered)
    output_dir = Path(cache_dir) if cache_dir else resolve_hindenburg_data_dir() / "cache"
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    attempts: list[ProviderAttempt] = []
    for provider_id in ordered:
        provider_label = BUILTIN_PROVIDER_LABELS.get(provider_id, provider_id)
        provider_url = BUILTIN_PROVIDER_URLS.get(provider_id)
        if time.monotonic() - started > total_budget_seconds:
            attempts.append(
                ProviderAttempt(
                    provider_id=provider_id,
                    provider_label=provider_label,
                    status="failed",
                    failure_code="TOTAL_BUDGET_EXCEEDED",
                    limitations=("provider chain time budget exceeded",),
                )
            )
            break
        if not provider_url:
            attempts.append(
                ProviderAttempt(
                    provider_id=provider_id,
                    provider_label=provider_label,
                    status="failed",
                    failure_code="UNSUPPORTED_PROVIDER",
                    limitations=("built-in provider URL is not configured",),
                )
            )
            continue
        result = _acquire_builtin_provider(provider_id, provider_label, provider_url, output_dir, read_timeout_seconds=read_timeout_seconds)
        attempts.extend(result.attempts)
        if result.status == "ok":
            return ProviderResult(
                status="ok",
                provider_id=result.provider_id,
                provider_label=result.provider_label,
                source_path=result.source_path,
                source_label=result.source_label,
                attempts=tuple(attempts),
                limitations=result.limitations,
            )
    return ProviderResult(
        status="failed",
        provider_id="builtin_provider_chain",
        provider_label="Built-in provider chain",
        failure_code="ALL_PROVIDERS_UNAVAILABLE",
        attempts=tuple(attempts),
        limitations=("3候補すべて取得不可",),
    )


def parse_barchart_market_momentum_html(
    payload: str,
    *,
    acquired_at: str | None = None,
) -> dict[str, Any]:
    """Parse public Barchart Market Momentum HTML/embedded JSON when full NYSE issue data is present."""

    text = html.unescape(payload)
    market_date = _parse_barchart_market_date(text)
    if market_date is None:
        return {"status": "failed", "failure_code": "INVALID_MARKET_DATE", "limitations": ["market date missing"]}
    candidates = _barchart_json_candidates(text)
    if not candidates:
        if "advancingVolume" in text or "decliningVolume" in text:
            return {
                "status": "failed",
                "failure_code": "ISSUE_COUNTS_NOT_AVAILABLE",
                "limitations": ["volume fields are present but issue counts are not available"],
            }
        return {
            "status": "failed",
            "failure_code": "MANDATORY_FIELD_MISSING",
            "limitations": ["mandatory NYSE issue fields are not present in public HTML or embedded JSON"],
        }
    if len(candidates) > 1:
        return {"status": "failed", "failure_code": "AMBIGUOUS_VALUE", "limitations": ["multiple NYSE candidate rows found"]}
    row = candidates[0]
    values = {
        "new_highs": _nonnegative_int(row.get("high52w")),
        "new_lows": _nonnegative_int(row.get("low52w")),
        "advancers": _nonnegative_int(row.get("advancingIssues")),
        "decliners": _nonnegative_int(row.get("decliningIssues")),
        "unchanged": _nonnegative_int(row.get("unchangedIssues")),
        "total_issues": _nonnegative_int(row.get("totalIssues")),
    }
    if any(values[key] is None for key in ("new_highs", "new_lows", "advancers", "decliners")):
        if row.get("advancingVolume") is not None or row.get("decliningVolume") is not None:
            return {
                "status": "failed",
                "failure_code": "ISSUE_COUNTS_NOT_AVAILABLE",
                "limitations": ["NYSE row does not expose advancing/declining issue counts"],
            }
        return {"status": "failed", "failure_code": "MANDATORY_FIELD_MISSING", "limitations": ["NYSE mandatory fields missing"]}
    advancers = values["advancers"]
    decliners = values["decliners"]
    unchanged = values["unchanged"]
    if values["total_issues"] is None and unchanged is not None and advancers is not None and decliners is not None:
        values["total_issues"] = advancers + decliners + unchanged
    return {
        "status": "ok",
        "provider_id": "barchart_market_momentum",
        "provider_label": BUILTIN_PROVIDER_LABELS["barchart_market_momentum"],
        "universe_id": "nyse_legacy_compat",
        "market": "NYSE",
        "market_date": market_date.isoformat(),
        "parser_version": PARSER_VERSION,
        "source_timestamp": acquired_at,
        "payload_checksum": hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest(),
        **values,
    }


def sanitize_provider_attempts(attempts: list[dict[str, Any]] | tuple[ProviderAttempt, ...]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for attempt in attempts:
        item = attempt.as_dict() if isinstance(attempt, ProviderAttempt) else dict(attempt)
        if item.get("source_label"):
            item["source_label"] = _redact_source_label(str(item["source_label"]))
        sanitized.append({key: value for key, value in item.items() if key not in {"url", "source_url", "response_body"}})
    return sanitized


def _acquire_builtin_provider(
    provider_id: str,
    provider_label: str,
    source_url: str,
    cache_dir: Path,
    *,
    read_timeout_seconds: int = DEFAULT_READ_TIMEOUT_SECONDS,
) -> ProviderResult:
    source_label = _redact_source_label(source_url)
    try:
        body = _download_text(source_url, read_timeout_seconds=read_timeout_seconds)
    except HTTPError as exc:
        failure = "ACCESS_DENIED" if exc.code in {401, 403} else f"HTTP_{exc.code}"
        return _builtin_failure(provider_id, provider_label, failure, source_label)
    except TimeoutError:
        return _builtin_failure(provider_id, provider_label, "TIMEOUT", source_label)
    except URLError as exc:
        failure = "TIMEOUT" if "timed out" in str(exc.reason).lower() else "NETWORK_ERROR"
        return _builtin_failure(provider_id, provider_label, failure, source_label)
    except ValueError as exc:
        return _builtin_failure(provider_id, provider_label, str(exc), source_label)
    except OSError:
        return _builtin_failure(provider_id, provider_label, "NETWORK_ERROR", source_label)

    access_failure = _detect_access_wall(body)
    if access_failure:
        return _builtin_failure(provider_id, provider_label, access_failure, source_label)
    parsed = (
        parse_barchart_market_momentum_html(body, acquired_at=utc_now_iso())
        if provider_id == "barchart_market_momentum"
        else {"status": "failed", "failure_code": "MANDATORY_FIELD_MISSING", "limitations": ["mandatory NYSE fields not found in public HTML"]}
    )
    if parsed.get("status") != "ok":
        return _builtin_failure(
            provider_id,
            provider_label,
            str(parsed.get("failure_code") or "STRUCTURE_CHANGED"),
            source_label,
            limitations=tuple(str(item) for item in parsed.get("limitations", [])),
        )
    csv_path = _write_normalized_provider_csv(parsed, cache_dir)
    attempt = ProviderAttempt(provider_id=provider_id, provider_label=provider_label, status="ok", source_label=source_label)
    return ProviderResult(
        status="ok",
        provider_id=provider_id,
        provider_label=provider_label,
        source_path=str(csv_path),
        source_label=source_label,
        attempts=(attempt,),
        limitations=("当日データ取得済み。履歴不足時は確定計算に使用しません。",),
    )


def _download_text(source_url: str, *, read_timeout_seconds: int = DEFAULT_READ_TIMEOUT_SECONDS) -> str:
    if requests is not None:
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            source_url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            timeout=(DEFAULT_CONNECT_TIMEOUT_SECONDS, read_timeout_seconds),
        )
        if response.status_code >= 400:
            raise HTTPError(source_url, response.status_code, "HTTP error", hdrs=Message(), fp=None)
        payload = response.content
        if len(payload) > DEFAULT_MAX_RESPONSE_BYTES:
            raise ValueError("OVERSIZED_RESPONSE")
        return payload.decode(response.encoding or "utf-8", errors="replace")
    request = Request(source_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(request, timeout=read_timeout_seconds) as response:
        status = getattr(response, "status", 200)
        if int(status) >= 400:
            raise HTTPError(source_url, int(status), "HTTP error", hdrs=Message(), fp=None)
        payload = _read_limited(response, DEFAULT_MAX_RESPONSE_BYTES)
    return payload.decode("utf-8", errors="replace")


def _builtin_failure(
    provider_id: str,
    provider_label: str,
    failure_code: str,
    source_label: str,
    *,
    limitations: tuple[str, ...] = (),
) -> ProviderResult:
    attempt = ProviderAttempt(
        provider_id=provider_id,
        provider_label=provider_label,
        status="failed",
        failure_code=_sanitize_failure_code(failure_code),
        source_label=source_label,
        limitations=limitations,
    )
    return ProviderResult(
        status="failed",
        provider_id=provider_id,
        provider_label=provider_label,
        failure_code=attempt.failure_code,
        attempts=(attempt,),
        limitations=limitations,
    )


def _sanitize_failure_code(value: str) -> str:
    allowed = {
        "TIMEOUT",
        "ACCESS_DENIED",
        "LOGIN_REQUIRED",
        "BROWSER_VERIFICATION",
        "CAPTCHA",
        "MANDATORY_FIELD_MISSING",
        "STRUCTURE_CHANGED",
        "AMBIGUOUS_VALUE",
        "INVALID_MARKET_DATE",
        "ISSUE_COUNTS_NOT_AVAILABLE",
        "NETWORK_ERROR",
        "OVERSIZED_RESPONSE",
        "TOTAL_BUDGET_EXCEEDED",
    }
    return value if value in allowed or value.startswith("HTTP_") else "STRUCTURE_CHANGED"


def _detect_access_wall(payload: str) -> str | None:
    lowered = payload.lower()
    if "captcha challenge" in lowered or "g-recaptcha-response" in lowered:
        return "CAPTCHA"
    if "browser verification" in lowered or "enable javascript and cookies" in lowered or "checking your browser" in lowered:
        return "BROWSER_VERIFICATION"
    if "subscribe now" in lowered and "markets diary" in lowered and "loading..." in lowered:
        return "MANDATORY_FIELD_MISSING"
    return None


def _write_normalized_provider_csv(parsed: dict[str, Any], cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    provider_id = str(parsed["provider_id"])
    market_date = str(parsed["market_date"])
    cache_path = cache_dir / f"{provider_id}_{market_date}.csv"
    columns = [
        "date",
        "new_highs",
        "new_lows",
        "advancers",
        "decliners",
        "unchanged",
        "total_issues",
        "source_note",
    ]
    row = [
        market_date,
        str(parsed["new_highs"]),
        str(parsed["new_lows"]),
        str(parsed["advancers"]),
        str(parsed["decliners"]),
        "" if parsed.get("unchanged") is None else str(parsed["unchanged"]),
        "" if parsed.get("total_issues") is None else str(parsed["total_issues"]),
        f"{provider_id}:{PARSER_VERSION}",
    ]
    fd, temp_name = tempfile.mkstemp(prefix="hindenburg_builtin_", suffix=".csv", dir=str(cache_dir))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(",".join(columns) + "\n")
            handle.write(",".join(row) + "\n")
        os.replace(temp_path, cache_path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
    return cache_path


def _parse_barchart_market_date(payload: str) -> date | None:
    patterns = [
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+([A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4})",
        r'"tradeTime"\s*:\s*"(\d{4}-\d{2}-\d{2})T',
    ]
    for pattern in patterns:
        match = re.search(pattern, payload)
        if not match:
            continue
        value = re.sub(r"(\d)(st|nd|rd|th)", r"\1", match.group(1))
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def _barchart_json_candidates(payload: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for script_body in re.findall(r"<script[^>]*>(.*?)</script>", payload, flags=re.IGNORECASE | re.DOTALL):
        if not all(term in script_body for term in ("high52w", "low52w")):
            continue
        bodies = [script_body.strip()]
        bodies.extend(match.group(1).strip() for match in re.finditer(r"=\s*([\[{].*?);\s*$", script_body, flags=re.DOTALL))
        for body in bodies:
            for obj in _extract_json_objects(body):
                candidates.extend(_find_barchart_nyse_rows(obj))
        if candidates:
            continue
        if all(term in script_body for term in ("exchange", "NYSE", "advancingIssues", "decliningIssues")):
            for row_text in re.findall(r"\{[^{}]*\"exchange\"\s*:\s*\"NYSE\"[^{}]*\}", script_body, flags=re.DOTALL):
                try:
                    obj = json.loads(row_text)
                except json.JSONDecodeError:
                    continue
                candidates.extend(_find_barchart_nyse_rows(obj))
    return candidates


def _extract_json_objects(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    objects: list[Any] = []
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return objects
    try:
        parsed, _end = decoder.raw_decode(stripped)
    except json.JSONDecodeError:
        return objects
    objects.append(parsed)
    return objects


def _find_barchart_nyse_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        exchange = str(value.get("exchange") or value.get("name") or value.get("market") or "").upper()
        has_required_names = {"high52w", "low52w"} <= set(value)
        has_issue_names = {"advancingIssues", "decliningIssues"} <= set(value)
        if exchange == "NYSE" and has_required_names and has_issue_names:
            rows.append(value)
        for child in value.values():
            rows.extend(_find_barchart_nyse_rows(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_find_barchart_nyse_rows(child))
    return rows


def _nonnegative_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.replace(",", "").strip()
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or not number.is_integer():
        return None
    return int(number)


def _download_static_csv(
    source_url: str,
    *,
    cache_dir: Path,
    connect_timeout_seconds: int,
    read_timeout_seconds: int,
    retry_count: int,
    max_response_bytes: int,
) -> ProviderResult:
    del connect_timeout_seconds
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{hashlib.sha256(source_url.encode('utf-8')).hexdigest()[:16]}.csv"
    source_label = _redact_source_label(source_url)
    attempts: list[ProviderAttempt] = []
    last_failure = "UNKNOWN"
    for _attempt_index in range(retry_count + 1):
        try:
            request = Request(source_url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=read_timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if int(status) >= 400:
                    raise HTTPError(source_url, int(status), "HTTP error", hdrs=Message(), fp=None)
                payload = _read_limited(response, max_response_bytes)
            fd, temp_name = tempfile.mkstemp(prefix="hindenburg_", suffix=".csv", dir=str(cache_dir))
            temp_path = Path(temp_name)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                os.replace(temp_path, cache_path)
            finally:
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
            attempts.append(
                ProviderAttempt(
                    provider_id="configured_static_csv",
                    provider_label="Configured static CSV",
                    status="ok",
                    source_label=source_label,
                )
            )
            return ProviderResult(
                status="ok",
                provider_id="configured_static_csv",
                provider_label="Configured static CSV",
                source_path=str(cache_path),
                source_label=source_label,
                attempts=tuple(attempts),
            )
        except HTTPError as exc:
            last_failure = f"HTTP_{exc.code}"
            attempts.append(
                ProviderAttempt(
                    provider_id="configured_static_csv",
                    provider_label="Configured static CSV",
                    status="failed",
                    failure_code=last_failure,
                    source_label=source_label,
                )
            )
            break
        except TimeoutError:
            last_failure = "TIMEOUT"
            attempts.append(_failed_configured_attempt(last_failure, source_label))
        except URLError as exc:
            last_failure = "TIMEOUT" if "timed out" in str(exc.reason).lower() else "NETWORK_ERROR"
            attempts.append(_failed_configured_attempt(last_failure, source_label))
        except ValueError as exc:
            last_failure = str(exc)
            attempts.append(_failed_configured_attempt(last_failure, source_label))
            break
        except OSError:
            last_failure = "IO_ERROR"
            attempts.append(_failed_configured_attempt(last_failure, source_label))
            break
    if cache_path.exists():
        return ProviderResult(
            status="cache_fallback",
            provider_id="configured_static_csv",
            provider_label="Configured static CSV",
            source_path=str(cache_path),
            source_label=source_label,
            failure_code=last_failure,
            attempts=tuple(attempts),
            limitations=("自動取得に失敗したため、前回の有効キャッシュを使用します。",),
        )
    return ProviderResult(
        status="failed",
        provider_id="configured_static_csv",
        provider_label="Configured static CSV",
        failure_code=last_failure,
        source_label=source_label,
        attempts=tuple(attempts),
        limitations=("利用者指定CSVの取得に失敗しました。",),
    )


def _failed_configured_attempt(failure_code: str, source_label: str) -> ProviderAttempt:
    return ProviderAttempt(
        provider_id="configured_static_csv",
        provider_label="Configured static CSV",
        status="failed",
        failure_code=failure_code,
        source_label=source_label,
    )


def _read_limited(response: Any, max_response_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, max_response_bytes + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > max_response_bytes:
            raise ValueError("OVERSIZED_RESPONSE")
        chunks.append(chunk)
    return b"".join(chunks)


def _redact_source_label(source: str) -> str:
    parsed = urlsplit(source)
    if parsed.scheme in {"http", "https"}:
        safe_netloc = parsed.hostname or parsed.netloc
        if parsed.port:
            safe_netloc = f"{safe_netloc}:{parsed.port}"
        return urlunsplit((parsed.scheme, safe_netloc, parsed.path, "", ""))
    return source


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
