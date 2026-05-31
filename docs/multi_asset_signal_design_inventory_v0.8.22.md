# v0.8.22 Multi-Asset Signal Design Inventory

## Purpose

This note inventories future evaluation axes for gold, bonds, and cash/wait
candidates. It is design-only. It does not add new scores, change displayed
candidate logic, or affect final decisions.

## Current foundation

v0.8.21 added a display-only section for four roles:

- equity: growth candidate
- gold: defensive candidate
- bond: diversification candidate
- cash: wait option

The section already carries these boundaries:

- `affects_final_action: False`
- `affects_buy_readiness_score: False`

v0.8.22 keeps those boundaries unchanged.

## Available data surfaces

Current configured or derived surfaces include:

| Area | Primary symbols | Fallback or related symbols | Current role |
| --- | --- | --- | --- |
| Gold ETF | `GLD` | `IAU` | defensive display candidate |
| Gold commodity | `GC=F` | `GLD`, `IAU` | inflation / defensive context |
| Aggregate bonds | `AGG` | `BND` | bond display candidate |
| Inflation-linked bonds | `TIP` | `SCHP` | inflation-sensitive bond context |
| Credit bonds | `LQD`, `HYG` | none configured | credit monitor context |
| Cash / wait | `CASH` display row | no market ticker | wait-state explanation |

These are sufficient for a future design discussion, but not enough to justify a
single shared cross-asset readiness score.

## Gold evaluation-axis inventory

Gold should remain separate from equity buy readiness. Candidate future axes:

- dollar pressure: use dollar-index context when available;
- inflation pressure: compare gold behavior with inflation monitor signals;
- real-rate proxy: use nominal-rate and inflation context only as a proxy unless
  a dedicated real-rate input is later added;
- drawdown regime: check whether gold is acting as a defensive asset while
  equity risk is elevated;
- momentum / trend: reuse existing asset comparison metrics such as 12-week
  momentum, volatility, and drawdown;
- yen impact: flag that Japanese investors also face FX movement.

Do not treat gold strength as a buy signal for equities. Do not label it as
safe or guaranteed defensive behavior.

## Bond evaluation-axis inventory

Bonds should be evaluated as rate-sensitive and credit-sensitive candidates.
Candidate future axes:

- rate direction: use Treasury-rate movement and rate warning context;
- duration sensitivity: separate long-duration candidates from aggregate or
  short-duration candidates before any score is created;
- credit stress: distinguish `LQD` / `HYG` style credit context from Treasury or
  aggregate bond context;
- volatility: use MOVE/risk-line context as a bond-market stress check;
- inflation linkage: keep `TIP`-style inflation-linked exposure separate from
  nominal aggregate bonds;
- yen impact: flag foreign-asset currency exposure.

Do not merge credit-risk and duration-risk behavior into one unexplained score.
Do not imply that bonds are automatically safer than equities.

## Cash / wait evaluation-axis inventory

Cash/wait is a state explanation, not an investment candidate score. Candidate
future axes:

- data reliability: stronger wait language when data is insufficient;
- risk-line stage: wait can be emphasized in danger-line states;
- blocker severity: wait can explain hard blockers without changing
  `final_action`;
- opportunity context: mention that waiting can avoid forced allocation, while
  also acknowledging opportunity cost;
- missing candidate data: use wait as a fallback display row when asset data is
  unavailable.

Cash/wait should not be framed as a guaranteed safe choice or as automated
allocation advice.

## Shared design constraints

Future gold, bond, and cash/wait diagnostics must remain separate from:

- `final_action`
- active/proposed threshold JSON
- `reliability_policy`
- buy window / candidate thresholds
- `buy_readiness_score`
- buy blocker logic
- buy decision card logic

Any later score must define its own role, range, inputs, missing-data behavior,
and non-advice wording before implementation.

## Non-advice wording

Keep wording in the current style:

> これは買い推奨ではなく、現在の市場状態を資産クラス別に整理したものです。外貨建て資産は為替の影響を受けます。

Avoid:

- 買うべき
- 今が買い
- 安全
- 利益が出る
- 確実
- 推奨銘柄

## Future implementation gates

Before adding gold or bond scoring, require:

- a documented objective for the score;
- a fixture covering missing data and sample fallback;
- a fixture covering normal, caution, and high-stress conditions;
- proof that `final_action` and threshold behavior are unchanged;
- separate display labels that do not resemble investment advice;
- targeted tests for no mixing with equity buy readiness.

## v0.8.22 non-goals

v0.8.22 does not:

- add a gold score;
- add a bond score;
- add a cash score;
- change report UI;
- change `final_action`;
- change threshold JSON;
- change reliability policy;
- change buy readiness, blocker, or decision-card logic;
- change CI, scripts, dependencies, generated reports, cache, or release
  archives.
