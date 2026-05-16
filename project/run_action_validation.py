from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project.action_validation import build_action_validation
from project.action_validation_report import write_action_validation_report
from project.history_dashboard import load_history_entries


def run_action_validation(
    history_dir: str | Path,
    price_points_json: str | Path,
    reports_dir: str | Path,
) -> dict[str, Any]:
    price_path = Path(price_points_json)
    if not price_path.exists():
        return {
            "status": "missing_price_points",
            "message": "validation price file is missing. Run project/validation_price_export.py first or pass --price-points-json.",
            "history_count": 0,
            "price_point_count": 0,
            "price_points_json": str(price_path),
        }
    history_entries = load_history_entries(history_dir)
    price_points = _load_price_points(price_path)
    payload = build_action_validation(history_entries, price_points)
    json_path, markdown_path = write_action_validation_report(payload, reports_dir)
    return {
        "status": payload.get("status"),
        "history_count": len(history_entries),
        "price_point_count": len(price_points),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _load_price_points(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("prices"), list):
        return payload["prices"]
    raise ValueError("price points JSON must be a list or an object with a prices list")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build action validation reports from saved history and price points.")
    parser.add_argument("--history-dir", default="project/reports/history", help="Directory containing report_*.json history files.")
    parser.add_argument(
        "--price-points-json",
        default="project/reports/validation_prices.json",
        help="JSON list of {date, price} points for the benchmark being validated.",
    )
    parser.add_argument("--reports-dir", default="project/reports", help="Output directory for action_validation.json/md.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_action_validation(args.history_dir, args.price_points_json, args.reports_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
