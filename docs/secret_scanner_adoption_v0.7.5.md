# Secret Scanner Adoption Decision

v0.7.5 records how this project should treat Gitleaks and TruffleHog during GitHub publish preparation.

This work is unrelated to investment decision logic. It does not change `final_action`, active/proposed thresholds, `reliability_policy`, `buy_window`, `buy_candidate`, `fx_soft_cap`, or regime-aware policy behavior.

## Purpose

- Reduce the risk of publishing secrets, private local config, or credential-adjacent files.
- Clarify how Gitleaks and TruffleHog fit beside the existing security audit.
- Start with local optional scanner use instead of required CI enforcement.
- Define release stop conditions for verified or high-confidence secret findings.

## Current Secret Scan Stack

The current release workflow already includes:

- `scripts/security_audit.ps1`
- `detect-secrets`
- `pip-audit`
- fallback grep scans for secret-like patterns
- generated/cache tracked-file checks
- release package forbidden-entry checks
- `docs/github_publish_readiness_checklist.md`

Gitleaks and TruffleHog remain optional workstation tools in v0.7.5. `security_audit.ps1` already records whether they are available and does not fail only because they are missing.

## Scanner Comparison

| Area | Gitleaks | TruffleHog |
|---|---|---|
| Main use | Fast secret scanning for Git history and working trees | Broad secret scanning with stronger verification-oriented workflows |
| Detection targets | Git history, directories, common credential patterns | Git repositories, filesystems, and other sources depending on configuration |
| Adoption cost | Lower; good first optional scanner | Higher; scan scope and finding review need more design |
| Windows local use | Suitable for release workstation checks | Suitable, but runtime and output review may be heavier |
| GitHub Actions fit | Good candidate for optional CI later | Good candidate after scope and noise behavior are reviewed |
| False positive handling | Needs review before allowlisting | Needs review; verified findings are especially important |
| v0.7.5 status | Preferred optional scanner | Candidate scanner |

Decision:

- Gitleaks: adopt as the preferred optional scanner.
- TruffleHog: document as a candidate scanner.
- Required CI enforcement: defer beyond v0.7.5.

## Local Optional Commands

Check the installed tool help before relying on exact arguments. CLI names and subcommands can differ by version.

Gitleaks examples:

```powershell
gitleaks version
gitleaks detect --source . --verbose --redact
# If your installed version recommends the git subcommand:
gitleaks git --redact
```

TruffleHog examples:

```powershell
trufflehog --version
trufflehog filesystem . --no-update --only-verified
# For broader review, run without --only-verified and manually review findings.
trufflehog filesystem . --no-update
```

Operational notes:

- Missing tools are warnings or optional-tool notes in v0.7.5.
- A verified secret finding stops public release.
- A high-confidence secret finding stops public release.
- An unverified finding requires manual review before release.
- Do not immediately add allowlist entries for false positives.
- If allowlisting is justified, record the reason, target, and recurrence prevention in docs or audit notes.

## Release Stop Conditions

Stop release when any of these are true:

- Verified secret finding.
- High-confidence secret finding.
- `.env` or secret-adjacent file is included.
- Private local config is included.
- generated reports/cache contain credential-like values.
- release package contains a secret candidate.
- scanner finding cannot be explained.

Continue only after the finding is removed, rotated, or documented as a reviewed false positive with a narrow rationale.

## CI Position

v0.7.5 does not add required CI enforcement for Gitleaks or TruffleHog.

Future CI work should start as optional and non-blocking, for example:

- Record scanner output in the workflow log or summary.
- Use `continue-on-error: true` while noise is characterized.
- Keep `scripts/security_audit.ps1` as the primary release-readiness gate.
- Do not add branch-protection requirements until false positive handling is clear.

## Not In v0.7.5

- Required Gitleaks or TruffleHog CI.
- Mandatory pre-commit hooks.
- Destructive full-history secret rewrites.
- Casual allowlist expansion.
- Decision-logic changes.
- Threshold changes.
- Automated trading features.
