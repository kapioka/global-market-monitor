# Changelog

## v0.7.9 - Gitleaks Optional CI Evaluation

### Added

- Added documentation for evaluating the optional Gitleaks CI trial.
- Added guidance for checking non-blocking behavior, CI logs, finding handling, and required-enforcement decision inputs.

### Changed

- Linked secret scanner adoption and publish readiness documentation to the v0.7.9 evaluation note.

### Security

- Documented that Gitleaks remains optional and non-blocking in v0.7.9.
- Documented that verified or high-confidence findings should stop public release review.
- Confirmed that required CI enforcement, `.gitleaks.toml`, and allowlist changes remain out of scope.

## v0.7.8 - Gitleaks Optional CI Trial

### Added

- Added a non-blocking GitHub Actions job for optional Gitleaks scanning.
- Documented Gitleaks CI trial behavior and release-stop handling for findings.

### Changed

- Clarified that Gitleaks CI is observational in v0.7.8 and is not a required release gate.

### Security

- Kept Gitleaks findings subject to manual review before release, without adding a default allowlist.

## v0.7.7 - CI Release Package Verification Integration

### Added

- Added latest release package auto-detection to release package verification.
- Added CI release package creation and manifest verification after dry-run validation.
- Added tests for latest release package detection.

### Changed

- Documented CI tagless package verification and release-tag verification guidance.

### Security

- Connected CI to the same generated/cache and forbidden-entry package verification used for local release checks.

## v0.7.6 - Release Package Manifest Verification

### Added

- Added release package verification tooling for source archives.
- Added automated checks for package manifest tag, commit, file count, required files, and forbidden entries.
- Added tests for release package verification behavior.

### Changed

- Linked publish readiness guidance to the release package verification command.

### Security

- Documented and automated checks for generated/cache, `.git`, `.env`, release recursion, and secret-adjacent package entries.

## v0.7.5 - Secret Scanner Adoption Decision

### Added

- Added secret scanner adoption guidance for Gitleaks and TruffleHog.
- Added local optional scanner commands for release workstations.
- Added release stop conditions for verified or high-confidence secret findings.

### Changed

- Clarified that Gitleaks is the preferred optional scanner and TruffleHog remains a candidate scanner.
- Linked publish readiness guidance to the secret scanner adoption documentation.

### Security

- Documented non-blocking scanner setup, escalation criteria, and public release stop conditions for secret findings.
- Documented that false positives should not be immediately allowlisted without rationale.

## v0.7.4 - GitHub Publish Readiness Checklist

### Added

- Added GitHub publish readiness checklist documentation.
- Added explicit release package manifest verification steps.
- Added known-warning handling for gitleaks/trufflehog and local pip check notes.

### Changed

- Linked README release guidance to the publish readiness checklist.

### Security

- Documented pre-publish checks for forbidden entries, generated/cache exclusion, secrets-adjacent files, and threshold/decision logic non-change verification.

## v0.7.3 - Release / Operation Hardening

### Added

- Added GitHub Actions CI for tests, linting, formatting checks, typing, dependency audit, security audit, and release package dry-run validation.
- Added a source-only release package script with generated/cache exclusion rules and a JSON manifest.
- Added sample-only documentation fixtures under `docs/sample/` for README references without committing live reports or cache.

### Changed

- Documented the shortest local run path, sample-only interpretation, Buy Decision Card reading notes, generated-file handling, and common misunderstandings.
- Kept v0.7.3 scoped to release and operational hardening without changing investment decision logic.

### Security

- Hardened the local security audit path for CI use and kept optional scanners as warnings when unavailable.
- Documented detect-secrets baseline handling and continued pip-audit usage for release checks.
