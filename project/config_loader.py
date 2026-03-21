from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PATH_KEYS = {"logs_dir", "reports_dir", "sample_output_dir", "cache_dir"}


def load_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    project_root = path.parent.parent
    paths = config.get("paths", {})
    for key in PATH_KEYS:
        value = paths.get(key)
        if not value:
            continue
        resolved = Path(value)
        if not resolved.is_absolute():
            paths[key] = str((project_root / resolved).resolve())
    return config
