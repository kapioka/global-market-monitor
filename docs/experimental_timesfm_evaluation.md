# experimental TimesFM evaluation

TimesFM diagnostic work was evaluated during v0.7.1 preparation, but it is not included in the v0.7.1 product surface.

Reasons:

- signal_quality: not_useful
- false_supportive_count: 11
- correctly_blocked special risk high rate: 0.0%
- added forecast diagnostics reduced explainability for v0.7.1
- final_action must remain based on active thresholds and reliability policy

TimesFM must not affect final_action, buy_candidate, buy_window, fx_soft_cap, or regime-aware candidates in v0.7.1. Future TimesFM work should happen on a separate branch as optional research only.

## v0.8.5 residual inventory

### Current conclusion

- TimesFM remains excluded from normal functionality.
- TimesFM does not affect `final_action`.
- TimesFM does not affect the beginner-facing buy decision UI.
- Existing references are retained as experimental evaluation and non-adoption records, plus negative verification and security audit controls.

### Read-only inventory results

The read-only inventory found tracked references in these locations only:

| Classification | References | Current purpose |
| --- | --- | --- |
| docs / user-facing statement | `README.md` | States that TimesFM is not part of normal functionality. |
| changelog / historical note | `RELEASE_NOTES_v0.7.1.md`, `RELEASE_NOTES_v0.7.2.md` | Records evaluation and continued exclusion. |
| docs / experimental record | `docs/experimental_timesfm_evaluation.md` | Keeps the evaluation result and this residual inventory. |
| docs / release and security record | `docs/github_publish_readiness_checklist.md`, `docs/release_operation_hardening_v0.7.3.md`, `docs/security_audit_v0.7.2.md` | Records exclusion and audit expectations. |
| tests | `project/tests/test_report_generator.py` | Confirms generated report text does not expose TimesFM. |
| security audit / allowlist-equivalent control | `scripts/security_audit.ps1` | Detects unexpected TimesFM references and prohibited dependency reintroduction. |

Searches for `times fm` and `time series foundation` found no tracked references.

### Dependency and execution-path confirmation

- `project/requirements.txt`, `project/requirements-dev.txt`, `project/requirements-lock.txt`, `pyproject.toml`, and `requirements-security.txt` contain no TimesFM runtime dependency.
- The dependency scan also found no `torch`, `jax`, `flax`, or `tensorflow` dependency introduced for this experimental layer.
- No TimesFM import path was found in project code.
- No TimesFM CLI option or configuration route was found.
- No normal report-generation or decision path was identified that would feed TimesFM output into `final_action` or the buy decision UI.

### Handling classification

| Handling | References | Rationale |
| --- | --- | --- |
| keep | `docs/experimental_timesfm_evaluation.md`, release notes, security audit record, README exclusion statement | These provide the non-adoption decision history and prevent misreading the feature as active. |
| keep | `project/tests/test_report_generator.py`, `scripts/security_audit.ps1` | These are negative verification and audit controls, not product execution paths. |
| rewrite | None required in v0.8.5 | Existing permitted references already describe exclusion rather than active usage. |
| remove candidate | Historical references only if a future documentation-retention decision removes obsolete evaluation material | Removal is not required for functionality and must not erase the current exclusion evidence without replacement. |
| investigate | Test and security audit references before any future deletion | They enforce absence and would need coordinated review if the historical references are removed. |

### Safe order for any future removal

1. Reconfirm that no import, dependency, CLI option, or configuration route exists.
2. Confirm tests that verify TimesFM non-exposure and decide whether equivalent negative coverage remains necessary.
3. Consolidate or replace documentation wording without implying active functionality.
4. Review security audit permitted-reference handling before removing or relocating historical references.
5. Re-run full lint, type, test, and strict security validation before recording a later release decision.

### Out of scope for v0.8.5

- No TimesFM code removal.
- No import, dependency, requirements, lock, test, or security audit change.
- No change to decision logic, thresholds, reliability policy, `final_action`, or readiness-score calculation.
- No generated report, cache, or release archive change.

## v0.8.6 reference policy and audit alignment

### Retention policy

- TimesFM remains an evaluated but non-adopted experimental layer, not normal functionality.
- It must not influence `final_action`, readiness-score calculation, or the beginner-facing buy decision UI.
- The existing references are retained for three bounded purposes: historical evaluation record, negative verification that reports do not expose it, and security-audit control against accidental reintroduction.
- Retention does not imply activation, support, or a plan to restore the experimental layer.

### Conditions for future removal

A later change may remove TimesFM references only when all of the following are true:

- Historical retention is no longer required, or an equivalent non-adoption record will remain available.
- The exclusion roles currently served by README, release notes, documentation, tests, and audit controls are either preserved or intentionally replaced.
- Any security-audit permitted-reference update is scoped, reviewed, and validated without weakening detection of normal-functionality reintroduction.
- Full lint, type, test, and strict security validation passes after the proposed removal.
- The removal reason can be recorded in a location accepted by the security-audit policy in effect at that time.

### Audit alignment policy

- The current strict security audit uses a bounded list of permitted TimesFM reference paths.
- Adding a new document that names TimesFM is blocked unless the audit policy is separately updated to recognize that location.
- Recording TimesFM directly in `CHANGELOG.md` is also incompatible with the current permitted-reference policy.
- Until that policy is intentionally revised, TimesFM evaluation, residual inventory, and retention/removal policy notes are consolidated in this already permitted document.
- If separate documentation or changelog traceability becomes necessary, the audit permitted-reference design must be reviewed in a separate goal before any new reference is committed.

### Candidate next steps

- Read-only impact review of whether every retained historical reference remains useful.
- Separate design review of audit permitted-reference maintenance and change-record traceability.
- Minimal documentation cleanup where wording could be clearer without adding new reference locations.
- Removal decision only after the retention and audit requirements above can be satisfied.
- Continued emphasis on non-adoption and normal-functionality exclusion instead of complete historical erasure.

### Out of scope for v0.8.6

- No new TimesFM reference document and no `CHANGELOG.md` update.
- No TimesFM code removal, import, dependency, requirements, lock, test, or security audit change.
- No change to decision logic, thresholds, reliability policy, `final_action`, or readiness-score calculation.
- No generated report, cache, or release archive change.
