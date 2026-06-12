# Hindenburg Omen manual input

Hindenburg Omen is supplemental and display-only. It does not affect `final_action`, buy readiness, or main risk.

## Supported modes

- automatic built-in providers: experimental and may fail safely.
- configured static CSV URL: supported.
- local manual CSV: supported.
- manual daily input: supported.
- converter utility: supported.
- previous confirmed value preservation: supported.
- no-data and insufficient-history states are not `点灯なし`.

User-facing acquisition and CSV preparation guide: `docs/hindenburg_omen_data_acquisition.md`

## CSV template

Template: `project/manual_sources/hindenburg_breadth_template.csv`

The rows in the template are examples only. They contain `EXAMPLE_DO_NOT_IMPORT` in `source_note`, and the importer rejects those rows as production observations.

Blank template: `project/manual_sources/hindenburg_breadth_blank_template.csv`

Default completed CSV path: `project/manual_sources/hindenburg_breadth.csv`

Mandatory fields:

- `date`
- `new_highs`
- `new_lows`
- `advancers`
- `decliners`

Optional fields:

- `total_issues`
- `nyse_index`
- `index_50d_ago`
- `mcclellan_oscillator`
- `source_note`

Internally derivable:

- `mcclellan_oscillator` can be derived after 39 valid `advancers` / `decliners` records are available.

Required only for a specific calculation method:

- `nyse_index` plus `index_50d_ago`, or enough `nyse_index` history, is needed for the uptrend criterion.

## Create a blank CSV template

```powershell
python -m project.hindenburg_manual create-template --output project/manual_sources/hindenburg_breadth.csv
```

Use `--overwrite` only when replacing an existing output file intentionally.

## Normalize a user-created CSV

```powershell
python -m project.hindenburg_manual normalize-csv --input path/to/source.csv --output project/manual_sources/hindenburg_breadth.csv
```

The converter accepts common Japanese and English headers such as `日付`, `新52週高値`, `値上がり銘柄数`, `date`, `new_highs`, and `advancers`, then writes the canonical app CSV format.

## Manual daily input

Use the local CLI:

```powershell
python -m project.hindenburg_manual daily-input --date 2026-01-02 --new-highs 80 --new-lows 75 --advancers 1200 --decliners 1200 --total-issues 2600 --nyse-index 10000 --index-50d-ago 9800 --source-note manual-confirmed
```

## Reset local state

This resets only the local Hindenburg Omen SQLite state and creates a backup when a database exists. It does not delete manual CSV files or generated reports.

```powershell
python -m project.hindenburg_manual reset-local-state --confirm "Hindenburg Omenのローカル状態を再初期化"
```
