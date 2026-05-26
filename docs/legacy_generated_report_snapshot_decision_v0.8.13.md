# Legacy Generated Report Snapshot Decision v0.8.13

## Purpose

This Phase 1 review decides how to handle the ignored legacy generated-output
snapshot at `project/reports_old_before_v070/`. It supplies evidence for a
later approval decision. It does not delete, move, rename, or archive files.

## Target Directory

- Target: `project/reports_old_before_v070/`
- Intended role: preserved output snapshot from before the current report
  output tree was adopted.
- Phase 1 boundary: review only; any archive or deletion is a separate,
  explicitly approved action.

## Read-Only Evidence

Commands used:

- `Get-ChildItem project\reports_old_before_v070 -Recurse -Force`
- `Get-ChildItem project\reports_old_before_v070 -Recurse -File | Group-Object Extension`
- `git ls-files project/reports_old_before_v070`
- `git check-ignore -v project\reports_old_before_v070`
- `git grep -n "reports_old_before_v070"` and `git grep -n "reports_old"`
- Scoped `rg -n` searches across `README.md`, `docs`, `project`, `project/tests`,
  and `scripts`
- Read-only comparisons of file counts and sizes against `project/reports/`
  and `project/sample_output/`

## Size And Composition

Observed on 2026-05-26 JST:

| Measure | Result |
| --- | ---: |
| Files | 257 |
| Directories below target | 1 (`history/`) |
| Total size | 22,036,802 bytes (21.016 MiB) |
| Oldest modified file | `penalty_calibration.md` at `2026-03-20 18:18:31 JST` |
| Newest modified file | `action_validation_summary.csv` at `2026-05-15 07:39:48 JST` |
| Largest file | `dashboard.html`, 2,474,549 bytes |

| Extension | Count | Content role observed from names |
| --- | ---: | --- |
| `.json` | 83 | Report summaries, diagnostics, recalibration, threshold and history results |
| `.md` | 78 | Human-readable report and diagnostic outputs |
| `.html` | 71 | Dashboard/report surfaces and dated history pages |
| `.png` | 24 | Prior visual verification captures |
| `.csv` | 1 | Action validation summary export |

The snapshot is not merely old HTML. It contains prior diagnostic and visual
evidence alongside report pages.

## Tracking And Reference State

- Git tracked state: no tracked files were returned under the target.
- Ignore state: `.gitignore:27` excludes `project/reports_old_before_v070/`.
- README reference: none found for the legacy target.
- Source and test reference: none found for the legacy target.
- Script reference: none found for the legacy target.
- Documentation reference: the target is recorded only by the v0.8.11
  inventory and v0.8.12 cleanup review as a stale/remove candidate.

Current output paths have separate live roles:

| Path | Current evidence | Decision boundary |
| --- | --- | --- |
| `project/reports/` | Documented in README and used by source/report tooling | Keep; not part of a legacy cleanup action |
| `project/reports/history/` | Read by diagnostics and documented as report history | Keep; not part of a legacy cleanup action |
| `project/sample_output/` | Configured and asserted by tests | Keep; not part of a legacy cleanup action |
| `project/reports_old_before_v070/` | Ignored, with no runtime/test consumption found | Candidate for a separately approved archive/remove action |

## Retention Value

The directory has no observed current execution dependency, but it has local
historical value:

- It preserves pre-current report HTML and dashboard output for visual
  comparison.
- It includes dated history outputs and supporting JSON/Markdown evidence.
- It includes PNG captures showing earlier UI verification work.
- It includes generated threshold/recalibration artifacts that may be useful
  for explaining historical presentation or audit work, even though they are
  not current policy inputs.

Existing workspace cleanup documentation treats old report evidence and history
conservatively and recommends archive-first handling before destructive
cleanup. This snapshot matches that retention pattern.

## Deletion Risk

No runtime or test breakage is expected from removing this ignored legacy tree
based on the reference search. The practical risks are loss of local evidence:

- loss of visual before/after comparison material;
- loss of dated generated history not present in the current output tree;
- loss of old generated calibration/diagnostic evidence needed for later
  retrospective checks;
- accidental expansion of a cleanup command into current generated or sample
  output trees.

Because the tree is ignored and untracked, deletion would not be reversible
through Git.

## Archive Zip Option

No zip is created in v0.8.13 Phase 1.

If deletion is approved later, an optional local archive may be created first:

- Source directory: `project/reports_old_before_v070/` only.
- Archive purpose: preserve local historical evidence before removing the
  ignored working-directory copy.
- Archive location and handling must be approved before creation.
- The archive must remain untracked and must not be treated as a release zip or
  included in any package/push.
- Before handoff or external publication, run the required secret check and
  review its result.

## Explicit Removal Target If Approved

The only proposed removal target for a later Phase 2 is:

```text
project/reports_old_before_v070/
```

That target currently represents:

| Included subtree or files | Current count or scope |
| --- | --- |
| `history/` subtree | 201 files, including 67 HTML pages |
| Top-level generated outputs and visual captures | 56 files |
| Total deletion scope | 257 files, 21.016 MiB |

Explicitly excluded from any Phase 2 approval implied by this document:

- `project/reports/`
- `project/reports/history/`
- `project/sample_output/`
- `project/test_output_history/`
- `.tmp/` and `.pytest_tmp/`
- tracked docs, source, tests, scripts, thresholds, and release material

## Required Validation After Any Approved Deletion

A later Phase 2 must:

1. Reconfirm that only `project/reports_old_before_v070/` is targeted and
   remains ignored and untracked.
2. Reconfirm that README, docs, tests, source code, and scripts do not consume
   the legacy path.
3. Confirm whether a local archive is required, and create one only under
   explicit approval.
4. Delete only the approved target.
5. Confirm that current reports, report history, and sample output remain
   untouched.
6. Run `git status --short --ignored` to verify no required or tracked output
   was affected.
7. Run `git diff --check`, `python -m ruff check .`,
   `python -m black --check .`, `python -m mypy .`, and `python -m pytest`.
8. Run strict security audit at the then-current tag baseline and verify zero
   tracked generated-artifact hits.

## Recommended Decision

**Recommendation: `archive then delete`, only after explicit user approval.**

Reasoning:

- `delete` is operationally plausible because no current runtime, test, or
  README consumption was found.
- `keep` indefinitely is unnecessary for operation and retains 21.016 MiB of
  redundant local generated output.
- `archive then delete` respects the evidence value of dated reports, UI
  screenshots, and generated diagnostic material while removing stale working
  output after approval.
- `postpone` remains acceptable if the user does not want to authorize either
  archive creation or deletion.

## Phase 1 Non-Changes

- No deletion, move, rename, or zip creation.
- No `.gitignore` change.
- No production-code or test change.
- No CI, security-script, dependency, decision-logic, threshold JSON,
  reliability-policy, final-action, or readiness-score calculation change.
- No generated report, cache, temporary output, or release archive commit.
- No GitHub Release and no push.

Phase 2 requires explicit user approval after reviewing this decision record.
