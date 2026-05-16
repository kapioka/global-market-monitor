# Security Review For Public Upload

Review date: 2026-05-16
Target version: v0.7.0

Scope:

- Package reviewed: `global-market-monitor-v0.7.0-github-source-*.zip`
- Goal: prepare a source-only GitHub upload package containing the working app and excluding local/private artifacts.

## Threat Model

Primary assets:

- local runtime output under `project/reports`, `project/cache`, and `project/logs`
- generated market summaries and downloaded public market data
- user's local filesystem privacy

Trust boundaries:

- public market data fetched from external sources
- local config values in `project/config.yaml`
- generated local HTML reports opened in a browser
- GitHub public repository boundary

Security invariants:

- no credentials, tokens, private keys, or local account paths should be published
- generated reports, logs, cache, screenshots, archives, and local runtime artifacts should not be published
- launcher scripts should not depend on a user-specific absolute path
- generated HTML must be local report output, not a privileged web service

## Included Surface

- Python source files under `project/`
- public ticker/config definitions
- threshold JSON definitions used by the app
- dependency list
- helper scripts for local report rendering and visual checks
- v0.7.0 threshold certification and rule-level certification source files
- GitHub-oriented README and upload checklist

## Excluded Surface

- `.git`
- `archive`
- `release`
- `project/reports`
- `project/cache`
- `project/logs`
- `project/.runtime`
- `project/sample_output`
- `docs/visual-evidence`
- temporary screenshot directories
- hardcoded local Python launcher `起動_main.bat`
- local handoff and environment-followup notes
- next-version worktree progress notes
- local visual rebuild handoff notes
- internal dashboard redesign plans

## Scan Summary

The package was scanned for common secret and personal-information patterns, including:

- `api_key`, `secret`, `token`, `password`, `credential`
- private-key headers
- GitHub token prefixes
- Slack token prefixes
- local user path fragments
- obvious Japanese personal-information labels

Findings requiring removal:

- None in the prepared public package at the time this file was created.

Known non-secret strings:

- Public market ticker symbols such as `XLK`, `XLE`, `^MOVE`, and `USDJPY=X`.
- Public package names in `requirements.txt`.
- `check_secrets.ps1` reported medium findings for ordinary code identifiers containing the word `key`, including sort-key callbacks; these were reviewed as false positives, not credentials.
- Targeted token scans can also match internal JavaScript placeholder fields named `token` in the generated dashboard template; these are fixed text markers, not authentication tokens.

## Validation Notes

This package intentionally omits generated reports and caches. Running the app will recreate runtime output locally.

Validation performed:

- `python -m compileall -q project`
- `python project/main.py --sample-only`
- warning-mode secret scan against the prepared public package
- targeted `rg` scan for API keys, tokens, private-key headers, local user paths, and obvious personal-information labels
- generated runtime output was removed again before packaging

The package should be re-scanned after any file is added manually.
