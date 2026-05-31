# v0.8.23 Multi-Asset Signal Fixture and Missing-Data Policy

## Purpose

This checkpoint fixes fixture and missing-data expectations for future
gold, bond, and cash/wait signal modeling. It prepares future implementation
without adding new scores or changing final decisions.

## Deliverables

- Fixture: `project/tests/fixtures/multi_asset_signal_cases_v0.8.23.json`
- Fixture schema guard: `project/tests/test_multi_asset_signal_fixtures.py`

The fixture is compact and synthetic. It does not contain raw market histories,
cache files, report HTML, API responses, local paths, or personal information.

## Covered cases

| Case | Expected status | Role | Missing-data rule |
| --- | --- | --- | --- |
| `gold_available` | `watch` | `defensive` | use available GLD/IAU/GC=F style context |
| `gold_missing` | `not_available` | `defensive` | do not create a fake gold candidate |
| `bond_available` | `watch` | `diversification` | use available AGG/BND/TIP/LQD/HYG style context |
| `bond_missing` | `not_available` | `diversification` | do not create a fake bond candidate |
| `cash_wait` | `wait` | `wait` | no market ticker required |
| `mixed_partial_data` | `informational` | `mixed_review` | partial data can inform text, not strong candidate status |

## Expected input fields

Future modeling may read these existing surfaces:

- `asset_compare`
- `inflation_monitor`
- `credit_monitor`
- `risk_lines`
- `data_reliability`
- `availability_map`
- configured ticker maps

Future implementation should keep the fixture fields close to display and
policy intent:

- `asset_class`
- `symbol`
- `display_name`
- `source_data_available`
- `expected_status`
- `expected_role`
- `expected_reason_category`
- `expected_caution_required`
- `expected_missing_data_representation`
- `must_not_affect_final_action`
- `must_not_affect_buy_readiness_score`

## Missing-data policy

Missing data must be represented directly.

- Missing gold or bond data must not create a fake candidate.
- Missing source data should use `not_available`, `informational`, or `wait`
  style handling.
- Partial data may support weak informational text, but not a strong candidate
  status.
- Caution text must remain when data is incomplete.
- Missing data must not lower or raise existing `buy_readiness_score`.
- Missing data must not change `final_action`.
- Missing data must not be converted into artificial confidence.

## Status vocabulary

The fixture reserves a small vocabulary for future implementation:

- `watch`: source data exists and the asset class can be reviewed;
- `informational`: partial data exists, but the case is not a candidate;
- `not_available`: expected source data is unavailable;
- `wait`: cash/wait explanation, not a scored candidate.

This vocabulary is not a scoring model.

## Reason categories

The fixture uses categories rather than formulas:

- `defensive_context`
- `rate_sensitive_context`
- `insufficient_data`
- `wait_context`
- `partial_data_context`

These categories are intended for future reason/caution text. They do not
drive `final_action`, thresholds, or equity buy readiness.

## Non-advice wording policy

Keep wording equivalent to:

> これは買い推奨ではなく、現在の市場状態を資産クラス別に整理したものです。外貨建て資産は為替の影響を受けます。

Avoid:

- 買うべき
- 今が買い
- 安全
- 利益が出る
- 確実
- 推奨銘柄

The fixture test checks that case payloads do not contain these expressions.

## Separation from equity buy readiness

Gold, bond, and cash/wait cases must remain separate from equity
`buy_readiness_score`.

- Gold can be a defensive or diversification review surface.
- Bonds can be rate-sensitive or credit-sensitive review surfaces.
- Cash/wait can explain waiting when inputs are incomplete or risk is elevated.
- None of these should be folded into the equity buy-readiness score without a
  separate, documented scoring design.

## v0.8.23 non-goals

v0.8.23 does not:

- implement a gold score;
- implement a bond score;
- implement a cash score;
- connect these cases to `final_action`;
- change `buy_readiness_score`;
- change threshold JSON;
- change reliability policy;
- change buy blocker or buy decision card logic;
- redesign report UI;
- add network fetching;
- add dependencies;
- update CI;
- push, tag, or create a GitHub Release.
