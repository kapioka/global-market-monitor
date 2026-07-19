# Repository Safety Rules

## Decision Boundaries

- Treat `final_action`, `reliability_policy`, threshold JSON, and buy-window / buy-candidate policy as protected. Do not change or loosen them unless the user explicitly reopens that exact scope.
- Keep `risk_engine_v2.mode=shadow`, `promotion_allowed=False`, and `policy_status=diagnostic_only_not_promoted` unless the user explicitly authorizes promotion work.
- Keep supplemental diagnostics and Japan-resident context separate from production decision logic, with explicit no-impact guarantees where applicable.

## Data And Completion

- Treat explicitly requested local data sources as first-class inputs. Verify their existence and provenance early, and fail fast when a requested path is missing.
- For diagnostic repair, continue through implementation, validation, semantic artifact parsing, protected-surface verification, and final evidence generation. File existence alone is not validation.
- When pausing a risky multi-phase task, update the existing checkpoint with completed commits, dirty or untracked state, remaining constraints, and the exact restart point.

## Proportional Validation

- Make validation proportional to the change risk and affected surface. For routine changes, default to the smallest focused tests and checks that directly cover the changed files and behavior.
- Documentation-only changes normally require diff and reference checks, not code tests, unless they alter executable documentation, generated artifacts, a release deliverable, or a declared validation contract.
- Do not automatically run the full test suite, every static-analysis tool, every smoke test, or a separate broad re-review after each routine change.
- Escalate beyond focused validation when concrete evidence requires it, including when:
  - a protected decision boundary in this file may be affected;
  - the task is a diagnostic repair that requires the completion evidence defined above;
  - schemas, dependencies, shared contracts, generated artifacts, or cross-module behavior change;
  - focused validation fails, is inconclusive, or reveals wider impact;
  - tag, push, GitHub Release, or comparable publication work invokes the release requirements below; or
  - the user explicitly requests broader or full validation.
- Plan one focused post-change validation pass by default. After a fix prompted by that pass, rerun only the failed or directly affected checks unless an escalation condition applies.
- Keep successful validation output compact. Report commands and summarized results without repeatedly rereading or reproducing full logs.
- Do not use child agents solely to duplicate routine post-change review. Use them only for genuinely independent work whose expected value exceeds coordination and context cost.
- Report completion precisely as implemented, focused-validation-passed, or full-validation-passed. Do not imply a broader evidence level than was actually run.
- This section controls validation breadth for routine work. It does not weaken the diagnostic-repair completion rule above, the protected decision boundaries, or the release and privacy requirements below.

## Release And Privacy

- Before tag, push, or GitHub Release work, inventory the worktree and protected surfaces, run the repository validation contract, and perform privacy/secrets checks.
- Similar versioned publication requests include Japanese changelog/release-note updates and verification of the real GitHub Release, not only local edits or a local tag.
- Keep generated, cache, runtime, diagnostic, and secret-adjacent artifacts out of tracked release source unless explicitly requested.
