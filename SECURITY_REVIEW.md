# Security Review For Public Upload

Review date: 2026-07-29

Target repository: `kapioka/global-market-monitor`

Target version: `v0.11.0`

## Result

The proposed v0.11.0 source passed the local release validation contract and a clean, tagged rehearsal-package verification. No credential, private-key, generated-artifact, dependency-vulnerability, or protected-decision-surface blocker remains.

This preparation review did not itself commit, tag, push, or create a GitHub Release. GitHub-hosted CI and the real tag/commit manifest check are performed only after explicit publication permission.

## Threat Model

Primary assets:

- local runtime output under `project/reports`, `project/cache`, and `project/logs`
- generated market summaries, downloaded market data, and local SQLite databases
- the user's local filesystem privacy
- the integrity of production decision policy and threshold files
- GitHub Actions credentials and release artifacts

Trust boundaries:

- external public market-data providers
- local configuration and manual data
- generated local HTML opened in a browser
- third-party GitHub Actions
- the public GitHub repository and source archive

Security invariants:

- credentials, tokens, private keys, local account paths, and runtime data are not published
- generated reports, logs, caches, databases, and local comparison images are not published
- generated HTML treats embedded data as text unless it passes an explicit safe-HTML formatter
- CI uses least privilege and immutable third-party Action references
- `final_action`, reliability policy, thresholds, and Risk Engine V2 promotion state are not changed by release preparation

## Codex Security Review

A repository-wide Codex Security scan was run against the clean pre-remediation revision `d439c02`.

It reported two low-severity findings:

1. GitHub Actions used mutable major-version references and did not explicitly declare least-privilege permissions.
2. `design-qa.md` contained local absolute paths that disclosed a workstation account name and temporary artifact locations.

Both findings were remediated:

- CI now declares `permissions: contents: read`.
- checkout uses `persist-credentials: false`.
- checkout, setup-python, upload-artifact, and Gitleaks are pinned to reviewed full commit SHAs.
- Gitleaks is a required CI job.
- local absolute paths were removed from the public design QA document.

The review also prompted defense-in-depth hardening for local generated HTML:

- dashboard JSON neutralizes `<`, `>`, and `&` before script embedding;
- dynamic dashboard HTML accepts preformatted markup only through an explicit `SafeHtml` wrapper;
- dynamic labels, alerts, tables, timestamps, and SVG text are escaped;
- chronicle `generation_id` is escaped for an HTML attribute;
- chronicle `generated_at` is read from neutralized JSON and written through `textContent`.

Regression tests cover script termination, HTML injection, attribute injection, and JavaScript template-literal injection.

## Secret, Privacy, And Dependency Checks

Repository strict audit:

- `publish_readiness: pass`
- blockers: `0`
- `detect-secrets`: `0` findings
- strong secret patterns: `0` findings
- generated/cache artifacts in tracked source: `0`
- personal email hits in Git history: `0`
- dependency audit for requirements and lock: pass
- protected decision diff: `0`
- threshold JSON diff: `0`

The required global warning-mode secret scan was reviewed. In the isolated release rehearsal it reported only the scanner's medium `env_assignment` heuristic (`238` matches), with `0` high or critical matches. The matches are ordinary code assignments, the literal `persist-credentials: false`, and the GitHub-provided `${{ secrets.GITHUB_TOKEN }}` reference; no secret value is stored in the repository.

Local Gitleaks and TruffleHog executables were unavailable. This is not hidden: `detect-secrets`, strong-pattern scanning, dependency auditing, Codex Security, and package inspection were completed locally, while the hardened GitHub workflow requires Gitleaks when the authorized push runs.

The local Python environment has an unrelated `pip check` warning: installed `argostranslate 1.9.6` expects `sentencepiece==0.2.0`, while the workstation has `0.2.1`. The project requirements and lock dependency audits both passed, and the application does not depend on that optional translation stack.

## Validation Evidence

- focused HTML security tests: `7 passed`
- full test suite: `700 passed`
- Ruff: pass
- Black check: pass
- Mypy: pass for `299` source files
- generated dashboard JavaScript syntax: pass
- generated chronicle JavaScript syntax: pass
- strict tagged rehearsal security audit for `v0.11.0`: pass
- rehearsal source package: `421` tracked source files
- forbidden package entries: `0`
- required package files: pass
- rehearsal manifest tag and commit: pass

## Excluded Public Surface

- `.git`
- `release`, archives, and nested packages
- `project/reports`, generated HTML, and generated Markdown reports
- `project/cache`, `project/logs`, and runtime state
- SQLite databases and journal files
- manual market-data inputs
- local comparison screenshots and visual-evidence directories
- temporary, build, test, and Python cache output
- `.env`, keys, certificates, secret files, and secret-adjacent logs

## Authorization-Gated Publication Procedure

After explicit publication permission:

1. review and commit only the prepared v0.11.0 scope;
2. create the real `v0.11.0` tag on that commit;
3. rerun strict security audit with `-ExpectedTag "v0.11.0"`;
4. regenerate and verify the source package against the real tag and commit;
5. push the reviewed branch and tag;
6. confirm GitHub Actions, including required Gitleaks, succeeds;
7. create or verify the Japanese GitHub Release notes.
