# Gitleaks Optional CI Evaluation v0.7.9

v0.7.9 evaluates the non-blocking Gitleaks GitHub Actions job added in v0.7.8. This is an operations and CI documentation task only. It does not change `final_action`, active/proposed threshold JSON, `reliability_policy`, `buy_window`, `buy_candidate`, `fx_soft_cap`, or regime-aware policy behavior.

## Scope

This evaluation covers:

- how the `gitleaks-optional` job behaves when it passes or reports findings
- where to review logs and annotations
- how to handle findings while the job remains non-blocking
- what evidence is still needed before any required-CI decision

This evaluation does not add:

- required Gitleaks branch protection
- `.gitleaks.toml`
- allowlist entries
- pre-commit hooks
- release package changes
- investment decision logic changes

## Current CI Behavior

The v0.7.8 workflow has a separate `gitleaks-optional` job in `.github/workflows/ci.yml`.

Expected behavior:

- The job runs on `push`, `pull_request`, and manual `workflow_dispatch` events.
- It checks out full Git history with `fetch-depth: 0`.
- It uses `gitleaks/gitleaks-action@v2` with the default action behavior.
- It runs with `continue-on-error: true`.
- A failure or finding is an observation signal, not a release-readiness gate by itself.

The Windows `validate` job remains the primary CI gate for tests, lint, type checks, dependency audit, security audit, and release package verification.

## Log Review Procedure

For each candidate release or PR:

1. Open the GitHub Actions run for the commit or PR.
2. Review the `Gitleaks optional scan` job result.
3. Open the `Run Gitleaks` step logs.
4. Check whether the job completed cleanly, reported findings, or failed for tool/runtime reasons.
5. Compare the result with the local `scripts/security_audit.ps1 -Strict` output.
6. Record unresolved findings or unexplained failures before publishing.

Treat the optional job as incomplete evidence when:

- the workflow did not run for the target commit
- the job was skipped or cancelled
- the log is unavailable
- the action failed before scanning
- the finding details cannot be explained without exposing secret-adjacent values

## Finding Handling

If Gitleaks reports a finding:

- Stop public release review until the finding is triaged.
- Do not add an allowlist entry as the first response.
- Determine whether the finding is verified, high-confidence, unverified, or a reviewed false positive.
- If a real secret may have been exposed, rotate or revoke it before continuing.
- Keep secret values out of issues, pull requests, docs, commit messages, and chat summaries.
- If the finding is a false positive, document the narrow reason in release notes or audit notes without copying sensitive log content.

Release remains blocked when:

- a verified secret finding exists
- a high-confidence secret finding exists
- a finding cannot be explained
- generated reports/cache or release output are involved
- local `security_audit.ps1 -Strict` does not report publish readiness

## Required-CI Decision Inputs

Do not make Gitleaks required until these inputs are available:

- at least one clean optional run on `main`
- at least one reviewed PR or manual-dispatch optional run
- documented behavior for findings, skipped runs, and action failures
- agreement that false positives can be handled without broad allowlists
- confirmation that `scripts/security_audit.ps1` remains the primary release-readiness gate
- confirmation that branch protection changes are desired and reversible

Required-CI adoption should be a separate release task. It should include an explicit rollback path for branch protection and should not be bundled with threshold, decision-logic, or release-package changes.

## v0.7.9 Completion Checks

For this evaluation task, completion means:

- docs describe non-blocking behavior and log review steps
- docs describe finding handling without exposing secret values
- docs list required-CI decision inputs
- no `.gitleaks.toml` or allowlist is added
- `.github/workflows/ci.yml` remains non-blocking unless a later task explicitly changes it
- decision logic and threshold files have no diff

Minimum local verification:

```powershell
git status --short
git diff --stat
git diff --check
python -m ruff check .
python -m black --check .
python -m mypy .
python -m pytest
```

Forbidden-diff verification:

```powershell
git diff -- project\reliability_policy.py
git diff -- project\threshold_decision_policy.py
git diff -- project\buy_window_diagnostics.py
git diff -- project\buy_candidate_near_miss.py
git diff -- project\risk_line_thresholds_active.json
git diff -- project\risk_line_thresholds_proposed.json
```

Run the full release package verification only when preparing an external publish, tag update, or fixed release package.

For the integrated pre-publish responsibility map across release-operation work, see `docs/pre_publish_integration_review_v0.7.11.md`.
