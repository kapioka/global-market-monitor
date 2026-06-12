from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project.hindenburg_converter import normalize_hindenburg_csv, write_blank_template
from project.hindenburg_omen import import_hindenburg_manual_record
from project.hindenburg_store import RESET_CONFIRMATION_PHRASE, reset_hindenburg_local_state

TEMPLATE_PATH = Path("project/manual_sources/hindenburg_breadth_template.csv")
BLANK_TEMPLATE_PATH = Path("project/manual_sources/hindenburg_breadth_blank_template.csv")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local Hindenburg Omen supplemental state.")
    sub = parser.add_subparsers(dest="command", required=True)

    daily = sub.add_parser("daily-input", help="Import one confirmed NYSE market-breadth record.")
    daily.add_argument("--date", required=True, help="US market date, YYYY-MM-DD.")
    daily.add_argument("--new-highs", required=True)
    daily.add_argument("--new-lows", required=True)
    daily.add_argument("--advancers", required=True)
    daily.add_argument("--decliners", required=True)
    daily.add_argument("--total-issues")
    daily.add_argument("--nyse-index")
    daily.add_argument("--index-50d-ago")
    daily.add_argument("--mcclellan-oscillator")
    daily.add_argument("--source-note", default="manual_daily_input")
    daily.add_argument("--db-path")

    reset = sub.add_parser("reset-local-state", help="Reinitialize only local Hindenburg Omen state.")
    reset.add_argument("--confirm", required=True, help=f"Must equal: {RESET_CONFIRMATION_PHRASE}")
    reset.add_argument("--db-path")
    reset.add_argument("--backup-dir")

    sub.add_parser("template-path", help="Print the manual CSV template path.")

    create_template = sub.add_parser("create-template", help="Create a blank canonical Hindenburg Omen CSV template.")
    create_template.add_argument("--output", default=str(BLANK_TEMPLATE_PATH))
    create_template.add_argument("--overwrite", action="store_true")

    normalize = sub.add_parser("normalize-csv", help="Normalize Japanese or English breadth CSV columns into canonical format.")
    normalize.add_argument("--input", required=True)
    normalize.add_argument("--output", required=True)
    normalize.add_argument("--overwrite", action="store_true")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "daily-input":
        return import_hindenburg_manual_record(
            market_date=args.date,
            new_highs=args.new_highs,
            new_lows=args.new_lows,
            advancers=args.advancers,
            decliners=args.decliners,
            total_issues=args.total_issues,
            nyse_index=args.nyse_index,
            index_50d_ago=args.index_50d_ago,
            mcclellan_oscillator=args.mcclellan_oscillator,
            source_note=args.source_note,
            db_path=args.db_path,
            as_of_date=args.date,
        )
    if args.command == "reset-local-state":
        return reset_hindenburg_local_state(
            args.db_path,
            confirmation=args.confirm,
            backup_dir=args.backup_dir,
        )
    if args.command == "template-path":
        return {"status": "ok", "template_path": str(TEMPLATE_PATH)}
    if args.command == "create-template":
        return write_blank_template(args.output, overwrite=args.overwrite)
    if args.command == "normalize-csv":
        return normalize_hindenburg_csv(args.input, args.output, overwrite=args.overwrite)
    raise ValueError(f"unsupported command: {args.command}")


def main() -> None:
    payload = run(build_parser().parse_args())
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
