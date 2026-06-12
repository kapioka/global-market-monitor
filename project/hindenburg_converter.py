from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

CANONICAL_COLUMNS = [
    "date",
    "new_highs",
    "new_lows",
    "advancers",
    "decliners",
    "total_issues",
    "nyse_index",
    "index_50d_ago",
    "mcclellan_oscillator",
    "source_note",
]

REQUIRED_COLUMNS = {"date", "new_highs", "new_lows", "advancers", "decliners"}
INTEGER_COLUMNS = {"new_highs", "new_lows", "advancers", "decliners", "total_issues"}
NUMERIC_COLUMNS = INTEGER_COLUMNS | {"nyse_index", "index_50d_ago", "mcclellan_oscillator"}
SAMPLE_MARKERS = ("EXAMPLE_DO_NOT_IMPORT", "sample", "example", "サンプル")

ALIASES = {
    "date": {"日付", "date", "market_date"},
    "new_highs": {"新高値", "新52週高値", "new_highs", "highs"},
    "new_lows": {"新安値", "新52週安値", "new_lows", "lows"},
    "advancers": {"値上がり", "値上がり銘柄数", "advancers", "advancing"},
    "decliners": {"値下がり", "値下がり銘柄数", "decliners", "declining"},
    "total_issues": {"対象銘柄数", "total_issues", "issues"},
    "nyse_index": {"NYSE指数", "nyse_index"},
    "index_50d_ago": {"50日前指数", "index_50d_ago"},
    "mcclellan_oscillator": {"McClellan", "mcclellan_oscillator"},
    "source_note": {"メモ", "source_note"},
}

ALIAS_TO_CANONICAL = {
    alias.strip().lower().replace(" ", "_").replace("-", "_"): canonical
    for canonical, aliases in ALIASES.items()
    for alias in aliases
}


@dataclass(frozen=True)
class ConversionSummary:
    status: str
    rows_read: int
    rows_written: int
    rejected_rows: int
    output_path: str
    errors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "rows_read": self.rows_read,
            "rows_written": self.rows_written,
            "rejected_rows": self.rejected_rows,
            "output_path": self.output_path,
            "errors": self.errors,
        }


def write_blank_template(path: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    output_path = Path(path)
    try:
        _ensure_can_write(output_path, overwrite=overwrite)
    except FileExistsError as exc:
        return ConversionSummary("error", 0, 0, 0, str(output_path), [str(exc)]).as_dict()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_rows(output_path, [])
    return ConversionSummary("ok", 0, 0, 0, str(output_path), []).as_dict()


def normalize_hindenburg_csv(input_path: str | Path, output_path: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    source_path = Path(input_path)
    if not source_path.exists():
        return ConversionSummary("error", 0, 0, 0, str(output_path), [f"入力CSVが見つかりません: {source_path}"]).as_dict()

    output = Path(output_path)
    try:
        _ensure_can_write(output, overwrite=overwrite)
    except FileExistsError as exc:
        return ConversionSummary("error", 0, 0, 0, str(output), [str(exc)]).as_dict()

    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        mapping_errors, mapping = _build_column_mapping(fieldnames)
        if mapping_errors:
            return ConversionSummary("error", 0, 0, 0, str(output), mapping_errors).as_dict()

        rows: list[dict[str, str]] = []
        errors: list[str] = []
        rows_read = 0
        rejected_rows = 0
        for row_number, raw_row in enumerate(reader, start=2):
            rows_read += 1
            normalized, row_errors = _normalize_row(raw_row, mapping, row_number=row_number)
            if row_errors:
                rejected_rows += 1
                errors.extend(row_errors)
                continue
            rows.append(normalized)

    output.parent.mkdir(parents=True, exist_ok=True)
    _write_rows(output, rows)
    return ConversionSummary("ok", rows_read, len(rows), rejected_rows, str(output), errors).as_dict()


def _build_column_mapping(fieldnames: list[str]) -> tuple[list[str], dict[str, str]]:
    errors: list[str] = []
    mapping: dict[str, str] = {}
    seen_canonical: dict[str, str] = {}
    for original in fieldnames:
        canonical = ALIAS_TO_CANONICAL.get(_normalize_header(original))
        if canonical is None:
            continue
        if canonical in seen_canonical:
            errors.append(f"同じ列に対応する見出しが複数あります: {seen_canonical[canonical]} / {original} -> {canonical}")
            continue
        seen_canonical[canonical] = original
        mapping[original] = canonical
    missing = sorted(REQUIRED_COLUMNS - set(seen_canonical))
    if missing:
        errors.append("必須列不足: " + ", ".join(missing))
    return errors, mapping


def _normalize_row(raw_row: dict[str, str], mapping: dict[str, str], *, row_number: int) -> tuple[dict[str, str], list[str]]:
    if _is_sample_row(raw_row):
        return {}, [f"{row_number}行目 サンプル行は出力できません。"]
    output = {column: "" for column in CANONICAL_COLUMNS}
    errors: list[str] = []
    for original, canonical in mapping.items():
        output[canonical] = str(raw_row.get(original) or "").strip()

    parsed_date = _parse_date(output["date"])
    if parsed_date is None:
        errors.append(f"{row_number}行目 date が YYYY-MM-DD ではありません。")
    else:
        output["date"] = parsed_date

    for column in NUMERIC_COLUMNS:
        value = output.get(column, "")
        if value == "":
            continue
        normalized, error = _normalize_number(value, integer=column in INTEGER_COLUMNS, allow_negative=column == "mcclellan_oscillator")
        if error:
            errors.append(f"{row_number}行目 {column}: {error}")
        else:
            output[column] = normalized
    return output, errors


def _normalize_number(value: str, *, integer: bool, allow_negative: bool) -> tuple[str, str | None]:
    try:
        number = float(value.replace(",", ""))
    except ValueError:
        return value, "数値ではありません。"
    if number < 0 and not allow_negative:
        return value, "負の値です。"
    if integer:
        if not number.is_integer():
            return value, "整数ではありません。"
        return str(int(number)), None
    return f"{number:g}", None


def _parse_date(value: str) -> str | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _normalize_header(value: str) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _is_sample_row(row: dict[str, str]) -> bool:
    text = " ".join(str(value or "") for value in row.values())
    lower_text = text.lower()
    return any(marker in text or marker in lower_text for marker in SAMPLE_MARKERS)


def _ensure_can_write(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"出力先が既に存在します。上書きする場合は --overwrite を指定してください: {path}")


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
