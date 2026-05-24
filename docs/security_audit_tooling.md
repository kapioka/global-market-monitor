# Pre-publish Security Audit Tooling

This repository uses `scripts/security_audit.ps1` to make release security checks repeatable before a public push.

The audit is a release hygiene check. It does not push, rewrite history, change threshold JSON, or change trading decision logic.

## Tools

- `gitleaks`: scans the Git history and working tree for likely secrets when the binary is available.
- `detect-secrets`: scans tracked and untracked source files and writes a temporary baseline under `.tmp/security/`.
- `pip-audit`: checks Python requirements for known vulnerabilities.
- `trufflehog`: optional extra Git secret scan when the binary is available.

Python-based security tools are kept in `requirements-security.txt`. They are not part of the application runtime requirements.

## Setup

```powershell
python -m pip install -r requirements-security.txt
```

You can also let the audit script install Python-based tools:

```powershell
.\scripts\security_audit.ps1 -InstallTools
```

`gitleaks` and `trufflehog` are external binaries. If they are not installed, the script records them as missing or skipped and still runs the fallback checks.

## Usage

Normal run:

```powershell
.\scripts\security_audit.ps1
```

Strict run before publishing:

```powershell
.\scripts\security_audit.ps1 -Strict
```

Skip dependency vulnerability checks when the environment is not suitable:

```powershell
.\scripts\security_audit.ps1 -Strict -SkipDependencyAudit
```

## Outputs

Audit outputs are written to `.tmp/security/`, including:

- `security_audit_summary.json`
- `security_audit_summary.md`
- scanner-specific output files

The `.tmp/security/` directory is generated output and must not be committed.

## Interpreting Results

- `publish_readiness: pass`: no release-blocking findings were found.
- `publish_readiness: fail`: at least one release blocker was found. Do not push.
- Missing optional tools are recorded as warnings, not blockers.
- `pip check` findings from packages outside this project's requirements should be reviewed, but are not automatically release blockers.
- Real secrets, private keys, credential paths, tracked generated artifacts, personal commit metadata, or threshold JSON diffs are blockers.

False positives should be documented in the audit report. Do not add broad allowlists that could hide future real findings.

## Optional CI Scanner Findings

The GitHub Actions `gitleaks-optional` job is an observation signal until a later release explicitly makes it required. For v0.7.10, review its findings during release preparation and keep `scripts/security_audit.ps1 -Strict` as the primary local publish-readiness gate.

Record local scanner availability and local scan results in the security audit outputs. Record CI finding triage in sanitized release review notes or issue/PR discussion. Do not copy raw secrets or secret-adjacent log excerpts into public documentation.

Do not add Gitleaks findings to `PACKAGE_MANIFEST.json` in v0.7.10. The release manifest describes package contents, commit/tag metadata, and forbidden-entry exclusions; scanner findings depend on CI context and manual triage state.

Stop release if Gitleaks reports a verified, high-confidence, or unexplained finding, even though the optional CI job remains non-blocking.

## Push Checklist

Before pushing a release:

```powershell
.\scripts\security_audit.ps1 -Strict
git status --short
git tag --points-at HEAD
```

Push only if the audit reports `publish_readiness: pass`, the working tree is clean, and the release tag points at the intended commit.
