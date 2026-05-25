# Feature Library Missing-Value Policy Review v0.8.9

v0.8.9 records the missing-value behavior currently used by the risk-line
feature library. This version is documentation and regression-coverage work;
it does not change feature calculation, threshold selection, or decision
behavior.

## Scope

The review covers `project/risk_line_feature_library.py`, where missing input
values can reach percentage-change calculations used by:

- `roc_1w`, `roc_2w`, `roc_4w`, and `roc_8w`
- rolling z-score derivatives of those rate-of-change columns
- `adverse_persistence_4` and `adverse_persistence_8`

The feature frames are consumed by risk-line backtesting and reality-check
reporting. A change to missing-value handling can therefore change model
candidate values or supporting diagnostic evidence, even without modifying a
threshold JSON file.

## Observed Current Behavior

For the synthetic series `[100.0, NA, 110.0, 105.0, NA, 120.0]`, current
Pandas default behavior produces:

```text
[NA, 0.0, 0.10, -0.0454545, 0.0, 0.1428571]
```

This behavior emits `FutureWarning` because implicit forward filling in
`pct_change()` is deprecated.

Building a `SPY` feature frame from the same series currently produces the
same compatible `roc_1w` sequence and emits warnings from more than one
percentage-change call path. The warning is therefore not limited to
`_adverse_persistence()`: the `roc_*` feature creation path also depends on
the current implicit behavior when internal missing values are present.

## Policy Alternatives

### A. Explicit current-compatible behavior

```python
series.ffill().pct_change(fill_method=None)
```

For the synthetic case above, this equals the current output exactly:

```text
[NA, 0.0, 0.10, -0.0454545, 0.0, 0.1428571]
```

This option makes forward filling deliberate and can remove the deprecation
warning without intentionally changing the present feature semantics.

### B. Strict missing-value propagation

```python
series.pct_change(fill_method=None)
```

For the same input, this produces:

```text
[NA, NA, NA, -0.0454545, NA, NA]
```

This option preserves missingness but changes rate-of-change and persistence
inputs. It may alter backtest candidates and reality-check diagnostics.

### C. Per-feature cleaning policy

A broader design could define separate preprocessing rules for rate-of-change,
persistence, and composite features. That would be a behavior-design change
and is outside v0.8.9.

## v0.8.9 Decision

- Keep the production feature implementation unchanged in this version.
- Record the current-compatible and strict alternatives with regression tests.
- Do not replace current calls directly with `pct_change(fill_method=None)`.
- Treat any future warning-removal implementation as a separate behavior
  preservation change requiring explicit validation.

## Safe Conditions for a Future Implementation

A later implementation may explicitly reproduce the current-compatible
behavior only when all of the following are true:

- both `roc_*` generation and adverse persistence handling are reviewed;
- tests prove compatible output for internal missing values;
- representative backtest and reality-check outputs are compared before and
  after the implementation;
- full lint, type, test, and security validation passes;
- threshold, reliability, and decision-policy files remain unchanged unless a
  separately approved goal reopens that scope.

## v0.8.10 Explicit Compatible Migration

v0.8.10 verified the explicit current-compatible form before changing
production feature calculation:

- `series.ffill().pct_change(fill_method=None)` matched the previous implicit
  default for no missing values, middle missing values, leading missing
  values, consecutive missing values, all-missing values, and nearly
  all-missing values.
- `series.pct_change(fill_method=None)` remained intentionally excluded
  because it differed for middle, consecutive, and nearly all-missing inputs.
- Synthetic missing-value feature-frame, backtest, and reality-check outputs
  were compared before and after the migration and remained identical.

Production feature generation now uses the explicit current-compatible form
for `roc_*` features and adverse-persistence input calculation. This removes
the deprecated implicit-fill warning without changing the selected
missing-value policy.

## Unchanged Surfaces

The policy review and explicit migration do not change:

- missing-value semantics;
- threshold JSON or risk-label definitions;
- reliability policy, final action, readiness score, or buy-decision logic;
- CI configuration, security scripts, or dependencies;
- generated reports, cache, or release archives.
