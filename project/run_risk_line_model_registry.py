from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from project.risk_line_model_registry_report import write_risk_line_model_registry_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a risk line model registry from calibrated model selection results.")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent / "config.yaml")
    parser.add_argument("--sample-only", action="store_true")
    args = parser.parse_args()

    json_path, md_path = write_risk_line_model_registry_report(args.config, sample_only=args.sample_only)
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
