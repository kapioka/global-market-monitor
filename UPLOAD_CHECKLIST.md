# GitHub Upload Checklist

Use this checklist before uploading this directory to GitHub as `v0.6.0`.

## Include

- `README.md`
- `RELEASE_NOTES_v0.6.0.md`
- earlier `RELEASE_NOTES_v*.md` files already published in the existing repository
- `.gitignore`
- `run_main.bat`
- `pytest.ini`
- `sitecustomize.py`
- `project/*.py`
- `project/config.yaml`
- `project/requirements.txt`
- `project/build_distribution.ps1`
- `project/tests/*.py`
- `project/risk_line_thresholds_active.json`
- `project/risk_line_thresholds_proposed.json`
- `project/risk_line_thresholds_schema.md`
- `scripts/*.ps1`

## Exclude

- `.git/`
- `archive/`
- `release/`
- `project/reports/`
- `project/cache/`
- `project/logs/`
- `project/.runtime/`
- `project/sample_output/`
- `docs/visual-evidence/`
- `.test_tmp*/`
- local handoff notes
- screenshots
- hardcoded local launcher files such as `起動_main.bat`

## Final Commands

For a fresh local verification repository, from inside this directory:

```powershell
git init
git add .
git status --short
git commit -m "Release v0.6.0"
```

For the existing GitHub repository:

```powershell
git remote add origin https://github.com/kapioka/global-market-monitor.git
git branch -M main
git push -u origin main
git tag v0.6.0
git push origin v0.6.0
```

Do not push until `SECURITY_REVIEW.md` still matches the actual contents.
