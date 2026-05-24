# GitHub Publish Final Dry Run v0.7.12

v0.7.12 is the final local dry run before a GitHub publish. It checks that the release-operation docs, commands, package verification, and stop conditions remain aligned.

This is a documentation and verification task only. It does not change CI requirements, scanner configuration, release scripts, package behavior, decision logic, thresholds, `reliability_policy`, generated outputs, or release archives.

## Final Dry Run Scope

Confirm these areas before publishing:

- README links to the publish readiness checklist and integration review.
- `docs/github_publish_readiness_checklist.md` lists the release commands and stop conditions.
- `docs/pre_publish_integration_review_v0.7.11.md` describes the responsibility map.
- `docs/security_audit_tooling.md` keeps `scripts/security_audit.ps1` as the local publish-readiness gate.
- `docs/secret_scanner_adoption_v0.7.5.md` keeps Gitleaks optional and TruffleHog as a candidate scanner.
- `docs/scanner_findings_integration_decision_v0.7.10.md` keeps scanner findings out of `PACKAGE_MANIFEST.json`.
- Generated reports, cache, runtime outputs, and release archives remain out of source control.

## Required Local Evidence

Run these checks from the repository root:

```powershell
git status --short
git diff --check
python -m ruff check .
python -m black --check .
python -m mypy .
python -m pytest
powershell -ExecutionPolicy Bypass -File scripts\security_audit.ps1 -Python "python" -ExpectedTag "<release-tag>" -Strict
python scripts\create_release_package.py --dry-run
python scripts\create_release_package.py
python scripts\verify_release_package.py --latest-dir release --expected-tag "<release-tag>" --expected-commit "<short-commit>"
```

For the v0.7.12 fixed release, use `-ExpectedTag "v0.7.12"` and `--expected-tag "v0.7.12"` after the tag points at the intended commit.

## Forbidden Diff Checks

These commands should print no diff:

```powershell
git diff -- .github\workflows\ci.yml
git diff -- scripts\security_audit.ps1
git diff -- scripts\create_release_package.py
git diff -- scripts\verify_release_package.py
git diff -- project\reliability_policy.py
git diff -- project\threshold_decision_policy.py
git diff -- project\buy_window_diagnostics.py
git diff -- project\buy_candidate_near_miss.py
git diff -- project\risk_line_thresholds_active.json
git diff -- project\risk_line_thresholds_proposed.json
```

Also confirm `.gitleaks.toml` is not present unless a later explicit release task adopts it.

## Publish Stop Conditions

Stop before publishing if any of these are true:

- security audit does not report `publish_readiness: pass`
- `detect-secrets` finding count is not zero
- pip-audit fails for requirements or lock inputs
- package verification fails
- forbidden entries are present in the source archive
- generated reports, cache, runtime outputs, or release archives are tracked
- threshold JSON, `reliability_policy`, or decision path files have diffs
- required scanner CI, `.gitleaks.toml`, allowlist entries, TruffleHog CI, or script changes become necessary
- raw scanner finding content or secret-adjacent values would need to be copied into docs
- wording would make the project look like regulated advice or automated trading guidance

## v0.7.12 Completion Evidence

The final dry run is complete when:

- README, docs, and CHANGELOG point to the same release workflow.
- the publish readiness checklist has no unresolved blocker.
- local validation and release package verification pass.
- forbidden diff checks are empty.
- the v0.7.12 source package manifest tag and commit match the fixed release.
