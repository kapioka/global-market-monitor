from __future__ import annotations

from pathlib import Path

from project.config_loader import load_config


def test_load_config_resolves_paths_from_workspace_root():
    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    config = load_config(config_path)

    workspace_root = config_path.parent.parent
    assert config["paths"]["reports_dir"] == str((workspace_root / "project" / "reports").resolve())
    assert config["paths"]["cache_dir"] == str((workspace_root / "project" / "cache").resolve())
    assert config["schema_version"] == 1
    assert config["_config_warnings"] == []
