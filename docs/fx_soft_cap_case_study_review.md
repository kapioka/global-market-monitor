# fx_soft_cap case study review

`fx_soft_cap` is diagnostic-only. It does not change current `final_action`.

## Purpose

`fx_soft_cap` shows cases where FX moderate/headwind would keep a market signal visible as `buy_candidate` instead of fully collapsing it to `watch`.

## Use

```powershell
python -m project.fx_soft_cap_case_study
```

Outputs:

- `project/reports/fx_soft_cap_case_study.json`
- `project/reports/fx_soft_cap_case_study.md`

## Reading

- `overblocked_by_current`: current policy may have been too strict.
- `correctly_blocked`: current policy likely avoided a weak outcome.
- `promising_candidate`: partial positive evidence, but not enough for adoption.
- `inconclusive`: future return data is insufficient.

Adoption decision remains `hold` until future return, excess return, and drawdown evidence is available.

## Adoption Criteria

- 13w or 26w future data exists for enough cases.
- `buy_candidate` conversion does not worsen excess return.
- Worst max drawdown does not worsen.
- False candidate cases do not increase materially.
- The rule improves explainability versus current policy.
