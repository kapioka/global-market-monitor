# Post-Publish Operation Baseline v0.8.0

v0.8.0 defines the first operating baseline after the GitHub publish. It keeps the release workflow focused on evidence collection, public repository checks, and safe follow-up handling.

This is an operations documentation and CI-stability update. It does not change decision logic, threshold JSON, `reliability_policy`, scanner enforcement, release scripts, generated outputs, or release archives.

## Immediate Post-Publish Checks

After pushing `main` and the release tag, confirm:

- GitHub Actions starts for the pushed commit.
- The required `validate` job completes successfully.
- The non-blocking `gitleaks-optional` job completes or has an explained non-blocking issue.
- The GitHub Release points at the intended tag.
- The attached source archive matches the package generated locally.
- README links still lead to the publish readiness checklist, final dry run, and this post-publish baseline.

Useful commands:

```powershell
git status --short
git ls-remote --heads origin main
git ls-remote --tags origin <release-tag>
gh run list --limit 5
gh release view <release-tag>
```

## GitHub Actions Review

The required `validate` job is the public CI gate. It should run:

- tests
- ruff
- black check
- mypy
- dependency audit
- security audit
- release package dry run
- release package creation
- release package verification

The pytest temporary directory uses `.pytest_tmp` so clean CI checkouts do not depend on a pre-existing `.tmp` parent directory.

## Gitleaks Optional Job

`gitleaks-optional` remains a non-blocking observation signal.

Review it after each publish:

- If it passes, record no additional action.
- If it fails because of setup or runner behavior, record the reason in release review notes.
- If it reports a verified, high-confidence, or unexplained secret finding, stop further release promotion until the finding is reviewed.
- Do not add allowlist entries without a written rationale and a narrow scope.

## GitHub Release Review

For each release, confirm:

- tag name
- title
- release notes
- attached source archive
- archive filename
- package verification output
- forbidden entries count

Release notes should keep these points clear:

- source-only archive
- security audit passed
- release package verification passed
- forbidden entries were zero
- generated reports, cache, runtime outputs, and release archives are excluded from source control
- this project is not investment advice
- this project does not perform automated trading

## Issue Intake

For ordinary issues:

1. Confirm whether the report concerns installation, CI, docs, generated outputs, or runtime behavior.
2. Reproduce with sample-only data when possible.
3. Avoid using real personal data or private local paths in issue replies.
4. Keep generated reports and cache out of commits.
5. If the issue requests decision-logic changes, move it to a separate scoped task.

## Security Finding Intake

For security reports:

1. Do not copy raw secret values into docs, issues, or release notes.
2. Confirm whether the finding is verified, high-confidence, or unexplained.
3. Stop publish or release promotion while the finding is unresolved.
4. Run local security audit and package verification after any remediation.
5. Avoid broad allowlists; prefer removing or rotating the exposed value when applicable.

## Generated Output Handling

Generated reports, cache, runtime logs, temporary scan output, and release archives remain local artifacts. They are not source files and should not be committed.

Before pushing, check:

```powershell
git status --short
git diff --check
```

If generated output appears in `git status`, stop and exclude or remove it from the commit scope before continuing.

## v0.8.x Candidates

Future v0.8.x work can consider:

- v0.8.1 report UI redesign planning for a beginner-readable `まず見るポイント` and 5-step `買い判断カード` without changing decision logic.
- Node.js runtime migration notes for GitHub Actions when upstream actions require it.
- Better CI artifact retention for release package review.
- Optional scanner result summaries that do not copy raw findings.
- More typed coverage for older modules as a separate type-cleanup track.
- A release-review template for issue and security intake.

## Out of Scope for v0.8.0

v0.8.0 does not:

- change decision logic
- change threshold JSON
- change `reliability_policy`
- promote diagnostic FX policy candidates into active behavior
- add automated trading or trading instructions
- make Gitleaks required in CI
- add TruffleHog CI
- add `.gitleaks.toml`
- add scanner allowlists
- make pre-commit mandatory
- commit generated reports, cache, runtime logs, or release archives

## Completion Evidence

v0.8.0 is complete when:

- this document is present
- README or related docs link to it
- CHANGELOG records v0.8.0
- local lint, format check, type check, tests, and security audit pass
- release package generation and verification pass after the v0.8.0 tag is fixed
- forbidden diff checks for decision logic, thresholds, scripts, and scanner configuration are empty
- `main` and `v0.8.0` are pushed, or manual follow-up requirements are explicitly reported
