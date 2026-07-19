# risk_engine_v2 current state

Last updated: 2026-07-13

Status: canonical source of truth

This is the only maintained design, completion, evidence, resume, and remaining
work document for risk_engine_v2. Earlier goal, phase, checkpoint, repair,
regeneration, and backlog documents were consolidated into this file and
removed. Future work must update this file instead of creating another dated
risk_engine_v2 progress document.

## Current decision boundary

risk_engine_v2 remains a diagnostic shadow engine.

- `risk_engine_v2.mode=shadow`
- `promotion_allowed=False`
- `policy_status=diagnostic_only_not_promoted`
- diagnostic artifacts must declare `affects_final_action=False`
- do not change `final_action`, production `buy_readiness_score`,
  `reliability_policy`, threshold JSON, or buy-window / buy-candidate policy
- official FRED series are coverage and provenance evidence unless separately
  validated stage thresholds are approved
- HYG/LQD remains the validated live credit-stage proxy
- gold is corroborative only and never an independent domain vote
- Hindenburg Omen remains separate from production decisions

Frozen protected hashes:

| File | SHA256 |
| --- | --- |
| `project/config.yaml` | `814F2DA2B4A031503A4DCE8C2FB444A55442890849FC85F7AD997DD78D875FC3` |
| `project/risk_line_thresholds_active.json` | `7277ABC57F5B0D6AFF28B9B9CCB4E983180637B8B15E9323F4EF6C72F5437FAE` |
| `project/risk_line_thresholds_proposed.json` | `1D067D3341087F0375AC717FBE8E885E641E2C9F28A3FF3B00CE70A3640D3200` |
| `project/spot_signal.py` | `6EB7F5082D325EB166FCEAC5CACBD9571D4C58F56E66F5942A640FBC1D647221` |
| `project/buy_readiness_score.py` | `53B356FDC5A475E2B2D0630A8EAA0DBA7C19DF5D3A26B9FE5C8DD1802EBA524D` |

## Operating acceptance contract

The redesign objective was to add an evidence-backed risk system with explicit
data contracts, point-in-time features, independent domain scoring, official
credit/rates/funding evidence, persistence, historical replay, and report
integration while preserving production decisions.

The acceptance contract remains:

- use 5/20/60-session as-of returns without silent zero substitution
- expose observation date, source, frequency, price type, freshness, quality,
  eligibility, and limitations for risk-relevant series
- prevent stale or asynchronous observations from creating combined signals
- count independent domains instead of correlated raw indicators
- distinguish inflation-rate stress from recession/flight-to-quality stress
- distinguish oil inflation shock from oil demand-collapse pressure
- apply cadence-aware persistence and hysteresis
- keep replay point-in-time and no-lookahead
- evaluate both historical stress episodes and quiet periods
- report missing coverage and fallback use instead of fabricating evidence
- preserve old report payload compatibility where practical
- keep active thresholds unchanged when coverage or acceptance is insufficient

Historical event coverage includes 2008, 2011, 2015-2016, 2018 Q4, 2020 Q1,
2022, and 2023 banking stress where source coverage permits. Replay evidence
tracks stage timing, future returns, drawdowns, event coverage, false and late
signals, quiet-period alerts, data coverage, and fallback use.

## Consolidated implementation history

### Foundation and shadow engine

| Work | Commit or checkpoint | Result |
| --- | --- | --- |
| Preflight and baseline | `0cbc882`, `69e223c` | Baseline and Phase 1 contracts frozen |
| Point-in-time feature contract | `5d53307` | As-of features, metadata, freshness and quality contract added |
| Shadow config and official FRED inputs | `f743898`, `fafbde0` | Shadow mode and official-series acquisition added |
| Independent domain engine | `27148e7` | Equity, volatility, credit, rates, funding and commodity domains added |
| Persistence and hysteresis | `291e60d` | Shadow state persistence added |
| Oil directionality | pre-V2 repair sequence | Inflation and demand-collapse directions separated |
| Shadow replay and outcomes | pre-V2 repair sequence | Diagnostic replay, forward outcomes and reconstructed history added |
| Episode review | pre-V2 repair sequence | False, late, protective and over-warning episodes classified |

### Strict V2 repair phases

| Phase | Commit | Result |
| --- | --- | --- |
| Repair baseline | `51a3bec` | Protected surfaces and known replay defects frozen |
| Replay cadence repair | `4ccb89e` | Canonical weekly cadence and full requested period restored |
| Episode review repair | `d1d33d2` | Episode ownership and outcome classification corrected |
| Global stage policy | `3d8cd09` | Independent-domain global policy and caps enforced |
| Cadence-aware persistence | `86baacd` | Calendar-gap false resets removed |
| Shadow contract | `bab6f4b` | Diagnostic-only contract enforced on generated artifacts |
| Promotion gate | Phase 7 implementation, now tracked | Minimum evidence, holdout and manual approval gate wired into review |

### Event-first and evidence-integrity repair

The event-first sequence was completed through commits `8dd25b5`, `b09a2b7`,
`7883070`, `cf58164`, `38f48bd`, and `43f0463`.

Completed behavior:

- event policy uses fixed split dates `2024-03-15` and `2025-05-23`
- canonical weekly record IDs are retained and resolved back from events
- unrecovered material drawdowns keep ownership through the latest observation
- right-censoring remains separate from event ownership
- holdout and root-cause diagnostics consume canonical weekly records
- retention reconciliation detects field, date, quality and provenance loss
- production invariance compares protected production-like fields
- holdout primary coverage is audited week by week and series by series

Holdout evidence used for measurement repair remains diagnostic-used evidence.
It must not be represented as a fresh untouched promotion holdout after model
behavior changes.

### Canonical official-series repair

The canonical local store is
`project/reports/risk_engine_v2_official_series.csv`.

Source-selection precedence is:

1. explicit `--official-series-csv`
2. `RISK_ENGINE_V2_OFFICIAL_SERIES_CSV`
3. optional `risk_engine_v2.official_series_csv`
4. repository default canonical store

Missing, unreadable, or schema-invalid selected stores fail before replay
evaluation and before canonical output writes. Provenance includes requested and
resolved path, selection origin, SHA256, row count, required-series presence,
series inventory, date range, duplicate count, and vintage status.

The July 3 refreshed store had:

- SHA256: `ad969e56bf2c3072bd986a3cf77e62b977c4ea19c23bf6db4da0d5ac24f4de0a`
- rows: `12924`
- range: `1971-01-08` to `2026-07-02`
- required series present: `7/7`
- warnings: `0`

Official series are used for strict-primary coverage and provenance. They are
not added to the production-like stress-monitor indicator map.

### July 3 data-quality completion

Commit `aea63e6` completed the current data-quality diagnostic repair:

- VIX and MOVE are exempt from the equity split-like 45 percent discontinuity
  rule because large moves are intrinsic to volatility indices
- other price series retain the discontinuity guard
- official OAS availability is distinguished from stage-scoring availability
- HYG/LQD remains the credit stage proxy
- production invariance permits append-only future weeks but rejects removed,
  inserted historical, or changed protected records

The cache-backed actual-data smoke passed without production-state persistence.
It confirmed VIX and MOVE as valid and stage-eligible, official OAS as
`diagnostic_coverage_only`, `risk_engine_v2.mode=shadow`, `final_action=watch`,
and production `buy_readiness_score=66`.

## Last fully regenerated diagnostic evidence

The latest complete canonical regeneration was produced on 2026-07-13 from
the fixed local market snapshot SHA256
`9dd48b4e982000506f47437148b65dbb093b749927c82131f612d1369813151e`:

- replay cases: `445`
- usable outcome cases: `441`
- primary strict cases: `107`
- primary partial cases: `338`
- primary unavailable cases: `0`
- replay episodes: `18`
- holdout weekly cases: `24`
- holdout evidence status: `ready`
- holdout status: `insufficient_holdout_episodes`
- performance status: `blocked_insufficient_matured_episodes`
- root-cause status: `no_target_episodes`
- retention reconciliation: `pass`, all required loss counts `0`
- controlled production invariance: `pass`, 445 weeks and all protected-field
  mismatch counts `0`
- holdout primary coverage: 24 strict weeks, no unavailable weeks
- holdout coverage audit: `no further coverage repair required`
- official-series regeneration comparison: `pass`, including all cross-artifact
  reconciliation gates
- artifact freshness: `current`, 7 of 7 fresh, consistent, no missing,
  malformed or policy-violation results
- promotion: `false`

The controlled before/after comparison used the same market snapshot. This is
required because comparing different snapshots previously produced misleading
invariance failures.

## Current local state

Verified on 2026-07-13:

- branch: `main`
- local branch: 44 commits ahead of `origin/main`
- source contract: `shadow_contract`
- artifact snapshot: `current`
- artifact consistency: `consistent`
- fresh diagnostic artifacts: `7`
- stale diagnostic artifacts: `0`
- missing or malformed diagnostic artifacts: `0`
- official-series maximum date: `2026-07-10`
- official-series rows: `12930`
- official-series SHA256:
  `bc8561f6453d6cf64b0a40627663305f261649235e4149879025c8e55de7213f`
- promotion gate: blocked at `18/30` episodes

The artifact-freshness preflight is integrated into the diagnostic-bundle
source manifest. It is read-only, uses explicit reports/config/as-of inputs,
does not return artifact bodies, and classifies source contract, artifact
freshness, missing/malformed state, policy consistency, replay/review counts,
and holdout/audit counts. Synthetic tests cover current, historical,
future-dated, incomplete, and inconsistent snapshots.

## Current implemented safeguards

The following behavior is implemented and is not a remaining target:

- artifact freshness is inspected read-only with explicit paths and as-of date
- official-series refresh retains older history and prefers valid fetched
  values on overlapping dates
- malformed or empty official-series inputs fail before canonical overwrite
- refresh metadata records rows, ranges, duplicate dates and overlap count
- reconstructed replay records market-snapshot path, SHA256, rows, columns and
  observation range before official-series merge
- production invariance requires matching baseline and candidate market-input
  SHA256 values
- regeneration comparison requires `same_market_snapshot=True`
- regeneration comparison supports normal loaded-to-loaded official-series
  comparisons and rejects missing or unloaded before/after stores
- regeneration comparison requires replay/review, holdout/audit and all
  coverage-loss reconciliation checks to pass
- freshness inspection includes the root-cause artifact
- freshness policy declarations fail closed when `policy_status`,
  `affects_final_action` or `promotion_allowed` is missing
- all of these paths remain diagnostic-only and preserve protected decisions

## Planned diagnostic presentation - Episode Chronicle

This is a future read-only presentation feature, not an unresolved Risk Engine
repair item. It presents each independent alert event as a continuing chapter
instead of dividing the product into annual editions.

### Product and visual direction

- reference mockup:
  `docs/visuals/risk_engine_v2_episode_chronicle_mockup.png`
- visual thesis: a calm market chronicle that combines the readability of a
  historical record with the precision of an evidence inspector
- content plan: episode index, recently opened tabs, selected-event chart,
  evidence sequence, evaluation and provenance
- interaction thesis: opening an episode creates a stable tab, selecting an
  evidence marker aligns the chart and explanation, and pending episodes extend
  in place as new weekly observations arrive
- years may be filters or labels but must never be the primary navigation or
  page boundary
- literal horizontal tabs are limited to recently opened episodes; the durable
  full collection uses a searchable and filterable episode index so the screen
  remains usable after hundreds of events

### Background generation boundary

The chronicle should be generated by a separate diagnostic post-processing
step after a complete evidence-chain regeneration. It must not be inserted into
production decision logic or made a prerequisite for `report.html`.

Inputs:

- `risk_engine_v2_reconstructed_replay.json` for canonical weekly records,
  market prices, stages and source provenance
- `risk_engine_v2_replay_review.json` for stable event IDs, classifications,
  maturity, event ownership and referenced weekly record IDs
- `risk_engine_v2_holdout_validation.json` for train, validation and holdout
  labels and performance-evidence status
- freshness and reconciliation results as publication gates

Proposed outputs:

- `risk_engine_v2_episode_chronicle.json`: normalized presentation view model
- `risk_engine_v2_episode_chronicle.html`: standalone read-only detail page

Generation rules:

- use stable `event_id` as the tab, bookmark and update identity
- update an active or pending episode in place; create a new chapter only for a
  new independent event ID
- derive the visible time window from each event's recorded lookback, peak or
  signal start, ownership end, recovery, outcome due date and latest observed
  date; do not impose a fixed year or one hard-coded duration
- retain the artifact's original policy version, split label and provenance so
  later policy revisions do not rewrite historical meaning
- fail closed when required inputs are missing, malformed, inconsistent or
  stale; never publish a mixed-generation chronicle
- write outputs atomically and allow only one generator for a reports directory
- declare `policy_status=diagnostic_only_not_promoted`,
  `affects_final_action=False` and `promotion_allowed=False`

### Selected episode screen

- episode index: date, type, peak stage, classification, maturity and split
- recent tabs: selected episode title plus active, pending or mature state
- primary chart: benchmark price and drawdown with candidate and confirmed
  stages on the same time axis
- event markers: signal start, warning, danger, material crossing, maximum
  drawdown, recovery and outcome due date when present
- evidence narrative: chronological explanation linked to the chart markers
- evaluation: protective, over-warning, late-confirmation, missed-risk,
  ambiguous or insufficient-outcome with plain-language meaning
- provenance inspector: official-series coverage, freshness, quality flags,
  source hashes and referenced weekly record IDs
- responsive behavior: episode index becomes a drawer on narrow screens, recent
  tabs remain horizontally scrollable, and evidence moves below the chart

The page is for explanation and historical review. It must not suggest that a
past classification changes the current `final_action`.

### Contract-first implementation plan

Status: implemented and focused-validation-passed. The standalone chronicle,
supplement launcher, generated presentation artifacts and semantic verifier are
available while remaining diagnostic-only.

The implementation is divided at a normalized presentation contract. The
backend owns evidence reconciliation and produces the contract; the standalone
page only renders that contract. The frontend must not reclassify an event,
recalculate its train, validation or holdout split, or infer maturity from chart
values. This boundary allows backend and frontend work to proceed independently
after the contract fixture is frozen.

#### Placement in the existing product

- keep `supplement_dashboard.html` as the entry page
- insert `5. 市場警戒年代記` immediately after
  `4. ヒンデンブルグオーメンのトリガー / 発動履歴`
- move `資産クラス / 候補証拠 詳細` and the following detailed sections to
  numbers 6 through 10; the existing `5つの要点` summary remains five items
- show a compact launch row with episode count, mature and pending counts,
  newest episode, generation time and freshness state
- open the full chronicle with `target="_blank"` and `rel="noopener"`; label the
  action explicitly as `市場警戒年代記を別窓で開く`
- when the chronicle is absent, stale or invalid, keep the supplement dashboard
  usable, disable the launch action and display the diagnostic reason
- never make chronicle generation a prerequisite for `report.html` or
  `supplement_dashboard.html`

#### Frozen backend-to-frontend contract

Create schema `risk_engine_v2.episode_chronicle.v1` before implementing either
side. A small deterministic fixture must cover one mature material-drawdown
event, one mature alert-only event, one pending event and one rejected-quality
case. The fixture is the frontend development input and the backend contract
test output.

Root fields:

| Field | Required meaning |
| --- | --- |
| `schema_version` | exact supported schema identifier |
| `generation_id` | hash-derived identity shared by JSON and HTML |
| `generated_at` | publication time, separate from evidence dates |
| `status` | `ready` only after every publication gate passes |
| `policy_status` | exactly `diagnostic_only_not_promoted` |
| `affects_final_action` | exactly `false` |
| `promotion_allowed` | exactly `false` |
| `source_fingerprint` | SHA-256 over source artifact names and content hashes |
| `source_artifacts` | path, artifact hash, schema, as-of range and gate status |
| `summary` | total, mature, pending, event-type and classification counts |
| `episodes` | normalized episode records ordered newest first |

Each `episodes[]` item must contain:

- identity: `event_id`, display title, event type, benchmark ID and source
- frozen evidence meaning: policy version and hash, split label,
  classification, maturity, performance-evaluable state and quality flags
- dates: anchor, ownership start and end, observed-through, outcome due,
  recovery and the derived display-window bounds
- chart series: date, benchmark price, drawdown, candidate stage, confirmed
  stage, coverage state and quality state; duplicate dates are prohibited
- markers: stable marker ID, date, kind, stage, value and narrative reference
- evaluation: machine status, Japanese plain-language label, summary metrics and
  evidence limitations
- narrative: ordered entries whose IDs link to chart markers
- provenance: referenced weekly record IDs and the relevant source hashes

Source ownership is fixed as follows:

| Source | Fields it owns |
| --- | --- |
| `risk_engine_v2_replay_review.json` | `event_id`, event semantics, event dates, classification, maturity, policy identity and weekly record references |
| `risk_engine_v2_reconstructed_replay.json` | benchmark price path, drawdown path, candidate and confirmed stages, coverage and quality evidence |
| `risk_engine_v2_holdout_validation.json` | frozen train, validation or holdout membership and performance-evidence status |
| freshness, retention and comparison results | publication eligibility and source-generation consistency |

The builder must join by stable `event_id` and referenced weekly record ID. It
must not use array position or display title as an identity. A missing join,
conflicting benchmark value, duplicate weekly record, unknown split, missing
diagnostic contract field or mixed source generation blocks publication.

#### Display-window and chart rules

For each event, calculate the first visible date from the earliest available
event anchor, weekly timeline start, peak, drawdown onset and first warning or
danger date. Calculate the last visible date from the latest available event
end, recovery, outcome due and observed-through date, then clamp it to the
available official benchmark series. A pending event ends at its latest observed
point. Include up to two source observations of context on each side when they
exist. This produces a stable event-centred window without imposing an annual
edition or a hard-coded duration.

Construct one canonical price point for each date from the reconstructed replay.
If overlapping drawdown paths disagree for the same benchmark date, fail closed
instead of selecting one silently. Derive chart drawdown from the event's
recorded peak and retain the original stored values used for evidence checks.

#### Background generation and publication lifecycle

Implement an idempotent diagnostic post-processing command rather than an
always-running daemon. It is invoked only after the canonical replay, review,
holdout, freshness and reconciliation chain has completed successfully.

1. Acquire one chronicle-generation lock scoped to the reports directory.
2. Load all required artifacts and validate their shadow contracts.
3. Require freshness, retention reconciliation and official-series comparison
   publication gates to pass for the same source generation.
4. Calculate `source_fingerprint`; exit as a successful no-op when the current
   ready artifact already has the same fingerprint.
5. Build the complete normalized view model in memory and validate it against
   the frozen schema and cross-artifact invariants.
6. Render JSON and standalone HTML into temporary files. Both outputs embed the
   same `generation_id`; the HTML contains all required data locally and makes
   no network request.
7. Parse the temporary JSON, run the HTML safety and completeness checks, then
   atomically replace the published files. Preserve the previous valid pair on
   any failure.
8. Release only this generator's lock and record a concise failure reason for
   the supplement launch state; never alter a production decision artifact.

Current upstream artifacts do not expose one shared evidence-chain generation
ID across replay, review and holdout. The implementation therefore does not
claim that stronger identity proof. It requires the comparison's exact replay
case hash to match the current replay, reconciles current review and holdout
counts and event ownership, validates the market-snapshot and cross-artifact
gates, fingerprints the exact bytes of every loaded input, and records
`source_generation_assurance.status=bounded_semantic_reconciliation`. Adding a
common upstream generation ID is optional provenance hardening, not a claim that
the current bounded assurance already provides it.

The first implementation should use these file boundaries:

- `project/risk_engine_v2_episode_chronicle.py`: source loading, validation,
  normalized view-model construction, fingerprinting and atomic publication
- `project/risk_engine_v2_episode_chronicle_renderer.py`: standalone HTML, CSS,
  SVG chart and local interaction rendering from the frozen view model
- `project/pipeline.py`: a compact, fail-closed chronicle summary loader for the
  supplement dashboard; it does not load the full episode collection
- `project/report_generator.py`: only the launch row, separate-window link,
  disabled state and detailed-section renumbering
- focused tests in new episode-chronicle test modules, plus direct extensions to
  `test_pipeline.py` and `test_report_generator.py`

#### Standalone page visual contract

The reference viewport is the 1680 by 945 mockup. Use a restrained archival
workspace rather than a dashboard card grid.

- visual thesis: dark-navy archival binding around a warm paper reading surface,
  with amber for warning, red for danger and green for recovery
- typography: at most two local system font stacks; a Japanese serif for the
  chronicle title and episode heading, and a Japanese sans serif for controls,
  numbers and evidence text; no web-font dependency
- desktop composition: 58-pixel top bar, approximately 320-pixel searchable
  episode index, flexible primary chart workspace and approximately 340-pixel
  evidence inspector, separated by quiet dividers rather than boxed cards
- centre hierarchy: recent-episode tabs, episode title and state badges,
  benchmark and date-range row, chart, legend, then the event narrative
- chart: accessible inline SVG with price line, drawdown and recovery regions,
  warning and danger phase bands, labelled event markers and a shared selected
  marker state with the narrative
- evidence inspector: lead time, maximum drawdown, official-series coverage,
  data quality, evaluation comment, high-level evidence and provenance
- years are search or filter facets only; the searchable episode index is the
  permanent navigation and recent tabs are capped at five open episodes
- desktop at 1200 pixels and above uses all three panes; from 768 to 1199 pixels
  the index becomes a drawer and the inspector moves below or beside the chart;
  below 768 pixels both secondary panes stack below the chart and tabs scroll
  horizontally
- interactions: a short episode-change cross-fade, synchronized marker focus
  between chart and narrative, and a restrained drawer transition; all are
  removed or reduced under `prefers-reduced-motion`
- controls, SVG marks and status colors must have text labels, keyboard focus,
  sufficient contrast and touch targets of at least 44 CSS pixels
- use embedded CSS and vanilla JavaScript only; no CDN, analytics, remote image,
  external font or fetch dependency is allowed for the local file page

#### Implementation sequence and handoff gates

Phase 0 - contract freeze:

- write the schema, source-to-field mapping and four-case contract fixture
- freeze the Japanese display vocabulary for event type, classification,
  maturity, split, coverage and quality status
- acceptance gate: backend builder tests and frontend fixture tests both accept
  the same file without compatibility adapters

Phase 1 - backend view model:

- implement joins, display-window calculation, canonical chart points, markers,
  narrative references, summary counts and provenance
- acceptance gate: deterministic output, stable IDs, no duplicate dates, exact
  source count reconciliation and fail-closed negative tests

Phase 2 - standalone renderer:

- reproduce the mock layout from only the frozen fixture, including desktop,
  narrow and mobile arrangements and empty or pending states
- acceptance gate: no backend import is required by renderer tests and no
  display value is hard-coded outside localization and style tokens

Phase 3 - background publication:

- add locking, source fingerprint no-op behavior, temporary validation, atomic
  replacement and preservation of the previous valid output
- acceptance gate: injected malformed, stale, interrupted and mixed-generation
  cases never replace the last valid chronicle

Phase 4 - supplement integration:

- add the compact loader and insert the separate-window launch row between the
  Hindenburg and asset/candidate sections, working around and preserving the
  current uncommitted supplement-dashboard redesign
- acceptance gate: ready, missing, stale and invalid states render correctly;
  the ready link opens a separate window with `noopener`; the main report still
  generates when chronicle data is unavailable

Phase 5 - evidence and visual verification:

- generate the chronicle from the current local canonical evidence chain and
  semantically parse the result
- capture local screenshots at 1680x945, a common laptop viewport and 390x844;
  compare hierarchy, pane proportions, marker alignment, overflow and legibility
  against the reference mockup
- verify all current events are represented once, pending events update under
  the same `event_id`, source hashes match, and the page emits no network request
- run the focused episode-chronicle, pipeline, report-generator, contract and
  production-invariance tests; broaden validation only if those checks expose
  shared-contract impact
- recheck that `final_action`, `reliability_policy`, threshold JSON and
  buy-window or buy-candidate policy are unchanged and that the three shadow
  declarations retain their protected values

Completion requires all six phase gates. A visually matching HTML file without
source reconciliation is incomplete, and a valid JSON artifact without the
desktop, narrow and mobile visual checks is also incomplete.

#### Implemented result

- backend view-model and publication command:
  `project/risk_engine_v2_episode_chronicle.py`
- standalone offline renderer:
  `project/risk_engine_v2_episode_chronicle_renderer.py`
- supplement summary loader and separate-window launch integration:
  `project/pipeline.py` and `project/report_generator.py`
- semantic verification includes
  `risk_engine_v2_episode_chronicle.json`
- generated local outputs:
  `project/reports/risk_engine_v2_episode_chronicle.json` and
  `project/reports/risk_engine_v2_episode_chronicle.html`
- current generated collection: 18 unique events, 16 mature, 2 pending and 4
  boundary-purged events retained with their original split ownership
- the 2020 material-drawdown episode displays from 2019-11-15 through
  2020-09-11; mature events stop at their event evidence boundary while pending
  events extend to the latest observed point
- the supplement launcher appears between Hindenburg history and asset or
  candidate evidence, and opens the standalone page in a separate window with
  `noopener`; the same action is also available in the supplement header in
  place of the ambiguous `補助確認` chip
- focused validation: 108 tests passed across the chronicle, renderer, pipeline,
  report generator, replay or review, holdout, freshness, retention,
  regeneration comparison, production invariance and artifact verifier surfaces
- semantic artifact verification: pass for all seven required Risk Engine V2
  JSON artifacts, including the chronicle
- runtime generation: first run generated 18 episodes; the immediately repeated
  run returned `no_change` for the same source fingerprint
- visual verification: the 1680x945 desktop and 390x844 mobile views rendered
  without console errors or network dependencies; search, recent tabs, marker
  narrative, responsive index and separate-window launcher were exercised
- all frozen protected file hashes remained unchanged after implementation

#### Saved plan - normal-run backend integration

Goal: make a normal `run_main.bat` execution generate or refresh the Episode
Chronicle without Codex, while keeping the diagnostic feature isolated from the
market report and all protected production-decision surfaces.

1. Add a small runtime coordinator around
   `run_risk_engine_v2_episode_chronicle`. It returns a bounded result with
   `generated`, `no_change`, `unavailable`, `busy` or `failed`, logs failures,
   and never deletes or overwrites the last valid publication on a failed run.
2. Invoke the coordinator once per normal process before report payloads are
   built: once in `run_with_backfill` for the whole backfill batch and once in
   `run_monitor` for a normal or scheduled run. Never invoke it for each
   backfill date.
3. Pass the resulting Chronicle summary explicitly into `build_report`. A
   successful result enables the separate-window launcher; a failed, busy or
   unavailable result disables the launcher for that report rather than
   presenting a retained older page as current.
4. Do not regenerate production Chronicle artifacts in `--sample-only` or
   `--actual-smoke`. Those modes receive an explicit non-publishable summary and
   must not mutate the production report directory.
5. Reuse the existing fingerprint no-op, freshness reconciliation, shadow
   contract checks, generation lock, temporary validation, atomic pair replace
   and rollback behavior. Do not add retries or polling loops.
6. Add focused tests for first generation, `no_change`, one invocation across
   multi-day backfill, scheduled or normal monitor use, sample and smoke skips,
   unavailable or failed input, lock contention, retained-output protection and
   launcher disabling.
7. Validate through an injected-fetch `run_main.bat`-equivalent execution,
   semantic parsing of the generated JSON and HTML, artifact verification and
   protected-file hash comparison. Live acquisition, policy promotion and
   threshold changes are outside this plan.

Acceptance requires normal execution to create the pair when validated source
artifacts are available, leave byte-identical output on `no_change`, keep the
ordinary market report running when Chronicle refresh fails, and preserve
`mode=shadow`, `policy_status=diagnostic_only_not_promoted`,
`affects_final_action=False` and `promotion_allowed=False`.

Implementation outcome:

- `project/risk_engine_v2_episode_chronicle_runtime.py` now isolates automatic
  refresh into the planned `generated`, `no_change`, `unavailable`, `busy` and
  `failed` outcomes and supplies only a validated ready summary to reports.
- `project/main.py` invokes refresh once in a normal monitor or scheduler run
  and once for an entire backfill batch. `--sample-only` and `--actual-smoke`
  explicitly skip production Chronicle generation.
- `project/pipeline.py` accepts the per-run summary override while retaining its
  existing disk loader as the compatibility default for other callers.
- a failed, unavailable or busy refresh leaves the previous publication files
  untouched but passes a non-publishable summary, so the supplement launcher is
  disabled rather than presenting retained output as current.
- an existing output pair must now pass the complete schema, shadow, freshness,
  generation-ID and offline-HTML checks before it can return `no_change`.
- focused integration and Risk Engine V2 validation passed 177 tests; Ruff,
  Black and Python compilation passed for all affected files.
- the current real evidence chain returned `no_change` with 18 episodes and the
  expected source fingerprint; semantic artifact verification passed all seven
  required JSON artifacts.
- protected configuration, threshold and decision-policy files have no working
  tree diff, and the generated Chronicle remains diagnostic-only with no final
  action or promotion impact.

#### Saved plan - dynamic episode context series

Goal: enrich each Episode Chronicle chart with the indicators that were
material to that specific historical warning state, without maintaining a
fixed display list and without using future outcome data to select them.

1. Keep ACWI as the permanent benchmark and select at most four additional
   series, for a maximum of five visible series. Do not fill unused slots when
   fewer indicators have valid point-in-time evidence.
2. Freeze selection once per episode at the latest reconstructed weekly case on
   or before the event anchor. Rank only stage-eligible, unsuppressed domains
   that actually contributed to the global candidate at that time. Exclude the
   equity domain when ACWI already represents that market direction.
3. Choose at most one series per independent domain. Prefer an explicitly used
   primary input, then an explicitly used fallback; use a declared contextual
   proxy only when the domain evidence has no raw series identifier, and label
   that distinction. Rank domains by candidate-stage severity, domain score,
   confidence and point-in-time abnormality, not by later episode outcome.
4. Read the market snapshot named by reconstructed replay provenance only after
   resolving it inside the workspace and verifying its SHA256 against the
   recorded snapshot hash. Add the verified snapshot bytes to the Chronicle
   source fingerprint so changed data cannot incorrectly return `no_change`.
5. Align each selected series to the Chronicle weekly dates using only same-day
   or bounded prior observations. Omit series with insufficient coverage or an
   invalid baseline. Record selection date, domain, rank, evidence status,
   source kind, quality, omissions and normalization method in the view model.
6. Render ACWI plus the selected series on one synchronized chart with the
   episode start indexed to 100. Keep ACWI visually dominant; use a restrained
   four-color secondary palette, a maximum-five legend, per-series visibility
   controls, shared date focus and raw values in the readout. Do not imply
   causality: label them as indicators that contributed to the warning decision
   or moved strongly in the recorded context.
7. Preserve a benchmark-only fallback for old fixtures or episodes without
   valid contextual inputs. The page must remain fully offline, keyboard
   accessible, responsive and readable with one through five series.
8. Add deterministic tests for per-episode selection differences, total-series
   cap, one-per-domain deduplication, point-in-time cutoff, quality or missing
   data omission, negative or zero baselines, snapshot path and SHA rejection,
   source-fingerprint participation, renderer toggles, raw-value readout and
   benchmark-only fallback.
9. Regenerate the real Chronicle, semantically verify every episode, confirm
   source provenance and repeat-run `no_change`, then rerun the focused Risk
   Engine, renderer, pipeline and artifact-verifier tests. Recheck all protected
   files and shadow declarations.

Acceptance requires deterministic episode-specific selection, no more than five
total series, no lookahead beyond the recorded selection date, verified snapshot
provenance, clear primary/fallback/proxy labels, usable normalized comparison and
no connection to `final_action`, threshold policy or production decisions.

Implementation outcome on 2026-07-19: completed and focused-validation-passed.
The generator now freezes each selection from the reconstructed case at or before
the event anchor, verifies the replay-named market snapshot path and SHA256, and
adds the snapshot hash to the Chronicle fingerprint. Selection eligibility,
ranking, coverage, baseline and scale use only observations available by that
cutoff; later values may extend an already selected line but cannot change which
line was selected. ACWI remains mandatory and the renderer defensively caps the
display at ACWI plus four independently selected context domains. The offline UI
adds keyboard-operable visibility controls, normalized comparison lines and a raw
value/date readout, while retaining a benchmark-only fallback.

The real 18-episode Chronicle regenerated with zero to four context series per
episode and then returned `no_change` on a repeat run. A semantic audit found no
episode above five total series, no non-ACWI benchmark and no selection date after
the event anchor. Artifact verification passed all seven required JSON artifacts;
focused Risk Engine, renderer, runtime, pipeline and report integration tests also
passed. The implementation remains read-only, diagnostic-only and disconnected
from protected production decisions.

## Repair status

### Resolved

- P1 evidence acceptance gates: resolved and validated on 2026-07-13
- P2 canonical evidence-chain refresh: resolved and validated on 2026-07-13
- all earlier repair, regeneration, data-quality and documentation issues:
  resolved or consolidated into the verified current implementation

### Only remaining issue - P3 mature evidence shortage

Priority: evidence-gated waiting item, after P2

The current episode count is 18 against the frozen minimum of 30. Twelve more
independent mature episodes are required before reassessment.

This is not permission to loosen event definitions, tune thresholds, or
promote the engine. If the count remains below 30, the correct result is to keep
waiting.

## Validation contract

Use validation proportional to the changed scope. A complete diagnostic repair
normally requires:

```powershell
python -m pytest -q
python -m ruff check .
python -m black --check .
python -m mypy project
python project\main.py --sample-only
python project\main.py --actual-smoke
```

Also parse regenerated JSON, verify protected hashes, run retention and
same-snapshot production invariance, inspect Git status, and run the privacy and
secret checks before any external handoff or publication.

For freshness-only work, use temporary synthetic fixtures and focused
validation; do not regenerate live artifacts merely to test the reader.

## Resume instructions

1. Read only this document for risk_engine_v2 project state.
2. Run `git status --short --branch` and inspect untracked work.
3. Re-verify protected hashes before any write task.
4. Continue from the first incomplete item in order: P1, P2, P3.
5. Update this document in place when status changes.
6. Do not create another dated risk_engine_v2 progress, checkpoint, repair, or
   backlog document.

Push, tag, release, and publication remain separate user-gated delivery work.
