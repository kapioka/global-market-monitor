# HTML Artifact Inventory v0.8.11

This inventory accompanies the display-only buy-readiness gauge fix. It is a
read-only classification of HTML outputs currently present in the workspace.
No HTML output is deleted or committed as part of v0.8.11.

## Evidence

- `git ls-files "*.html"` reports zero tracked HTML files.
- `.gitignore` excludes `project/reports/`, `project/reports_old_before_v070/`,
  `project/sample_output/`, `project/test_output_history/`, `.tmp/`, and
  `.pytest_tmp/`.
- `README.md` names the operational generated report surfaces:
  `project/reports/report.html`, `project/reports/supplement_dashboard.html`,
  and `project/reports/history_dashboard.html`.
- `project/report_generator.py` writes latest and historical report HTML plus
  optional sample output; `project/history_dashboard.py` links back to
  `report.html`.

## Classification

| Classification | Observed location | HTML files present | Rationale | v0.8.11 action |
| --- | --- | ---: | --- | --- |
| linked | `project/reports/` | 86 | Runtime output area containing report surfaces documented in `README.md`; current reports are user-facing generated outputs. | Keep ignored; do not commit or delete. |
| generated | `project/reports/history/` within the count above | included | Historical runtime output produced by report generation. | Keep ignored; do not commit or delete. |
| sample | `project/sample_output/` | 2 | Optional generated sample output written by report flow and referenced by tests. | Keep ignored; do not commit or delete. |
| generated | `project/test_output_history/` | 5 | Test-created report and sample outputs referenced by `test_report_history.py`. | Keep ignored; do not commit or delete. |
| stale candidate | `project/reports_old_before_v070/` | 71 | Preserved pre-v0.7.0 generated report tree; not a current README runtime surface. | Review under a separate cleanup goal before any deletion. |
| ignore candidate | `.tmp/` | 13 at inventory baseline | Temporary HTML from v0.8.2-v0.8.4 UI smoke and snapshot QA. v0.8.11 validation adds further ignored temporary score and viewport QA pages in `.tmp/v0811_report_ui/`. | Leave untracked; cleanup only under a separate goal if needed. |
| ignore candidate | `.pytest_tmp/` | 1 | Temporary test-generated dashboard HTML. Already ignored. | Leave untracked; cleanup only under a separate goal if needed. |
| remove candidate | none confirmed | 0 | No file is safe to designate for deletion without a separate retention review. | No deletion. |

## Boundary

- HTML output remains generated or temporary data, not source-controlled input.
- v0.8.11 changes only report display code, tests, and documentation.
- Readiness-score calculation, final-action behavior, buy-decision logic,
  thresholds, and reliability policy are outside this inventory and unchanged.
- Any deletion, ignore-rule adjustment, or archival action requires a separate
  approved goal.
