import importlib.util
import json
import sys
import zipfile
from pathlib import Path


def load_verify_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "verify_release_package.py"
    spec = importlib.util.spec_from_file_location("verify_release_package", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_package(path: Path, files: list[str], tag: str = "v0.7.5", commit: str = "abcdef123456") -> None:
    manifest = {
        "commit": commit,
        "short_commit": commit[:7],
        "tags": [tag],
        "file_count": len(files),
        "files": files,
    }
    with zipfile.ZipFile(path, "w") as archive:
        for file_path in files:
            archive.writestr(f"global-market-monitor-{tag}-source/{file_path}", "x")
        archive.writestr(
            f"global-market-monitor-{tag}-source/PACKAGE_MANIFEST.json",
            json.dumps(manifest),
        )


def required_files(module) -> list[str]:
    return list(module.REQUIRED_FILES)


def test_verify_package_passes_for_valid_archive(tmp_path):
    module = load_verify_module()
    package = tmp_path / "release.zip"
    files = required_files(module)
    write_package(package, files)

    result = module.verify_package(package, expected_tag="v0.7.5", expected_commit="abcdef1")

    assert result.manifest["short_commit"] == "abcdef1"
    assert result.forbidden_entries == []
    assert result.missing_required_files == []


def test_verify_package_rejects_forbidden_entry(tmp_path):
    module = load_verify_module()
    package = tmp_path / "release.zip"
    files = required_files(module) + ["project/cache/live.csv"]
    write_package(package, files)

    try:
        module.verify_package(package, expected_tag="v0.7.5")
    except module.VerificationError as exc:
        assert "Forbidden entries" in exc.reason
    else:
        raise AssertionError("expected VerificationError")


def test_verify_package_rejects_wrong_tag(tmp_path):
    module = load_verify_module()
    package = tmp_path / "release.zip"
    write_package(package, required_files(module), tag="v0.7.5")

    try:
        module.verify_package(package, expected_tag="v0.7.6")
    except module.VerificationError as exc:
        assert "expected tag" in exc.reason
    else:
        raise AssertionError("expected VerificationError")


def test_find_latest_package_returns_newest_source_zip(tmp_path):
    module = load_verify_module()
    old_package = tmp_path / "global-market-monitor-v0.7.5-source.zip"
    new_package = tmp_path / "global-market-monitor-v0.7.6-source.zip"
    ignored_package = tmp_path / "other.zip"
    write_package(old_package, required_files(module), tag="v0.7.5")
    write_package(new_package, required_files(module), tag="v0.7.6")
    ignored_package.write_text("not a release package", encoding="utf-8")

    old_time = 1_700_000_000
    new_time = 1_700_000_100
    import os

    os.utime(old_package, (old_time, old_time))
    os.utime(new_package, (new_time, new_time))

    assert module.find_latest_package(tmp_path) == new_package
