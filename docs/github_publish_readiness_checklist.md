# GitHub Publish Readiness Checklist

This checklist is for the final pre-publish review before a GitHub release. It is meant to prevent publishing accidents, secret leakage, generated-file inclusion, and unintended decision-logic changes.

This is not investment advice, does not improve investment decision logic, and does not change `final_action`, thresholds, `reliability_policy`, `buy_window`, or `buy_candidate` behavior.

## Scope

Use this checklist for v0.11.0 and later releases based on the existing release-operation hardening.

For the overall responsibility map across CI, local security audit, release package generation, manifest verification, optional scanner review, and scanner finding policy, see `docs/pre_publish_integration_review_v0.7.11.md`.

For the final local dry run before publishing, see `docs/github_publish_final_dry_run_v0.7.12.md`.

For the first post-publish operating baseline, see `docs/post_publish_operation_baseline_v0.8.0.md`.

Expected supporting tools:

- GitHub Actions CI
- `scripts/security_audit.ps1`
- `scripts/create_release_package.py`
- `detect-secrets`
- `pip-audit`
- release package `PACKAGE_MANIFEST.json`

## Pre-Publish Commands

Run from the repository root in PowerShell:

```powershell
git status --short
git diff --check
python -m pytest
python -m ruff check .
python -m black --check .
python -m mypy .
powershell -ExecutionPolicy Bypass -File scripts\security_audit.ps1 -Python "python" -ExpectedTag "" -Strict
python scripts\create_release_package.py --dry-run
```

Before permission, validate the complete proposed source in an isolated rehearsal repository. Do not create the real tag or push.

After explicit publication permission, commit the reviewed scope, create the release tag, and run the tag-specific checks:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\security_audit.ps1 -Python "python" -ExpectedTag "<release-tag>" -Strict
python scripts\create_release_package.py
python scripts\verify_release_package.py --package release\global-market-monitor-<release-tag>-source.zip --expected-tag <release-tag>
```

For v0.11.0, use `-ExpectedTag "v0.11.0"` only after that tag exists on the reviewed commit.

CI also creates a source package and verifies the newest package in `release/` with commit matching enabled. Normal push and pull request CI may run without a release tag, so tag verification remains a release-publish check:

```powershell
python scripts\verify_release_package.py --latest-dir release --expected-commit <commit>
```

## Optional Actual-Data Smoke

Run this optional local check before a public release or before larger
decision-score, blocker, or report-card changes:

```powershell
python project\main.py --actual-smoke
```

This is intentionally separate from `python project\main.py --sample-only`.

- `--sample-only` uses synthetic fallback data, needs no external data, and is
  suitable for stable startup and generated-report smoke checks.
- `--actual-smoke` reuses the newest acquired cached market snapshot when one
  is available. If no saved snapshot can be used, it attempts the normal fetch
  path.
- `--actual-smoke` is useful for checking the actual-data readiness score,
  blocker breakdown, reliability, recovery, risk stage, and decision-card path.
- `--actual-smoke` is not a required CI gate because it can depend on network
  access, cache availability, external provider behavior, market calendar
  timing, and changing market data.

Record the result in release review notes with this template:

```text
Actual smoke result:
- command:
- timestamp:
- source/data_source:
- sample_fallback_count:
- reliability:
- actions:
- readiness_score:
- risk_stage:
- final_action:
- generated_outputs_committed: no
- notes:
```

Confirm after the run:

- the command exits successfully, or any fetch/cache failure is understood as
  an optional local validation issue rather than a CI failure;
- `source` or `data_source` is recorded;
- `sample_fallback_count` is recorded;
- reliability, actions, readiness score, risk stage, and final action are
  recorded;
- generated outputs remain ignored and unstaged.

Do not commit outputs from:

- `project/reports/`
- `project/reports/history/`
- `project/cache/`
- `.tmp/`
- `release/`

## Tag Check

```powershell
git tag --list "v0.11.*"
git rev-parse HEAD
git rev-parse <release-tag>
```

Confirm:

- The release tag points at `HEAD`.
- `security_audit.ps1` receives the same release tag through `-ExpectedTag`.
- The release package manifest tag matches the release tag.
- The release package manifest commit matches `HEAD`.

## Release Package Manifest Check

Open `PACKAGE_MANIFEST.json` inside the generated source archive and confirm:

- Package name is the expected source archive.
- Manifest path is present inside the archive.
- Manifest commit matches `HEAD`.
- Manifest tag contains the release tag.
- Included file count is reasonable for tracked source files.
- Forbidden entries check returns `0`.
- `docs/sample/sample_report_summary.json` is the only committed sample fixture needed for README references.
- Generated/cache paths are excluded.
- `.git` is excluded.
- `.env` and secret-adjacent file types are excluded.
- Real reports, live cache, private local config, and personal data are excluded.

For v0.7.6 and later, use the verification script to automate this check:

```powershell
python scripts\verify_release_package.py --package release\global-market-monitor-<release-tag>-source.zip --expected-tag <release-tag> --expected-commit <commit>
```

If `--expected-commit` is omitted, the script still displays the manifest commit and validates required files and forbidden entries.
If the exact package name is inconvenient in CI, use `--latest-dir release` to verify the newest `global-market-monitor-*-source.zip`.

Forbidden entry examples:

- `.git/`
- `.env`
- `project/reports/`
- `project/cache/`
- `.tmp/`
- nested `release/` output
- `github_upload/`
- `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.secret`, `secrets.*`
- private local config
- real report output

## Decision-Logic Non-Change Check

Run these checks before publishing:

```powershell
git diff -- project\reliability_policy.py
git diff -- project\threshold_decision_policy.py
git diff -- project\buy_window_diagnostics.py
git diff -- project\buy_candidate_near_miss.py
git diff -- project\risk_line_thresholds_active.json
git diff -- project\risk_line_thresholds_proposed.json
```

Confirm:

- No `reliability_policy` diff.
- No active/proposed threshold JSON diff.
- No `final_action` decision path diff.
- No `buy_window` or `buy_candidate` threshold diff.
- No TimesFM normal-functionality reintroduction.
- No `fx_soft_cap` or regime-aware adoption change.
- No automated trading feature.

## Security Scanner Status

From v0.11.0, GitHub Actions runs Gitleaks as a required job with read-only repository permissions. The action and all other third-party Actions are pinned to reviewed full commit SHAs. A Gitleaks failure blocks publication until the result is explained and resolved.

`trufflehog` remains an optional local supplemental scanner. The local `security_audit.ps1` records the availability of optional scanners and still requires `detect-secrets`, fallback scans, dependency audit, and protected-surface checks in strict mode.

Historical adoption and evaluation records remain available in:

- `docs/secret_scanner_adoption_v0.7.5.md`
- `docs/gitleaks_optional_ci_evaluation_v0.7.9.md`
- `docs/scanner_findings_integration_decision_v0.7.10.md`

Required security signals:

- `security_audit.ps1` reports `publish_readiness: pass`.
- `detect-secrets` reports `finding_count: 0`.
- fallback scans have no strong secret hits.
- `pip-audit` exits with code `0` for requirements and lock inputs.

`pip check` may report an existing local environment warning where `argostranslate` expects `sentencepiece==0.2.0` while the local environment has `sentencepiece 0.2.1`. Treat this as a local environment note unless the project starts depending on that optional translation stack.

## Mypy Scope

v0.7.3 made `python -m mypy .` a repeatable operational check by documenting and configuring the current practical type-checking surface.

For v0.7.4, do not expand full-repository typing. Type cleanup for excluded older modules should be handled as separate staged work. If future releases add more mypy exclusions, record the reason in docs or CHANGELOG.

## Publish Decision

Passing the preparation checks means the source is ready to request publication permission. It does not authorize a commit, tag, push, or GitHub Release.

Publish is allowed only when all are true:

- the user has explicitly authorized publication;
- `pytest` passes.
- `ruff` passes.
- `black --check` passes.
- `mypy` passes.
- security audit reports `publish_readiness: pass`.
- `detect-secrets finding_count` is `0`.
- `pip-audit` exits with code `0`.
- release package generation succeeds.
- forbidden entries check returns `0`.
- manifest tag and commit match the release target.
- decision-logic checks show no diff.
- threshold JSON checks show no diff.

Stop publishing when any are true:

- Possible secret or credential material is found.
- Forbidden entries are included.
- generated reports/cache are included.
- threshold JSON has a diff.
- `reliability_policy` has a diff.
- `final_action` decision path has a diff.
- release tag and manifest do not match.
- security audit fails.
