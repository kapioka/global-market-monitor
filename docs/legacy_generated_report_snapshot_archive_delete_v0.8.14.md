# Legacy Generated Report Snapshot Archive And Delete v0.8.14

## Purpose

v0.8.14 applies the `archive then delete` decision documented in v0.8.13 to
the ignored legacy generated-output snapshot at
`project/reports_old_before_v070/`. The operation preserves a local archive
before deleting only that legacy source directory.

## Archived Target

- Deleted source target: `project/reports_old_before_v070/`
- Git tracked state before deletion: untracked.
- Ignore state before deletion: excluded by `.gitignore:27`.
- Scope verified before archive: 257 files, 22,036,802 bytes (21.016 MiB).

Pre-archive extension counts:

| Extension | Files |
| --- | ---: |
| `.json` | 83 |
| `.md` | 78 |
| `.html` | 71 |
| `.png` | 24 |
| `.csv` | 1 |
| Total | 257 |

## Archive Result

Archive created on `2026-05-26 18:53:27 +09:00`.

| Item | Value |
| --- | --- |
| Local archive path | `local_archives/reports_old_before_v070_v0.8.14_20260526-185327.zip` |
| Archive file count | 257 entries |
| Archive size | 9,760,292 bytes (9.308 MiB) |
| SHA256 | `25F73FA7450DBDA7B0C0CF2003942C896939474FDB6909A3168BAD38820A79CB` |
| Entry path boundary | Every file begins with `project/reports_old_before_v070/` |
| Git handling | The archive file is ignored by the existing `.gitignore` `*.zip` rule and is not committed. |
| Release handling | The archive is local-only and is not attached to a GitHub Release. |

No `.gitignore` change was needed. The existing `*.zip` rule prevents this
local archive artifact from entering Git status or a commit.

## Delete Result

Deletion was executed only after verifying the archive entry count and SHA256.

| Check | Result |
| --- | --- |
| `project/reports_old_before_v070/` after deletion | Does not exist |
| Deleted scope | Only `project/reports_old_before_v070/` |
| Tracked-file deletion | None, because the source tree was ignored and untracked |

## Preserved Out-Of-Scope Directories

The following paths were explicitly checked after deletion and remain present:

- `project/reports/`
- `project/reports/history/`
- `project/sample_output/`
- `project/test_output_history/`
- `.tmp/`
- `.pytest_tmp/`
- `release/`

No cleanup action was applied to those paths.

## Restore Procedure

Restoration is local-only and should be performed only if the legacy evidence
is needed again:

1. Locate
   `local_archives/reports_old_before_v070_v0.8.14_20260526-185327.zip`.
2. Verify its SHA256 is
   `25F73FA7450DBDA7B0C0CF2003942C896939474FDB6909A3168BAD38820A79CB`.
3. Extract the zip at the repository root so that it recreates
   `project/reports_old_before_v070/`.
4. Confirm the restored directory is still ignored and untracked.
5. If the restored output is used for any comparison, rerun the applicable
   smoke test and validation checks before relying on it.

## Git And Release Boundary

- The deletion changes no tracked generated artifact because the removed tree
  was never tracked.
- The commit for this goal records only this operational result document.
- The local archive zip must not be staged, pushed, packaged as a release zip,
  or uploaded to a GitHub Release.
- No GitHub Release is created and no push is performed in v0.8.14.

## Non-Changes

- No change to current report output, history output, or sample output.
- No `.gitignore` change.
- No production-code or test change.
- No CI, security-script, dependency, decision-logic, threshold JSON,
  reliability-policy, final-action, or readiness-score calculation change.
