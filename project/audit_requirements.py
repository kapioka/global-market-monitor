from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


LOCAL_VERSION_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*==\s*([^#;\s]+)\+([^#;\s]+)(.*)$")


@dataclass(frozen=True)
class ExcludedRequirement:
    line_number: int
    requirement: str
    package: str
    version: str
    local_label: str
    reason: str


def split_auditable_requirements(source: Path) -> tuple[list[str], list[ExcludedRequirement]]:
    auditable: list[str] = []
    excluded: list[ExcludedRequirement] = []

    for line_number, raw_line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.rstrip()
        match = LOCAL_VERSION_RE.match(line)
        if match:
            package, version, local_label, _tail = match.groups()
            excluded.append(
                ExcludedRequirement(
                    line_number=line_number,
                    requirement=line,
                    package=package,
                    version=version,
                    local_label=local_label,
                    reason=(
                        "Pinned local-version build cannot be resolved from the default PyPI index by pip-audit; "
                        "audit this package separately against its install source."
                    ),
                )
            )
            continue

        auditable.append(line)

    return auditable, excluded


def write_outputs(source: Path, output_dir: Path) -> dict[str, object]:
    auditable, excluded = split_auditable_requirements(source)
    output_dir.mkdir(parents=True, exist_ok=True)

    requirements_path = output_dir / "requirements-lock.pip-audit.txt"
    exclusions_path = output_dir / "requirements-lock.pip-audit-excluded.json"
    summary_path = output_dir / "requirements-lock.pip-audit-excluded.md"

    requirements_path.write_text("\n".join(auditable) + "\n", encoding="utf-8")
    exclusions_path.write_text(
        json.dumps([asdict(item) for item in excluded], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary_lines = [
        "# pip-audit excluded requirements",
        "",
        f"Source: `{source.as_posix()}`",
        f"Auditable requirements: `{requirements_path.as_posix()}`",
        "",
    ]
    if excluded:
        summary_lines.extend(["| Line | Requirement | Reason |", "| ---: | --- | --- |"])
        for item in excluded:
            summary_lines.append(f"| {item.line_number} | `{item.requirement}` | {item.reason} |")
    else:
        summary_lines.append("No requirements were excluded.")
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    return {
        "source": str(source),
        "auditable_requirements": str(requirements_path),
        "excluded_json": str(exclusions_path),
        "excluded_summary": str(summary_path),
        "auditable_count": sum(1 for line in auditable if line.strip() and not line.lstrip().startswith("#")),
        "excluded_count": len(excluded),
        "excluded": [asdict(item) for item in excluded],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a pip-audit-compatible requirements file from the lockfile.")
    parser.add_argument("--source", type=Path, default=Path(__file__).with_name("requirements-lock.txt"))
    parser.add_argument("--output-dir", type=Path, default=Path(".tmp") / "pip-audit")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    args = parser.parse_args()

    result = write_outputs(args.source, args.output_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote auditable requirements: {result['auditable_requirements']}")
        print(f"Wrote exclusions: {result['excluded_summary']}")
        print(f"Auditable: {result['auditable_count']}; excluded: {result['excluded_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
