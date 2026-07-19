"""Verify a Global Market Monitor source release package."""

from __future__ import annotations

import argparse
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_NAME = "PACKAGE_MANIFEST.json"
REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "docs/github_publish_readiness_checklist.md",
    "docs/sample/sample_report_summary.json",
    "docs/secret_scanner_adoption_v0.7.5.md",
    "scripts/create_release_package.py",
)
FORBIDDEN_PREFIXES = (
    ".git/",
    ".tmp/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".pytest_tmp/",
    ".ruff_cache/",
    "archive/",
    "github_upload/",
    "project/.runtime/",
    "project/cache/",
    "project/logs/",
    "project/reports/",
    "project/sample_output/",
    "release/",
)
FORBIDDEN_SUFFIXES = (
    "-shm",
    "-wal",
    ".backup",
    ".bak",
    ".db",
    ".key",
    ".log",
    ".p12",
    ".pem",
    ".pfx",
    ".secret",
    ".sqlite",
    ".sqlite3",
    ".zip",
)
FORBIDDEN_NAMES = {".env"}
FORBIDDEN_PATHS = {
    "docs/market_data_storage_baseline.json",
    "docs/market_data_storage_migration_result.json",
}


@dataclass(frozen=True)
class VerificationResult:
    package: Path
    manifest_name: str
    manifest: dict[str, Any]
    normalized_files: list[str]
    forbidden_entries: list[str]
    missing_required_files: list[str]


class VerificationError(Exception):
    def __init__(self, reason: str, fix: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.fix = fix


def normalize_path(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix()


def strip_archive_root(path: str) -> str:
    normalized = normalize_path(path)
    parts = PurePosixPath(normalized).parts
    if len(parts) <= 1:
        return normalized
    return PurePosixPath(*parts[1:]).as_posix()


def is_forbidden_entry(path: str) -> bool:
    normalized = normalize_path(path)
    name = PurePosixPath(normalized).name.lower()
    lower_path = normalized.lower()
    return (
        name in FORBIDDEN_NAMES
        or lower_path in FORBIDDEN_PATHS
        or any(lower_path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
        or any(lower_path.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES)
        or ".secret." in lower_path
        or name.startswith("secrets.")
    )


def load_manifest(package: Path) -> tuple[str, dict[str, Any], list[str]]:
    if not package.exists():
        raise VerificationError(
            f"Package does not exist: {package}",
            "Run python scripts/create_release_package.py first, or pass the correct --package path.",
        )
    if not zipfile.is_zipfile(package):
        raise VerificationError(
            f"Package is not a readable zip archive: {package}",
            "Regenerate the source archive with scripts/create_release_package.py.",
        )

    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        manifests = [name for name in names if strip_archive_root(name) == MANIFEST_NAME]
        if len(manifests) != 1:
            raise VerificationError(
                f"Expected exactly one {MANIFEST_NAME}, found {len(manifests)}.",
                "Regenerate the archive and confirm create_release_package.py writes one package manifest.",
            )
        manifest_name = manifests[0]
        try:
            manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VerificationError(
                f"Could not parse {manifest_name}: {exc}",
                "Regenerate the package manifest as UTF-8 JSON.",
            ) from exc
    return manifest_name, manifest, names


def verify_package(package: Path, expected_tag: str | None = None, expected_commit: str | None = None) -> VerificationResult:
    manifest_name, manifest, archive_names = load_manifest(package)
    normalized_files = sorted(strip_archive_root(name) for name in archive_names if not name.endswith("/"))
    manifest_files = sorted(normalize_path(path) for path in manifest.get("files", []))

    if expected_tag and expected_tag not in manifest.get("tags", []):
        raise VerificationError(
            f"Manifest tags do not include expected tag {expected_tag!r}.",
            "Create the release package from the tagged commit, or pass the correct --expected-tag.",
        )

    manifest_commit = str(manifest.get("commit", ""))
    manifest_short_commit = str(manifest.get("short_commit", ""))
    if expected_commit and not (manifest_commit.startswith(expected_commit) or manifest_short_commit.startswith(expected_commit)):
        raise VerificationError(
            f"Manifest commit {manifest_commit!r} does not match expected commit {expected_commit!r}.",
            "Create the package from the expected commit, or pass the correct --expected-commit.",
        )

    archive_source_files = sorted(path for path in normalized_files if path != MANIFEST_NAME)
    if manifest_files and archive_source_files != manifest_files:
        raise VerificationError(
            "Archive source files do not match manifest files.",
            "Regenerate the archive so PACKAGE_MANIFEST.json and zip contents are in sync.",
        )

    forbidden_entries = [path for path in normalized_files if is_forbidden_entry(path)]
    if forbidden_entries:
        raise VerificationError(
            f"Forbidden entries found: {forbidden_entries}",
            "Remove generated/cache/secret-adjacent files and regenerate the release package.",
        )

    missing_required_files = [path for path in REQUIRED_FILES if path not in normalized_files]
    if missing_required_files:
        raise VerificationError(
            f"Required files missing: {missing_required_files}",
            "Regenerate the package from a complete release checkout.",
        )

    manifest_count = manifest.get("file_count")
    if manifest_count != len(manifest_files):
        raise VerificationError(
            f"Manifest file_count {manifest_count!r} does not match manifest files length {len(manifest_files)}.",
            "Regenerate the package manifest.",
        )

    return VerificationResult(
        package=package,
        manifest_name=manifest_name,
        manifest=manifest,
        normalized_files=normalized_files,
        forbidden_entries=forbidden_entries,
        missing_required_files=missing_required_files,
    )


def find_latest_package(directory: Path) -> Path:
    if not directory.exists():
        raise VerificationError(
            f"Latest package directory does not exist: {directory}",
            "Run python scripts/create_release_package.py first, or pass --package explicitly.",
        )
    candidates = sorted(
        directory.glob("global-market-monitor-*-source.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise VerificationError(
            f"No source release packages found in {directory}",
            "Run python scripts/create_release_package.py first, or pass --package explicitly.",
        )
    return candidates[0]


def print_pass(result: VerificationResult) -> None:
    manifest = result.manifest
    print("release_package_verification: pass")
    print(f"package: {result.package}")
    print(f"manifest_path: {result.manifest_name}")
    print(f"manifest_tag: {', '.join(manifest.get('tags', []))}")
    print(f"manifest_commit: {manifest.get('short_commit') or manifest.get('commit')}")
    print(f"tracked_source_files: {manifest.get('file_count')}")
    print(f"forbidden_entries: {len(result.forbidden_entries)}")
    print("required_files: pass")


def print_fail(error: VerificationError) -> None:
    print("release_package_verification: fail")
    print(f"reason: {error.reason}")
    print(f"fix: {error.fix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    package_group = parser.add_mutually_exclusive_group(required=True)
    package_group.add_argument("--package", type=Path, help="Path to the release source zip.")
    package_group.add_argument("--latest-dir", type=Path, help="Find the newest global-market-monitor-*-source.zip in this directory.")
    parser.add_argument("--expected-tag", default="", help="Expected release tag in PACKAGE_MANIFEST.json.")
    parser.add_argument("--expected-commit", default="", help="Expected commit or commit prefix in PACKAGE_MANIFEST.json.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        package = args.package if args.package is not None else find_latest_package(args.latest_dir)
        result = verify_package(
            package,
            expected_tag=args.expected_tag or None,
            expected_commit=args.expected_commit or None,
        )
    except VerificationError as exc:
        print_fail(exc)
        return 1
    print_pass(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
