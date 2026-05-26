# HTML Artifact Cleanup Review v0.8.12

## Purpose

v0.8.12 is a read-only review of ignored HTML and adjacent generated output
trees. It determines which artifacts may be considered for cleanup in a later
goal. This review does not delete, move, rename, or reclassify any file or
directory.

## Evidence Collected

Commands used for the review:

- `git ls-files "*.html"` and `git ls-files "**/*.html"`
- `git status --short --ignored`
- `git check-ignore -v` for report, sample, legacy, and temporary output trees
- `git grep -n` and scoped `rg -n` for README, docs, tests, source, and script references
- read-only file count, extension count, timestamp, and shared-output hash checks

Observed tracking and ignore state:

| Path | Tracked HTML | Ignore source | Current role |
| --- | ---: | --- | --- |
| `project/reports/` | 0 | `.gitignore:25` | Current runtime-generated reports |
| `project/reports/history/` | 0 | inherited from `.gitignore:25` | Runtime report history and downstream diagnostic input |
| `project/reports_old_before_v070/` | 0 | `.gitignore:27` | Preserved legacy generated-output snapshot |
| `project/sample_output/` | 0 | `.gitignore:26` | Generated sample output exercised by tests |
| `.tmp/` | 0 | `.gitignore:5` | Temporary validation output |
| `.pytest_tmp/` | 0 | `.gitignore:4` | Temporary pytest output |

Both tracked HTML checks returned zero files. No ignored HTML directory needs an
ignore-rule change for the current policy.

## HTML Inventory Result

Read-only counts observed on 2026-05-26:

| Path | Total files | HTML files | Classification | Evidence and decision |
| --- | ---: | ---: | --- | --- |
| `project/reports/` | 357 | 86 | generated / keep | README and `project/README.md` identify current report surfaces; source modules read/write the history area. Keep ignored as live generated output. |
| `project/sample_output/` | 3 | 2 | sample / keep | Configured by `project/config.yaml`, written by `project/report_generator.py`, and asserted by `project/tests/test_report_history.py`. |
| `project/test_output_history/` | 8 | 5 | generated / keep | Test sandbox output created by report history tests; already ignored. |
| `project/reports_old_before_v070/` | 257 | 71 | stale candidate / remove candidate | Ignored legacy snapshot with no current README, source, or test use discovered. Keep in place for v0.8.12; eligible for explicit deletion review later. |
| `.tmp/` | 171 | 22 | ignore candidate / keep ignored | Temporary audits and UI QA outputs; already excluded and may be cleared only under a separate cleanup goal. |
| `.pytest_tmp/` | 102 | 1 | ignore candidate / keep ignored | Pytest temporary output; already excluded and not a source artifact. |

## `project/reports_old_before_v070/` Review

### Status

- Git tracked: no; the directory is ignored by `.gitignore:27`.
- README reference: none found.
- Source or test execution reference: none found.
- Document reference: only the v0.8.11 HTML inventory and this review record it as a legacy candidate.
- Relevance to current runtime: no evidence that current report generation or current tests read it.

### Contents

The directory is not an HTML-only folder. It contains a legacy generated-output
snapshot:

| Extension | Files |
| --- | ---: |
| `.html` | 71 |
| `.json` | 83 |
| `.md` | 78 |
| `.png` | 24 |
| `.csv` | 1 |
| Total | 257 |

- Top-level files: 56.
- `history/` files: 201, including 67 HTML history pages.
- Observed timestamp range: `2026-03-20T18:18:31` through `2026-05-15T07:39:48` JST.
- It contains `report.html`, `dashboard.html`, `supplement_dashboard.html`, and `report_summary.json`.
- Matching current output filenames exist under `project/reports/`, but their
  hashes differ and the current versions were regenerated on `2026-05-26`.

### Cleanup Assessment

`project/reports_old_before_v070/` is a **stale candidate** because it is an
ignored legacy snapshot with no current consumption path found. It is also a
**remove candidate** for a later goal, because removing it would be a
filesystem cleanup operation that needs an explicit deletion list and a
separate validation run.

Deleting it now would discard historical generated-output evidence. A later
cleanup decision must first decide whether the snapshot has retention value
outside the repository, such as manual visual comparison or local operational
history.

## Classification

| Category | Items | v0.8.12 disposition |
| --- | --- | --- |
| keep | `project/reports/`, `project/reports/history/` | Preserve as ignored current runtime output. |
| generated | `project/reports/`, `project/reports/history/`, `project/test_output_history/` | Do not track or alter. |
| sample | `project/sample_output/` | Preserve because configuration and tests use it. |
| stale candidate | `project/reports_old_before_v070/` | Preserve during this review; consider separately. |
| ignore candidate | `.tmp/`, `.pytest_tmp/` | No change required because they are already ignored. |
| remove candidate | `project/reports_old_before_v070/`, subject to retention decision | No deletion in v0.8.12. |
| investigate | Retention need for local legacy snapshot and temporary audit artifacts | Resolve only before a deletion goal. |

## Safety Conditions For A Future Deletion Goal

A later deletion goal may proceed only when all of the following are confirmed:

1. The exact target files or directory tree are listed before deletion.
2. The targets are not Git-tracked and remain outside release/package inputs.
3. README, docs, tests, source code, and scripts do not depend on the targets.
4. `project/sample_output/` and current `project/reports/` output are excluded
   from deletion unless separately approved.
5. Any local retention requirement for legacy visual evidence or operational
   history is resolved or explicitly waived.
6. The cleanup does not require `.gitignore`, CI, scripts, dependencies,
   decision logic, thresholds, or reliability-policy changes.
7. Before and after cleanup, the standard lint, type, test, and strict security
   audit checks pass with no generated artifacts becoming tracked.

## Next-Goal Procedure If Deletion Is Approved

1. Re-check clean worktree, current tag, ignored state, and zero tracked HTML.
2. Produce the explicit deletion target list and count files by extension.
3. Re-check references for each target tree.
4. Confirm retention disposition for `project/reports_old_before_v070/`.
5. Delete only the approved ignored targets.
6. Run `git status --short --ignored` and verify no source or required sample
   artifacts were removed.
7. Run full validation and strict security audit.
8. Record the deletion result in docs and, only if appropriate, CHANGELOG.

## v0.8.12 Non-Changes

- No HTML or directory deletion.
- No file move or rename.
- No `.gitignore` change.
- No production-code or test change.
- No CI, security-script, dependency, decision-logic, threshold JSON,
  reliability-policy, final-action, or readiness-score calculation change.
- No generated report, cache, temporary output, or release archive commit.
