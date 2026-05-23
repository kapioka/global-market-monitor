# Changelog

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
