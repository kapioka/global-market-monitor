from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "project" / "diagnostics" / "chatgpt_logic_review_v0.8.54.zip"

SEED_FILES = (
    "CHANGELOG.md",
    "README.md",
    "project/main.py",
    "project/data_fetcher.py",
    "project/pipeline.py",
    "project/report_generator.py",
    "project/risk_lines.py",
    "project/risk_line_confidence_audit.py",
    "project/domestic_market_metrics.py",
    "project/domestic_danger_context.py",
    "project/japan_macro_adapters.py",
    "project/japan_resident_asset_context.py",
    "project/japan_resident_integrated_context.py",
    "project/decision_boundary_experiment.py",
    "project/multi_asset_candidates.py",
    "project/buy_readiness_score.py",
    "project/buy_decision_card.py",
    "project/buy_blocker_breakdown.py",
    "project/buy_unlock_conditions.py",
    "project/threshold_decision_policy.py",
    "project/reliability_policy.py",
    "project/japan_risk_monitor.py",
    "project/stress_monitor.py",
    "project/investment_candidates.py",
    "project/spot_signal.py",
    "project/recovery_candidates.py",
    "project/config.yaml",
    "project/ticker_labels.py",
    "project/sample_data.py",
    "project/risk_line_thresholds_active.json",
    "project/risk_line_thresholds_proposed.json",
    "project/threshold_metadata.py",
    "project/threshold_certainty.py",
    "project/scoring.py",
    "project/asset_compare.py",
    "project/credit_monitor.py",
    "project/inflation_monitor.py",
    "project/indicators.py",
)

TEST_FILES = (
    "project/tests/test_domestic_market_metrics.py",
    "project/tests/test_domestic_danger_context.py",
    "project/tests/test_japan_macro_adapters.py",
    "project/tests/test_japan_resident_asset_context.py",
    "project/tests/test_japan_resident_integrated_context.py",
    "project/tests/test_risk_line_confidence_audit.py",
    "project/tests/test_decision_boundary_experiment.py",
    "project/tests/test_report_generator.py",
    "project/tests/test_buy_readiness_score.py",
    "project/tests/test_multi_asset_candidates.py",
    "project/tests/test_main.py",
)

DOC_FILES = (
    "docs/v0.8.47_domestic_danger_logic_rebuild.md",
    "docs/v0.8.48_global_risk_logic_confidence_audit.md",
    "docs/v0.8.49_japan_resident_integrated_risk_context.md",
    "docs/v0.8.50_report_ux_rebuild_for_risk_context.md",
    "docs/v0.8.51_decision_boundary_experiment.md",
    "docs/v0.8.53_rc_logic_polish.md",
    "docs/actual_data_readiness_regression_v0.8.16.md",
    "docs/buy_readiness_score_recalibration_v0.8.15.md",
    "docs/multi_asset_signal_design_inventory_v0.8.22.md",
)

REPORT_FILES = (
    "project/reports/report.md",
    "project/reports/report.html",
    "project/reports/supplement_dashboard.html",
)

EXCLUDED_PREFIXES = (
    ".git/",
    ".tmp/",
    "project/cache/",
    "project/diagnostics/",
    "project/manual_sources/",
    "project/reports/history/",
    "release/",
)

QUESTION_TEXT = """# Logic Review Questions v0.8.54

Please review the included files for these points:

1. Domestic danger context: confirm it is based on measured domestic metrics and not only acquisition logs or data presence.
2. JPY gold and USD gold: confirm 1540.T, GLD, and GC=F are clearly separated.
3. Domestic metric quality: confirm split-like or suspicious discontinuities become data limitations, not risk signals.
4. Drawdown semantics: confirm short lookback drawdown drives supplemental risk while full-period drawdown is reference-only.
5. Missing macro data: confirm CPI, BOJ, and JGB limitations are represented as data limitations and not automatic risk events.
6. Global risk confidence: confirm fallback_review, low_precision, and pass states are distinguishable and not over-trusted.
7. Currency roles: confirm DXY and USDJPY/EURJPY are separated conceptually.
8. Japan resident integrated context: confirm it remains display-only and does not affect final_action or buy_readiness_score.
9. Decision boundary experiment: confirm production default remains unchanged and the experimental payload is disabled/comparison-only.
10. Investment wording: flag wording that could look like investment advice, automatic trading, or guaranteed outcome.
11. Release risk: identify any reason this local RC should not proceed to a broader release validation pass.
"""


@dataclass(frozen=True)
class BundleResult:
    zip_path: Path
    size_bytes: int
    sha256: str
    entry_count: int
    included_files: tuple[str, ...]


def build_chatgpt_diagnostic_bundle(output_path: Path = DEFAULT_OUTPUT, *, version: str = "v0.8.54") -> BundleResult:
    output_path = output_path.resolve()
    bundle_name = output_path.stem
    staging_root = REPO_ROOT / ".tmp" / f"{bundle_name}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    bundle_root = staging_root / bundle_name
    if staging_root.exists():
        shutil.rmtree(staging_root)
    bundle_root.mkdir(parents=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    included = sorted(_collect_files())
    for rel_path in included:
        source = REPO_ROOT / rel_path
        target = bundle_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    (bundle_root / "DIAGNOSTIC_MANIFEST.md").write_text(_manifest(version, included), encoding="utf-8")
    (bundle_root / "logic_review_questions.md").write_text(_sanitize_text(QUESTION_TEXT), encoding="utf-8")

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(bundle_root).as_posix())

    with zipfile.ZipFile(output_path) as archive:
        names = archive.namelist()
        _assert_no_control_chars(archive.read("logic_review_questions.md").decode("utf-8"))
    digest = _sha256(output_path)
    size = output_path.stat().st_size
    shutil.rmtree(staging_root)
    return BundleResult(output_path, size, digest, len(names), tuple(included))


def _collect_files() -> set[str]:
    paths = set(SEED_FILES) | set(TEST_FILES) | set(DOC_FILES) | set(REPORT_FILES)
    paths |= _transitive_project_imports(paths)
    return {path for path in paths if _safe_existing_file(path)}


def _transitive_project_imports(seed_paths: Iterable[str]) -> set[str]:
    found: set[str] = set()
    pending = [path for path in seed_paths if path.endswith(".py")]
    while pending:
        rel_path = pending.pop()
        if rel_path in found:
            continue
        found.add(rel_path)
        source = REPO_ROOT / rel_path
        if not source.exists():
            continue
        for imported in _project_imports(source):
            if imported not in found:
                pending.append(imported)
    return found


def _project_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        module_names: list[str] = []
        if isinstance(node, ast.Import):
            module_names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_names = [node.module]
        for module_name in module_names:
            if not module_name.startswith("project."):
                continue
            candidate = REPO_ROOT / (module_name.replace(".", "/") + ".py")
            if candidate.exists():
                imports.add(candidate.relative_to(REPO_ROOT).as_posix())
    return imports


def _safe_existing_file(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if any(normalized.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    source = REPO_ROOT / normalized
    return source.is_file()


def _manifest(version: str, included: list[str]) -> str:
    status = _run_git(["status", "--short"])
    head = _run_git(["rev-parse", "HEAD"])
    branch = _run_git(["branch", "--show-current"])
    included_lines = "\n".join(f"- {path}" for path in included)
    return _sanitize_text(
        f"""# ChatGPT Logic Review Diagnostic Bundle {version}

Generated: {datetime.now().isoformat(timespec="seconds")}
Branch: {branch.strip()}
HEAD: {head.strip()}
Worktree status before bundle:
{status if status.strip() else "- clean"}

## Purpose

Review the local RC logic and report context after v0.8.53 polish. This bundle is for design and logic review only. It is not a release package.

## Inclusion Policy

- Includes explicit seed files for risk context, report generation, decision-boundary experiment, thresholds, scoring, indicators, monitors, tests, docs, and latest report snapshots.
- Includes transitive `project.*` Python imports reachable from the seed Python files.
- Excludes cache, manual sources, report history, previous diagnostics, release zips, local secrets, and VCS metadata.

## Included Files

{included_lines}
"""
    )


def _sanitize_text(text: str) -> str:
    return "".join(ch for ch in text if ch in {"\n", "\r", "\t"} or ord(ch) >= 32)


def _assert_no_control_chars(text: str) -> None:
    for char in text:
        if char not in {"\n", "\r", "\t"} and ord(char) < 32:
            raise ValueError("logic_review_questions.md contains a control character")


def _run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a ChatGPT logic review diagnostic bundle.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--version", default="v0.8.54")
    args = parser.parse_args(argv)
    result = build_chatgpt_diagnostic_bundle(args.output, version=args.version)
    print(
        json.dumps(
            {
                "zip_path": str(result.zip_path),
                "size_bytes": result.size_bytes,
                "sha256": result.sha256,
                "entry_count": result.entry_count,
                "included_file_count": len(result.included_files),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
