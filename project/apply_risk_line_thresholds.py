from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from project.config_loader import load_config
from project.risk_line_threshold_apply import apply_proposed_thresholds


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply approved proposed risk-line thresholds to the active set.")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config.yaml")
    parser.add_argument("--tickers", nargs="*", default=None)
    parser.add_argument("--stages", nargs="*", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    result = apply_proposed_thresholds(config["paths"]["reports_dir"], tickers=args.tickers, stages=args.stages)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
