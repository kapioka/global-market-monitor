# Package Manifest

This document describes the source-only public package for Global Market Monitor v0.11.0.

## Intended GitHub Target

- Repository: `kapioka/global-market-monitor`
- Version: `v0.11.0`
- Audience and license: unchanged; private, personal, non-commercial execution only

## Included Source

- Root documentation, license, changelog, and release notes
- `.github/workflows/ci.yml`
- Python application source and public configuration under `project/`
- Tests and fixed dependency inputs
- Public decision-policy and threshold review documentation
- Release, security-audit, and report-verification scripts under `scripts/`
- README screenshots under `docs/visuals/`

The archive generator records the exact included paths, commit, tags, and file count in the generated `PACKAGE_MANIFEST.json`.

## v0.11.0 Release Files

- `README.md`
- `CHANGELOG.md`
- `RELEASE_NOTES_v0.11.0.md`
- `SECURITY_REVIEW.md`
- `UPLOAD_CHECKLIST.md`
- `design-qa.md`
- `docs/github_publish_readiness_checklist.md`

## Excluded Local Data

- `.git/`
- `release/`, archives, and nested packages
- `project/reports/`, generated HTML, and generated Markdown reports
- `project/cache/`, `project/logs/`, and `project/.runtime/`
- SQLite databases and journal files
- manual market-data inputs
- local comparison screenshots and `docs/visual-evidence/`
- temporary directories, build output, Python caches, and test output
- `.env`, keys, certificates, secret files, and secret-adjacent logs

## Safety Boundaries

v0.11.0 does not change `final_action`, `reliability_policy`, active or proposed threshold JSON, buy-window / buy-candidate policy, or the Risk Engine V2 shadow-only status.

The source archive must be generated from tracked files and accepted by `scripts/verify_release_package.py` before publication.
