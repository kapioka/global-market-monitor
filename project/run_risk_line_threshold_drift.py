from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from project.risk_line_threshold_drift_report import write_risk_line_threshold_drift_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build drift diagnostics for active risk-line thresholds.")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config.yaml")
    args = parser.parse_args()

    json_path, md_path = write_risk_line_threshold_drift_report(args.config)
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
