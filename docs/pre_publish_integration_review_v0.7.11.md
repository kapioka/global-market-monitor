# Pre-Publish Integration Review v0.7.11

v0.7.11 reviews how the public-release operation pieces added from v0.7.3 through v0.7.10 connect to each other.

This is a documentation and release-operations review. It does not change CI enforcement, scanner configuration, release scripts, package generation behavior, decision logic, thresholds, `reliability_policy`, generated outputs, or release archives.

For the final local dry run before publishing, see `docs/github_publish_final_dry_run_v0.7.12.md`.

## Scope

Reviewed release-operation areas:

- GitHub Actions CI
- local security audit
- source release package generation
- release package manifest verification
- GitHub publish readiness checklist
- optional Gitleaks CI trial and evaluation
- scanner finding integration policy

Out of scope for v0.7.11:

- required scanner CI
- TruffleHog CI
- pre-commit enforcement
- `.gitleaks.toml`
- allowlist entries
- release script changes
- investment decision logic changes
- threshold JSON changes
- generated report, cache, or release archive commits

## Responsibility Map

| Area | Primary artifact | Responsibility |
|---|---|---|
| CI validation | `.github/workflows/ci.yml` | Runs tests, lint, formatting, type checks, dependency audit, security audit, package creation, and package verification. |
| Local release security gate | `scripts/security_audit.ps1` | Produces `publish_readiness` and local scanner/dependency/generated-artifact evidence. |
| Release source archive | `scripts/create_release_package.py` | Builds a source-only package from tracked source files and excludes generated/cache/secret-adjacent paths. |
| Package manifest verifier | `scripts/verify_release_package.py` | Validates package manifest tag, commit, required files, file count, and forbidden entries. |
| Human publish checklist | `docs/github_publish_readiness_checklist.md` | Lists the manual pre-publish commands and stop conditions. |
| Scanner adoption decision | `docs/secret_scanner_adoption_v0.7.5.md` | Defines Gitleaks as the preferred optional scanner and TruffleHog as a candidate scanner. |
| Optional Gitleaks CI evaluation | `docs/gitleaks_optional_ci_evaluation_v0.7.9.md` | Describes how to inspect the non-blocking Gitleaks job before any required-enforcement decision. |
| Scanner finding integration | `docs/scanner_findings_integration_decision_v0.7.10.md` | Defines where optional scanner findings affect release review and where they are not recorded. |

## Integrated Pre-Publish Flow

Use this order for a public-release review:

1. Confirm the working tree and intended release tag.
2. Run local validation: tests, lint, format check, type check, dependency audit, and security audit.
3. Review the GitHub Actions `validate` job.
4. Review the non-blocking `gitleaks-optional` job as an observation signal.
5. Generate the source package from a clean tree.
6. Verify the package manifest with the target tag and commit.
7. Confirm decision-logic and threshold non-change checks.
8. Publish only when the checklist allows release and no stop condition is present.

## Consistency Decisions

- `scripts/security_audit.ps1` remains the primary local publish-readiness gate.
- `gitleaks-optional` remains non-blocking and observational.
- Verified, high-confidence, or unexplained scanner findings stop public release review even when the CI job is non-blocking.
- `PACKAGE_MANIFEST.json` remains package inventory metadata and does not store scanner findings.
- CI validates package creation and manifest verification, but release tag matching remains a release-publish check.
- Missing local Gitleaks or TruffleHog binaries remain non-blocking when fallback checks and required security checks pass.
- Generated reports, cache, runtime outputs, and release archives remain excluded from source control.

## Release Stop Conditions

Stop and report before continuing if any of these are required to proceed:

- making Gitleaks or another scanner required in CI
- adding `.gitleaks.toml`
- adding allowlist entries
- adding TruffleHog CI
- changing release scripts or security audit scripts
- changing decision logic, threshold JSON, or `reliability_policy`
- committing generated reports, cache, or release archives
- adding wording that looks like regulated advice or automated trading guidance
- copying raw scanner finding content or secret-adjacent values into docs

## v0.7.11 Completion Evidence

Completion requires:

- docs and CHANGELOG references are internally consistent
- public-release command sequence is clear
- responsibility boundaries are documented
- forbidden files have no diff
- lint, format check, type check, tests, security audit, and release package verification pass
