# Changelog

## v0.8.4 - Multi-Scenario Report UI Snapshot QA

### Added

- Added synthetic multi-scenario coverage for standard monitoring, near-candidate, wait, insufficient-data, no-candidate, and long-blocker beginner UI rendering states.
- Added snapshot QA documentation covering 1366px, 1024px, and 768px temporary render checks.

### Changed

- Confirmed the v0.8.3 HTML/CSS layout needs no additional product UI changes after multi-scenario QA.

### Security

- Confirmed the beginner top sections continue to exclude internal decision terms and investment-advice or outcome-guarantee wording.
- Kept JavaScript, external libraries, decision logic, threshold JSON, `reliability_policy`, `final_action`, `buy_readiness_score` calculation, CI, scanner configuration, allowlists, generated reports, cache, and release archives out of scope.

## v0.8.3 - Report UI Visual QA / Responsive Polish

### Changed

- Polished the beginner-friendly report top UI after generated HTML visual QA by keeping step-flow arrows inside the card bounds to avoid narrow overflow flags.
- Confirmed the `まず見るポイント` and 5-step `買い判断カード` remain HTML/CSS-only with no JavaScript or external library additions.

### Security

- Confirmed the top beginner sections avoid internal decision terms and investment-advice or outcome-guarantee wording.
- Kept decision logic, threshold JSON, `reliability_policy`, `final_action`, `buy_readiness_score` calculation, CI, scanner configuration, allowlists, generated reports, cache, and release archives out of scope.

## v0.8.2 - Beginner Summary HTML/CSS Implementation

### Added

- Added the beginner-readable `まず見るポイント` HTML section with six tiles for current judgment, buy-area state, market state, main reasons, next checks, and a beginner note.
- Added a 5-step `買い判断カード` HTML layout with a CSS-only readiness gauge and the required note that the score is not a success probability.
- Added report HTML tests for the new top sections and scoped internal-term exclusion.

### Changed

- Replaced the top `まず見る要約` and mixed `Buy Decision Card / 買い判断カード` HTML sections with Japanese-first beginner summary UI.
- Kept the implementation HTML/CSS-centered without adding JavaScript or external libraries.

### Security

- Kept decision logic, threshold JSON, `reliability_policy`, `final_action`, `buy_readiness_score` calculation, CI, scanner configuration, allowlists, generated reports, cache, and release archives out of scope.

## v0.8.1 - Report UI Redesign Plan

### Added

- Added a documentation-only report UI redesign plan for replacing the top `まず見る要約` and `Buy Decision Card / 買い判断カード` areas with beginner-readable `まず見るポイント` and a 5-step `買い判断カード`.
- Added Japanese display-label guidance for keeping internal terms out of the first screen while preserving existing decision outputs.
- Added a v0.8.2+ roadmap for HTML/CSS-first implementation and later progressive disclosure.

### Changed

- Clarified that v0.8.1 is a planning release and does not implement report generator changes.

### Security

- Confirmed that the plan does not change decision logic, threshold JSON, `reliability_policy`, CI, scanner configuration, allowlists, generated reports, cache, or release archives.

## v0.8.0 - Post-Publish Operation Baseline

### Added

- Added post-publish operation baseline documentation for GitHub Actions, GitHub Release, release package, scanner review, issue intake, and security finding intake.
- Added README and publish-doc links to the post-publish baseline.

### Changed

- Changed pytest temporary output to `.pytest_tmp` so clean CI checkouts do not require a pre-existing `.tmp` parent directory.
- Clarified drawdown summary typing so CI mypy on Python 3.11 accepts the diagnostic analysis module.

### Security

- Documented post-publish handling for non-blocking Gitleaks review, generated-output exclusion, and security finding intake without adding required scanner enforcement, scanner allowlists, or scanner configuration.

## v0.7.12 - GitHub Publish Final Dry Run

### Added

- Added final GitHub publish dry-run documentation.
- Added explicit final dry-run commands, forbidden diff checks, and publish stop conditions.

### Changed

- Linked README and publish readiness guidance to the final dry-run checklist.

### Security

- Confirmed final publish checks for security audit readiness, generated/cache/report exclusion, package manifest verification, and scanner finding handling without changing CI requirements or scanner configuration.

## v0.7.11 - Pre-Publish Integration Review

### Added

- Added a pre-publish integration review that maps CI, security audit, release packaging, manifest verification, optional scanner review, and scanner findings policy responsibilities.

### Changed

- Linked README and release-operation docs to the integrated pre-publish responsibility map.
- Replaced the stale optional-scanner TODO in the v0.7.3 hardening notes with references to the later scanner decision docs.

### Security

- Confirmed that scanner CI remains optional, findings are not written to the release package manifest, and generated/cache/release artifacts remain outside source control.

## v0.7.10 - Scanner Findings Integration Decision

### Added

- Added scanner findings integration decision documentation for optional Gitleaks CI findings.
- Added release review rules for verified, high-confidence, and unexplained scanner findings.

### Changed

- Clarified that optional Gitleaks CI findings are release review inputs, not standalone required CI gates.
- Clarified that scanner findings are recorded in CI logs, security audit outputs, and sanitized release review notes rather than `PACKAGE_MANIFEST.json`.

### Security

- Documented release stop conditions for optional scanner findings without adding `.gitleaks.toml`, allowlists, TruffleHog CI, or required Gitleaks enforcement.

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
