# GitHub Actions Runtime Notice Review v0.8.7

v0.8.7 records a read-only review of runtime notices shown by the successful GitHub Actions run triggered after syncing the v0.8.1 through v0.8.6 commits and tags. This review does not change workflow configuration, action versions, runners, scripts, dependencies, report behavior, or investment decision logic.

## Reviewed Run

| Item | Value |
| --- | --- |
| Repository | `kapioka/global-market-monitor` |
| Workflow | `CI` |
| Run ID | `26401064522` |
| Trigger | `push` to `main` |
| Head commit | `0a0b4b09e0a27b9c3f43c6af1c009026bbf0887e` |
| Overall result | `success` |
| Run URL | `https://github.com/kapioka/global-market-monitor/actions/runs/26401064522` |

Read-only evidence was collected using:

```powershell
gh run view 26401064522 --repo kapioka/global-market-monitor --json status,conclusion,event,headSha,url,jobs
gh run view 26401064522 --repo kapioka/global-market-monitor --log
gh run view 26401064522 --repo kapioka/global-market-monitor --log-failed
gh api repos/kapioka/global-market-monitor/check-runs/77713242922/annotations
gh api repos/kapioka/global-market-monitor/check-runs/77713242940/annotations
```

`--log-failed` returned no failed-step output because both jobs completed successfully.

## Notice Summary

| Notice | Job | Origin identified by annotation | Effect in reviewed run |
| --- | --- | --- | --- |
| Node.js 20 action deprecation warning | `Gitleaks optional scan` | `actions/checkout@v4`, `gitleaks/gitleaks-action@v2` | Warning only; job succeeded |
| Node.js 20 action deprecation warning | `validate` | `actions/checkout@v4`, `actions/setup-python@v5` | Warning only; job succeeded |
| `windows-latest` migration notice | `validate` | `runs-on: windows-latest`; hosted runner notice states requests are redirected to `windows-2025-vs2026` by June 15, 2026 | Notice only; job succeeded |

## Job Results

### Gitleaks optional scan

- Runner declaration in the current workflow: `ubuntu-latest`.
- Actions used: `actions/checkout@v4` and `gitleaks/gitleaks-action@v2`.
- Result: `success`.
- The action scanned the six newly pushed commits and reported `no leaks found`.
- The Node.js warning is an upstream action-runtime lifecycle notice, not a scanner finding.

### validate

- Runner declaration in the current workflow: `windows-latest`.
- Actions associated with the Node.js warning: `actions/checkout@v4` and `actions/setup-python@v5`.
- Result: `success`.
- Successful steps included tests, ruff, black check, mypy, dependency audit, security audit, release-package dry run, release-package creation, and release-package verification.
- The hosted runner notice concerns future routing of `windows-latest`; it did not change the outcome of the reviewed run.

## Current Impact

- Neither notice caused a workflow failure.
- Neither notice is a release blocker for the already synchronized v0.8.1 through v0.8.6 tags.
- No Gitleaks finding was reported.
- The CI security audit completed with `publish_readiness: pass` and `detect-secrets` findings of zero.
- Immediate CI configuration change is not required for v0.8.7 because current validation remains green and this version is limited to recording the operational signal.

## Why v0.8.7 Does Not Change CI

- The current workflow is passing, so a runtime migration change should be scoped and validated independently instead of being bundled into a notice review.
- Updating action versions or selecting an explicit Windows runner changes the public CI execution environment and requires its own acceptance criteria.
- Keeping this review documentation-only preserves the decision-logic, security-script, and release-operation boundaries already established for the v0.8.x sequence.

## Future Response Options

The following are candidates for a separately approved CI-maintenance change:

- Review upstream versions of `actions/checkout`, `actions/setup-python`, and `gitleaks/gitleaks-action` for Node.js 24 support.
- Determine whether to adopt an explicit Windows runner image instead of relying on `windows-latest` routing.
- Re-run the full CI matrix after any action or runner change.
- Keep the optional scanner non-blocking unless a separate release policy change is explicitly approved.

## Conditions for a Future CI Change

A follow-up CI change should start only when at least one of these is true:

- An upstream action release provides the appropriate runtime migration path.
- GitHub begins enforcing the announced Node.js runtime transition for the currently used actions.
- The hosted Windows runner migration causes a reproducible failure, dependency problem, or output difference.
- Maintainers intentionally choose to make runner selection explicit before the hosted migration takes effect.

Any such change must be verified with tests, lint, type checks, dependency and security audit, and release-package verification before being merged or published.

## Unchanged Surfaces

v0.8.7 does not change:

- `.github/workflows/ci.yml`
- GitHub Actions versions or runner declarations
- security or release scripts
- dependencies or lock files
- report UI or decision logic
- threshold JSON, reliability policy, `final_action`, or readiness-score calculation
- generated reports, cache, or release archives
- GitHub Releases
