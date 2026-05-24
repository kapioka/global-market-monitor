# Scanner Findings Integration Decision v0.7.10

v0.7.10 defines how findings from the optional Gitleaks CI job should affect release decisions before any required-CI enforcement is adopted.

This is an operations and security documentation task only. It does not change `final_action`, active/proposed threshold JSON, `reliability_policy`, `buy_window`, `buy_candidate`, `fx_soft_cap`, TimesFM, or regime-aware policy behavior.

## Purpose

- Decide how optional Gitleaks CI findings feed into release readiness.
- Clarify where findings are recorded.
- Keep `scripts/security_audit.ps1` as the primary local release-readiness gate.
- Avoid adding required Gitleaks CI, TruffleHog CI, `.gitleaks.toml`, or allowlist entries in v0.7.10.

## Decision Summary

Gitleaks optional CI findings are release review inputs, not standalone release gates.

Adopted:

- Review the `gitleaks-optional` job before public release.
- Treat verified, high-confidence, or unexplained findings as release stop conditions.
- Record local scanner availability and local scan outcomes in `scripts/security_audit.ps1` outputs.
- Record CI finding triage in release review notes or issue/PR discussion, without copying secret values.
- Keep release package manifest verification focused on source package reproducibility and forbidden-entry checks.

Not adopted in v0.7.10:

- Required Gitleaks CI enforcement.
- TruffleHog CI.
- `.gitleaks.toml`.
- Gitleaks allowlist entries.
- Release package manifest fields for scanner findings.
- Automated promotion of optional CI findings into threshold or decision logic.

## Recording Locations

| Location | v0.7.10 decision | Reason |
|---|---|---|
| GitHub Actions `gitleaks-optional` logs | Record observation signal | CI is where the optional action runs. |
| `scripts/security_audit.ps1` outputs | Record local scanner availability and local scan results | This remains the primary local release-readiness gate. |
| `docs/github_publish_readiness_checklist.md` | Record release reviewer obligations | The checklist is the human publish gate. |
| Release package `PACKAGE_MANIFEST.json` | Do not record scanner findings | The manifest should describe package contents, commit, tag, and exclusion rules, not mutable CI triage. |
| CHANGELOG | Record policy changes | Version history should capture the decision. |

If scanner findings need durable detail, record only sanitized summaries in release review notes. Do not copy secret values, secret-adjacent paths from private environments, or raw scanner excerpts into public docs.

## Release Decision Rule

Publishing can continue when all are true:

- `gitleaks-optional` is clean, skipped for an understood infrastructure reason, or has reviewed false positives with narrow rationale.
- `scripts/security_audit.ps1 -Strict` reports `publish_readiness: pass`.
- `detect-secrets` reports `finding_count: 0`.
- `pip-audit` exits with code `0`.
- release package verification reports `release_package_verification: pass`.
- decision-logic and threshold non-change checks show no diff.

Publishing must stop when any are true:

- Gitleaks reports a verified secret.
- Gitleaks reports a high-confidence secret.
- A finding cannot be explained without exposing secret-adjacent values.
- A finding suggests `.env`, local private config, generated report output, cache, or release package contamination.
- Local `security_audit.ps1 -Strict` fails publish readiness.
- The release package manifest or verifier reports forbidden entries.

## Triage Workflow

When `gitleaks-optional` reports a finding:

1. Stop public release review.
2. Inspect the GitHub Actions log without copying secret values into docs or chat.
3. Classify the finding as verified, high-confidence, unverified, infrastructure/tool failure, or reviewed false positive.
4. Compare the CI result with local `scripts/security_audit.ps1 -Strict` output.
5. Remove, rotate, or document the finding before release resumes.
6. If the finding is a false positive, record a narrow rationale in release notes or audit notes. Do not add an allowlist by default.

## Security Audit Boundary

`scripts/security_audit.ps1` already runs local Gitleaks checks when the binary is available and records missing tools as non-blocking. v0.7.10 does not change that behavior.

Future automation may ingest CI scanner artifacts into a structured audit summary, but only after the output format and redaction rules are defined. Until then, CI findings remain human-reviewed release inputs.

## Release Manifest Boundary

`PACKAGE_MANIFEST.json` remains a package-content manifest. It should continue to record:

- package name
- commit and tag
- tracked source files
- excluded prefixes and suffixes
- generated/cache and forbidden-entry exclusions

It should not record scanner findings in v0.7.10 because scanner results depend on CI context, tool version, licensing/runtime behavior, and triage state. Keeping findings out of the manifest avoids mixing release artifact inventory with mutable review evidence.

## Future Decision Inputs

Before making Gitleaks required, collect:

- at least one clean optional CI run on the release branch
- behavior on pull request and tag workflows
- known false positive examples, if any
- documented redaction rules for scanner excerpts
- confirmation that required enforcement will not block releases on tool licensing or runtime setup issues
- a decision on whether scanner results should be summarized as CI artifacts rather than manifest fields

## Completion Checks

- Gitleaks remains optional and non-blocking.
- TruffleHog CI is not added.
- `.gitleaks.toml` is not added.
- No allowlist is added.
- `scripts/security_audit.ps1` behavior is unchanged unless a future task explicitly adopts scanner result ingestion.
- release package manifest behavior is unchanged.
- decision logic, thresholds, and `reliability_policy` have no diff.
