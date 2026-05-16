# Package Manifest

This package is a source-only public upload set for Global Market Monitor v0.7.0.

## Directory Layout

```text
.
├── README.md
├── SECURITY_REVIEW.md
├── UPLOAD_CHECKLIST.md
├── PACKAGE_MANIFEST.md
├── RELEASE_NOTES_v0.7.0.md
├── RELEASE_NOTES_v0.6.0.md
├── RELEASE_NOTES_v0.5.0.md
├── RELEASE_NOTES_v0.4.0.md
├── RELEASE_NOTES_v0.3.0.md
├── .gitignore
├── pytest.ini
├── run_main.bat
├── sitecustomize.py
├── project/
│   ├── *.py
│   ├── config.yaml
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── threshold_historical_replay.py
│   ├── threshold_metadata.py
│   ├── threshold_candidate_policy.py
│   ├── threshold_certainty.py
│   ├── threshold_decision_policy.py
│   ├── threshold_rule_identity.py
│   ├── threshold_rule_evidence.py
│   ├── threshold_rule_certification.py
│   ├── threshold_rule_certification_report.py
│   ├── build_distribution.ps1
│   ├── tests/
│   ├── risk_line_thresholds_active.json
│   ├── risk_line_thresholds_proposed.json
│   └── risk_line_thresholds_schema.md
└── scripts/
    ├── render_supplement_dashboard.ps1
    └── verify_supplement_dashboard.ps1
```

## Rationale

The package includes enough source to run the app and regenerate the report locally. It excludes private or machine-specific output so GitHub receives only the application source and public configuration.

## Threshold Review Docs

- `docs/threshold_decision_policy.md`
- `docs/threshold_historical_replay_review.md`
- `docs/threshold_overblocking_diagnostics.md`
- `docs/threshold_candidate_v2_review.md`
- `docs/risk_line_threshold_proposal_review.md`
- `docs/validation_limits.md`

## v0.7.0 Threshold Certification Files

- `RELEASE_NOTES_v0.7.0.md`
- `project/threshold_metadata.py`
- `project/threshold_candidate_policy.py`
- `project/threshold_certainty.py`
- `project/threshold_decision_policy.py`
- `project/threshold_historical_replay.py`
- `project/threshold_rule_identity.py`
- `project/threshold_rule_evidence.py`
- `project/threshold_rule_certification.py`
- `project/threshold_rule_certification_report.py`

## Intended GitHub Target

- Repository: `kapioka/global-market-monitor`
- Version: `v0.7.0`

## Excluded Internal Notes

The public package excludes local-only continuation notes, worktree progress
notes, visual rebuild handoffs, and dashboard redesign drafts. Those files may
contain machine-specific paths or operational context that is not needed to run
the public source package.
