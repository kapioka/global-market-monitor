# GitHub Upload Checklist

Use this checklist for the authorized v0.11.0 publication to `kapioka/global-market-monitor`.

## Before Permission

- Confirm all intended source and documentation changes.
- Run focused tests, the full repository validation contract, dependency audit, and secret/privacy scans.
- Confirm protected decision surfaces have no diff.
- Validate a source-only package in an isolated tagged rehearsal repository.
- Do not push, create a tag in the real repository, or create a GitHub Release.

## Included

- Application source, public configuration, tests, and dependency inputs
- `README.md`, `CHANGELOG.md`, `RELEASE_NOTES_v0.11.0.md`
- `LICENSE`, security review, package description, and publish checklist
- GitHub Actions and public validation/release scripts

## Excluded

- generated reports and local market data
- cache, logs, SQLite databases, runtime state, and manual data
- release archives and temporary output
- local-only screenshots, absolute workstation paths, and handoff notes
- credentials, keys, certificates, `.env`, and secret-adjacent artifacts

## Validation Commands

Run from the repository root:

```powershell
git status --short
git diff --check
python -m pytest
python -m ruff check .
python -m black --check .
python -m mypy .
.\scripts\audit_python_dependencies.ps1 -Python "python"
.\scripts\security_audit.ps1 -Python "python" -ExpectedTag "" -Strict
python scripts\create_release_package.py --dry-run
```

The final tag-specific package check is performed only after publication permission:

```powershell
git tag v0.11.0
.\scripts\security_audit.ps1 -Python "python" -ExpectedTag "v0.11.0" -Strict
python scripts\create_release_package.py
python scripts\verify_release_package.py --latest-dir release --expected-tag v0.11.0 --expected-commit <commit>
```

## Authorization Gate

Do not commit, tag, push, or create a GitHub Release solely because this checklist passes. Confirm the exact diff and wait for the user's explicit publication permission. After permission, publish only the reviewed v0.11.0 scope.
