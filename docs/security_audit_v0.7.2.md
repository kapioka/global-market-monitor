# Security Audit v0.7.2

## Target

- Audit date: 2026-05-23
- Release candidate commit before audit: `06a7ee8`
- Release tag before audit: `v0.7.2`
- Scope: tracked source tree plus publish-facing docs, with generated reports/cache excluded from source control

## Result

- Publish readiness: pass
- Push performed: no
- Security fixes required: no
- History rewrite required: no
- Reusable audit tooling: added after the initial v0.7.2 release audit

## Checks

### Git metadata

- `git status --short`: clean before audit changes
- `git tag --points-at HEAD`: `v0.7.2`
- HEAD author / committer: GitHub noreply address
- `gmail.com` / `akisoe` metadata scan: no matches

### Secret scan

- Reusable script: `scripts/security_audit.ps1 -Strict`
- External / optional tools:
  - `gitleaks`: not installed, recorded as missing and covered by fallback scans
  - `trufflehog`: not installed, recorded as missing and covered by fallback scans
  - `detect-secrets`: installed from `requirements-security.txt` and executed
- `detect-secrets` result: pass, `finding_count: 0`
- Fallback `git grep` scan: no credential values found
- Strong secret pattern scan: pass, `hit_count: 0`
- PowerShell source scan: no credential values found
- Workspace `check_secrets.ps1` with explicit repo root completed.

Notes:

- `check_secrets.ps1` reported medium findings for ordinary code identifiers such as `key=`, `stage_key`, sort-key callbacks, and locally generated `.tmp/security` scan outputs. These were reviewed as false positives, not credentials.
- The first `check_secrets.ps1` attempt was started without a repo root and was stopped after it scanned too broadly. The audit was rerun with `-RepoRoot` set to this repository.

### Local path / personal information scan

- Tracked files do not contain the actual workspace path as publish-facing runtime configuration.
- Path-like hits were reviewed as:
  - test fixtures using `E:\dist\...` or `C:\repo\...`
  - dynamic `Path.home() / AppData` handling in `sitecustomize.py`
  - ignored archive / visual-evidence files outside the source-controlled publish set
- No personal email was found in tracked commit metadata.

### Generated files / cache

- `project/reports/`, `project/cache/`, `.tmp/`, `.runtime/`, Python caches, and local package artifacts are ignored.
- `git ls-files` did not show generated reports/cache, zip files, databases, logs, parquet files, or generated CSV files as tracked release content.

### TimesFM exclusion

- TimesFM is not present in normal pipeline/report code.
- Remaining TimesFM references are limited to:
  - release notes stating it is excluded
  - `docs/experimental_timesfm_evaluation.md`
  - a test assertion that report output does not contain TimesFM

### Investment-advice wording

- README/docs/report wording states:
  - this tool does not provide investment advice or buy instructions
  - `buy_readiness_score` is not probability, expected return, or investment success rate
  - next review conditions / `unlock_conditions` are not automatic buy conditions
  - `buy_candidate` and `buy_window` are not buy instructions

### Dependency check

- `python -m pip check` reported an environment-level conflict:
  - `argostranslate 1.9.6` requires `sentencepiece==0.2.0`, but installed `sentencepiece` is `0.2.1`
- `argostranslate` and `sentencepiece` are not listed in this project's requirements files, so this is treated as a global environment note, not a release blocker.
- `pip-audit` was installed from `requirements-security.txt`.
- `pip-audit -r project/requirements.txt`: pass, no known vulnerabilities found.
- `pip-audit` on the filtered lock input: pass, no known vulnerabilities found.
- Requirements scan found no TimesFM, torch, jax, flax, or tensorflow dependency in project requirements.

### Audit tooling

- Added `scripts/security_audit.ps1` for repeatable pre-publish checks.
- Added `requirements-security.txt` for Python security tooling:
  - `detect-secrets==1.5.0`
  - `pip-audit==2.10.0`
- Added `docs/security_audit_tooling.md` with usage, strict mode, missing-tool handling, and push checklist.
- Audit outputs are written under `.tmp/security/` and are not source-controlled.

### Final validation

- `python -m compileall -q project`: pass
  - Note: existing `.runtime` listing warnings were printed, exit code 0.
- `python -m pytest project/tests --basetemp .tmp/pytest/v072_release`: 282 passed
- `python -m pytest project/tests --basetemp .tmp/pytest/v072_security_tooling`: 282 passed
- `python project/main.py --sample-only`: pass
- `scripts/security_audit.ps1 -Strict`: pass, `publish_readiness: pass`
- `python -m project.buy_decision_audit`: pass
- `python -m project.validation_price_export`: pass
- `python -m project.run_action_validation`: pass
- `python -m project.threshold_historical_replay`: pass
- `python -m project.buy_window_diagnostics`: pass
- `python -m project.fx_soft_cap_watchlist`: pass, `adoption_decision: hold`
- `python -m project.regime_aware_fx_policy_replay --features project/cache/historical_features_long.csv`: pass, `adoption_decision: hold`
- `python -m ruff check .`: pass
- `python -m black --check .`: pass
- `python -m mypy project/buy_readiness_score.py project/buy_blocker_breakdown.py project/buy_unlock_conditions.py project/buy_decision_card.py project/buy_decision_audit.py`: pass

## Remaining Known Limitations

- `gitleaks` and `trufflehog` were not available locally. The reusable audit script records them as missing and runs fallback scans.
- Ignored archive and visual-evidence folders exist in the workspace but are not tracked in the release source set.
- `fx_soft_cap`, DD guard, and regime-aware candidates remain diagnostic-only / hold.

## Publish Recommendation

Publish readiness is pass for the tracked source tree. It is safe to push `main` and tag `v0.7.2` after confirming the remote tag does not already exist or intentionally updating the remote with the current tag.
