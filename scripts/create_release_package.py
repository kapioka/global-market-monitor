"""Create a source-only release archive for Global Market Monitor."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

EXCLUDED_PREFIXES = (
    ".git/",
    ".github/workflows/.tmp/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".pytest_tmp/",
    ".ruff_cache/",
    ".tmp/",
    "archive/",
    "build/",
    "dist/",
    "docs/visual-evidence/",
    "github_upload/",
    "project/.runtime/",
    "project/cache/",
    "project/logs/",
    "project/reports/",
    "project/sample_output/",
    "release/",
)
EXCLUDED_SUFFIXES = (
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
    ".pyc",
    ".pyo",
    ".secret",
    ".sqlite",
    ".sqlite3",
    ".zip",
)
EXCLUDED_NAMES = {".env"}
EXCLUDED_PATHS = {
    "docs/market_data_storage_baseline.json",
    "docs/market_data_storage_migration_result.json",
}
ALLOWED_EXCLUDED_TRACKED_FILES = {"docs/visual-evidence/.gitkeep"}
MANIFEST_NAME = "PACKAGE_MANIFEST.json"


@dataclass(frozen=True)
class GitMetadata:
    commit: str
    short_commit: str
    tags: list[str]
    status_short: list[str]


def run_git(repo_root: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def normalize(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix()


def is_excluded(path: str) -> bool:
    normalized = normalize(path)
    name = PurePosixPath(normalized).name
    lower_path = normalized.lower()
    lower_name = name.lower()
    return (
        lower_name in EXCLUDED_NAMES
        or lower_path in EXCLUDED_PATHS
        or any(lower_path.startswith(prefix.lower()) for prefix in EXCLUDED_PREFIXES)
        or any(lower_path.endswith(suffix) for suffix in EXCLUDED_SUFFIXES)
        or ".secret." in lower_path
        or lower_name.startswith("secrets.")
    )


def collect_tracked_source_files(repo_root: Path) -> list[str]:
    files = sorted(normalize(path) for path in run_git(repo_root, "ls-files"))
    included = [path for path in files if not is_excluded(path)]
    excluded = [path for path in files if is_excluded(path) and path not in ALLOWED_EXCLUDED_TRACKED_FILES]
    if excluded:
        raise SystemExit(f"Tracked files match release exclusion rules: {excluded}")
    return included


def read_metadata(repo_root: Path) -> GitMetadata:
    commit = run_git(repo_root, "rev-parse", "HEAD")[0]
    tags = run_git(repo_root, "tag", "--points-at", "HEAD")
    status = run_git(repo_root, "status", "--short")
    return GitMetadata(
        commit=commit,
        short_commit=commit[:7],
        tags=tags,
        status_short=status,
    )


def build_manifest(files: list[str], metadata: GitMetadata, archive_name: str) -> dict[str, object]:
    return {
        "name": "global-market-monitor",
        "archive_name": archive_name,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "commit": metadata.commit,
        "short_commit": metadata.short_commit,
        "tags": metadata.tags,
        "working_tree_clean": len(metadata.status_short) == 0,
        "excluded_prefixes": EXCLUDED_PREFIXES,
        "excluded_suffixes": EXCLUDED_SUFFIXES,
        "file_count": len(files),
        "files": files,
    }


def write_archive(repo_root: Path, output_path: Path, files: list[str], manifest: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    package_root = output_path.stem
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(repo_root / file_path, f"{package_root}/{file_path}")
        archive.writestr(
            f"{package_root}/{MANIFEST_NAME}",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print the package manifest without writing the archive.")
    parser.add_argument("--output-dir", default="release", help="Directory where the archive will be created.")
    parser.add_argument("--name", default="", help="Archive base name. Defaults to project name plus tag or commit.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow packaging when the working tree has changes.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    metadata = read_metadata(repo_root)
    if metadata.status_short and not args.allow_dirty and not args.dry_run:
        print("Working tree is not clean. Commit or stash changes, or pass --allow-dirty for a local dry run.", file=sys.stderr)
        for line in metadata.status_short:
            print(f"  {line}", file=sys.stderr)
        return 2

    version = metadata.tags[0] if metadata.tags else metadata.short_commit
    archive_base = args.name or f"global-market-monitor-{version}-source"
    archive_name = f"{archive_base}.zip"
    files = collect_tracked_source_files(repo_root)
    manifest = build_manifest(files, metadata, archive_name)

    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    output_path = repo_root / args.output_dir / archive_name
    write_archive(repo_root, output_path, files, manifest)
    print(f"Created {output_path}")
    print(f"Included {len(files)} tracked source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
