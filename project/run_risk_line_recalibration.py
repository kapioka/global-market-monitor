from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from project.risk_line_recalibration_pipeline import write_risk_line_recalibration_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build risk-line recalibration outputs and proposed thresholds.")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config.yaml")
    parser.add_argument("--sample-only", action="store_true")
    args = parser.parse_args()

    outputs = write_risk_line_recalibration_outputs(args.config, sample_only=args.sample_only)
    for path in outputs.values():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
