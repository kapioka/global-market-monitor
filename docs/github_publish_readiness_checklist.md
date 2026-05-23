# GitHub Publish Readiness Checklist

This checklist is for the final pre-publish review before a GitHub release. It is meant to prevent publishing accidents, secret leakage, generated-file inclusion, and unintended decision-logic changes.

This is not investment advice, does not improve investment decision logic, and does not change `final_action`, thresholds, `reliability_policy`, `buy_window`, or `buy_candidate` behavior.

## Scope

Use this checklist for releases based on v0.7.3 or later release-operation hardening.

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
powershell -ExecutionPolicy Bypass -File scripts\security_audit.ps1 -Python "python" -ExpectedTag "<release-tag>" -Strict
python scripts\create_release_package.py --dry-run
python scripts\create_release_package.py
```

For a v0.7.3 publish check, use `-ExpectedTag "v0.7.3"`. For the next release, pass the actual target tag as `-ExpectedTag "<release-tag>"`.

## Tag Check

```powershell
git tag --list "v0.7.*"
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

## Known Warnings

`gitleaks` and `trufflehog` are workstation-optional at this stage. If they are not installed, `security_audit.ps1` records that status and continues with fallback checks. Missing optional scanners are not release blockers by themselves.

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

Publish is allowed only when all are true:

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
