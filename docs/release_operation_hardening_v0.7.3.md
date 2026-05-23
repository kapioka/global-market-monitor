# v0.7.3 Release / Operation Hardening

v0.7.3 is an operation-hardening release. It does not change `final_action`, `reliability_policy`, active/proposed threshold JSON, `buy_window`, or `buy_candidate` thresholds.

## Local Validation

```powershell
python -m pytest
python -m ruff check .
python -m black --check .
python -m mypy .
.\scripts\audit_python_dependencies.ps1 -Python "python"
.\scripts\security_audit.ps1 -Python "python" -ExpectedTag "" -Strict
python scripts/create_release_package.py --dry-run
```

`python -m mypy .` is intentionally configured as the current operational type-checking surface. v0.7.3 does not expand full-repository typing or change decision logic; it records a repeatable CI target while excluding older modules that still need separate typing cleanup.

## Release Package

Create a source-only archive:

```powershell
python scripts/create_release_package.py
```

The archive is written under `release/` and includes a `PACKAGE_MANIFEST.json` with commit, tag, version source, file list, and exclusion rules.

The package script uses tracked source files from Git and rejects tracked files that match generated/cache/secret-like exclusion rules. It excludes paths such as:

- `project/reports/`
- `project/cache/`
- `.tmp/`
- `.pytest_tmp/`
- `release/`
- `github_upload/`
- `archive/`

For v0.7.6 and later, verify the generated archive before publishing:

```powershell
python scripts\verify_release_package.py --package release\global-market-monitor-<release-tag>-source.zip --expected-tag <release-tag>
```

This checks the package manifest, release tag, optional commit prefix, required release docs, and forbidden generated/cache/secret-adjacent entries.

## Security Audit Operation

`scripts/security_audit.ps1` runs local and CI-friendly checks:

- Git metadata and optional expected tag verification
- gitleaks, detect-secrets, and trufflehog when installed
- fallback grep checks for high-risk secret patterns
- generated/cache tracked-file checks
- threshold JSON diff checks
- TimesFM dependency/reference checks
- pip check and pip-audit when available

Optional scanners are not required to be installed for routine local development. Missing tools are reported as warnings or tool-status entries; strong secret patterns and generated/cache tracking remain blockers.

`pip check` can report an existing local environment warning such as `argostranslate` requiring `sentencepiece==0.2.0` while the environment has `sentencepiece 0.2.1`. Treat this as an environment hygiene note unless the project starts depending on that optional translation stack. `pip-audit` remains the release vulnerability check.

## detect-secrets Baseline

The audit writes a generated baseline-like scan output to `.tmp/security/detect-secrets.baseline.json` when `detect-secrets` is installed. Treat it as a review artifact, not as a source-controlled approval by itself.

If a stable baseline is intentionally introduced later, keep it reviewed and small, and continue to run:

```powershell
detect-secrets scan --all-files
```

before release packaging.

## Optional Future Scanners

`gitleaks` and `trufflehog` are supported when available on PATH. If they are not installed, the audit records their status and continues with fallback checks. For public release, installing both tools before the final publish review is recommended.

TODO for v0.7.4: decide whether to make one or both optional scanners part of the recommended release workstation setup.
