from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project.history_dashboard import load_history_entries
from project.report_generator import render_supplement_dashboard_html


def _default_reports_dir() -> Path:
    return Path(__file__).resolve().parent / "reports"


def render_from_summary(
    summary_path: Path,
    output_path: Path,
    history_dir: Path,
) -> Path:
    if not summary_path.exists():
        raise FileNotFoundError(f"report summary not found: {summary_path}")
    report: dict[str, Any] = json.loads(summary_path.read_text(encoding="utf-8"))
    history_entries = load_history_entries(history_dir) if history_dir.exists() else []
    html = render_supplement_dashboard_html(report, history_entries=history_entries)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    reports_dir = _default_reports_dir()
    parser = argparse.ArgumentParser(
        description="Render project/reports/supplement_dashboard.html from report_summary.json."
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=reports_dir / "report_summary.json",
        help="Path to report_summary.json.",
    )
    parser.add_argument(
        "--history-dir",
        type=Path,
        default=reports_dir / "history",
        help="Path to report history directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=reports_dir / "supplement_dashboard.html",
        help="Output HTML path.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_path = render_from_summary(
        summary_path=args.summary.resolve(),
        output_path=args.output.resolve(),
        history_dir=args.history_dir.resolve(),
    )
    print(f"rendered: {output_path}")


if __name__ == "__main__":
    main()
