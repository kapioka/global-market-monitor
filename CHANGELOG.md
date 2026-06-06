# Changelog

## v0.8.60 - RC Final Polish

### Changed

- Suppressed suspicious domestic metric values at the domestic danger reason source so split/discontinuity-limited values are shown as non-adopted or reference-excluded instead of ordinary report metrics.
- Added Hindenburg Omen `as_of_date` and stale CSV handling so old manual breadth data cannot be shown as confidently active for the current date.
- Added basic Hindenburg manual CSV value validation for negative breadth counts, zero breadth totals, invalid dates, nonnumeric McClellan values, and impossible `total_issues` relationships.
- Made default diagnostic bundle output filenames follow the requested `--version`.

### Scope

- Kept `final_action`, production `buy_readiness_score`, Hindenburg decision/display-only boundary, decision-boundary experiment behavior, threshold JSON contents, reliability policy, buy blocker/card logic, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.59 - RC Metadata / Report Polish

### Changed

- Made diagnostic bundle review-question headings use the requested bundle version instead of a fixed older RC label.
- Adjusted report wording for suspicious domestic metrics so split/discontinuity-limited values are shown as non-adopted or reference-excluded while keeping the raw limitation visible.

### Scope

- Kept `final_action`, production `buy_readiness_score`, decision-boundary experiment behavior, threshold JSON contents, reliability policy, buy blocker/card logic, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.57 - Hindenburg Omen Display-Only Signal Monitor

### Added

- Added a display-only Hindenburg Omen monitor backed by an optional manual market breadth CSV.
- Added conservative criteria evaluation, trigger date history, and active-period summarization.
- Added report display for active, inactive, and manual-missing states using non-panic supplemental wording.

### Scope

- Kept `final_action`, production `buy_readiness_score`, decision-boundary experiment behavior, threshold JSON contents, reliability policy, buy blocker/card logic, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.55 - RC Semantics Polish

### Changed

- Split supplemental domestic context into domestic asset, FX, and domestic macro levels so integrated report labels do not mix asset risk with currency risk.
- Updated integrated FX semantics so EURJPY caution is reflected in the FX level while domestic asset level remains separate.
- Removed unavailable `GLD` rows from the domestic danger context; JPY gold is represented through `1540.T`, while USD gold remains in non-domestic candidate/report sections.
- Added raw versus clamped score delta fields to the disabled decision-boundary experiment.
- Renamed Japan-resident candidate display from `文脈スコア` to `確認材料スコア`.
- Included the diagnostic bundle builder, its test, and bundle docs in subsequent diagnostic zips.

### Scope

- Kept `final_action`, production `buy_readiness_score`, threshold JSON contents, reliability policy, buy blocker/card logic, risk labels, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.54 - Diagnostic Bundle Completeness Polish

### Changed

- Added a reproducible ChatGPT diagnostic bundle builder that includes explicit review seed files and transitive `project.*` Python imports.
- Added threshold JSON, indicators, scoring, asset comparison, and monitor dependencies to the review bundle scope without modifying those files.
- Added bundle tests for required review dependencies, excluded generated/private paths, and control-character-free `logic_review_questions.md`.

### Scope

- Kept `final_action`, production `buy_readiness_score`, threshold JSON contents, reliability policy, buy blocker/card logic, risk labels, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.53 - RC Logic Polish

### Changed

- Connected JPY gold price metrics from `1540.T` directly into the supplemental domestic danger context when candidate output does not carry that row.
- Split JPY gold proxy wording from USD-denominated gold reference wording for `1540.T`, `GLD`, and `GC=F`.
- Added domestic price discontinuity guarding so split-like or suspicious jumps become data limitations instead of risk signals.
- Split domestic drawdown fields into 12-week, 26-week, and full-period reference values while keeping short lookback drawdown as the active supplemental risk input.
- Adjusted Japan-resident integrated FX level mapping so a neutral USDJPY summary is not upgraded to caution only by generic moderate/review normalization.

### Scope

- Kept `final_action`, production `buy_readiness_score`, threshold JSON, reliability policy, buy blocker/card logic, risk labels, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.51 - Decision Boundary Experiment

### Changed

- Added a disabled-by-default `decision_boundary_experiment` payload that compares baseline `final_action` / `buy_readiness_score` against an experimental integrated-context score adjustment.
- Added markdown and standard HTML display for the baseline versus experimental comparison without writing back to the buy decision card.

### Scope

- Kept production `final_action`, production `buy_readiness_score`, threshold JSON, reliability policy, buy blocker/card logic, risk labels, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.50 - Report UX Rebuild for Risk Context

### Changed

- Added a standard HTML report hub that separates core decision output, supplemental risk context, global risk-line detail, data limitations, and source acquisition status.
- Kept Japan-resident integrated context visible as supplemental context while making data limitations and acquisition counts easier to distinguish from observed risk.

### Scope

- Kept `final_action`, `buy_readiness_score`, threshold JSON, reliability policy, buy blocker/card logic, risk labels, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.49 - Japan Resident Integrated Risk Context

### Changed

- Added a display-only Japan-resident integrated risk context that combines US/global risk lines, risk-line confidence audit, domestic danger context, FX context, rate context, and Japan macro data limitations.
- Added report display and tests for the integrated context, including DXY versus USDJPY/EURJPY role separation and explicit non-impact flags.

### Scope

- Kept `final_action`, `buy_readiness_score`, threshold JSON, reliability policy, buy blocker/card logic, risk labels, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.48 - Global Risk Logic Confidence Audit

### Changed

- Added a display-only global risk-line confidence audit for active threshold provenance, confidence buckets, and final-action isolation.
- Documented that `DX-Y.NYB` is the global dollar stress input while `USDJPY=X` / `EURJPY=X` remain Japan-resident FX context inputs.
- Added report and test coverage for fallback_review / low_precision / pass distinction and the composite risk score / trigger path relationship.

### Scope

- Kept threshold JSON, `final_action`, `buy_readiness_score`, reliability policy, buy blocker/card logic, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.47 - Domestic Danger Logic Rebuild

### Changed

- Rebuilt supplemental domestic danger context so observed domestic market metrics, not acquisition status alone, drive `normal` / `watch` / `caution` / `unavailable` display levels.
- Kept missing Japan-oriented sources as limitations or unavailable context instead of treating missing CPI, BOJ, JGB, JPY bond, Japan REIT, FX, or JPY gold data as caution signals.
- Added per-row metric/limitation display and documentation for the domestic danger context while keeping Public Equity Investing context workflow-supporting only.

### Scope

- Kept `final_action`, `buy_readiness_score`, threshold JSON, reliability policy, buy blocker/card logic, risk labels, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.46 - Domestic Market Metrics Layer

### Changed

- Added display-only domestic market metrics for Japan equity, JPY bond, Japan REIT, JPY gold proxy, and FX context series when acquired price data is available.
- Connected domestic metrics to Japan-resident multi-asset rows and domestic danger context so acquisition logs alone do not create watch/caution states.
- Added report display for useful domestic metrics and limitations while keeping missing data as a limitation rather than a risk signal.

### Scope

- Kept `final_action`, `buy_readiness_score`, threshold JSON, reliability policy, buy blocker/card logic, risk labels, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.45 - Domestic Data Wiring Fix

### Changed

- Wired optional Japan macro context into the normal report pipeline so local manual CPI/BOJ CSV inputs can reach Japan-resident multi-asset and domestic danger display sections without requiring live fetches.
- Added explicit report-payload injection coverage for MOF JGB, CPI, and BOJ macro context.
- Kept missing JGB/domestic-rate data neutral for domestic bond and Japan REIT display components instead of treating absence as a caution signal.

### Scope

- Kept `final_action`, `buy_readiness_score`, threshold JSON, reliability policy, buy blocker/card logic, CI, scripts, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.44 - Domestic Market Monitoring and Danger-Line Integration

### Changed

- Added a supplemental domestic danger-context payload for domestic stocks, JPY bonds, Japan REIT, JPY gold, FX, JGB yield, and CPI/BOJ fallback limitations.
- Integrated domestic/Japan-resident context into supplemental market monitoring, supplemental judgement, danger-line monitoring, and danger-line detail display without changing core danger-line thresholds.
- Added tests proving domestic danger context stays display-only and does not affect `final_action` or `buy_readiness_score`.

### Scope

- Kept `final_action`, `buy_readiness_score`, threshold JSON, reliability policy, buy blocker/card logic, CI, dependencies, generated reports, cache, manual source files, tags, GitHub Release, and push out of scope.

## v0.8.43 - Smoke and Buy Readiness Logic Audit

### Changed

- Added audit documentation for controlled smoke validation, numeric acquisition, and the observed `buy_readiness_score` of 40.
- Added regression tests showing the current watch + FX caution + score-shortfall case calculates 40 by design.
- Added coverage proving Japan-resident macro/context payloads remain display-only and do not feed equity `buy_readiness_score`.

### Scope

- Kept `final_action`, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, CI, scripts, dependencies, generated reports, cache, manual source files, release archives, tags, GitHub Release, and push out of scope.

## v0.8.42 - API-Key-Free Japan Macro Public File Resolver

### Changed

- Reoriented CPI and BOJ macro acquisition toward distribution-safe appId-free public/manual source files instead of normal-use API credentials.
- Added optional local manual CSV resolution for CPI and BOJ short-rate context under `project/manual_sources/` without creating or requiring runtime manual files.
- Kept e-Stat optional and disabled unless the user supplies `ESTAT_APP_ID`; missing appId does not trigger a network request.
- Documented manual source filenames, compact CSV column contracts, and fallback behavior.

### Scope

- Kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, CI, scripts, dependencies, generated reports, cache, manual source files, release archives, tags, GitHub Release, and push out of scope.

## v0.8.41 - Official Japan Macro Endpoint Discovery Fallback Registry

### Changed

- Added a two-level optional Japan official macro live strategy: robust first-party endpoints when available, otherwise source registry fallback entries.
- Switched the JGB live source to the MOF historical CSV endpoint and added parser support for its title-row/header shape.
- Added structured non-data fallback statuses for CPI missing `ESTAT_APP_ID`, unresolved e-Stat table mapping, and unresolved BOJ short-rate endpoint discovery.
- Kept fallback registry entries out of real macro observations so missing official macro data gives no score boost.

### Scope

- Kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.40 - Official Macro Live Source Resolver

### Changed

- Classified optional Japan macro live-once responses before parser execution so official HTML landing pages become structured `landing_page` failures instead of raw CSV tokenizer errors.
- Documented the live resolver endpoint limitation while keeping official macro fetching optional and non-blocking.

### Scope

- Kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.37-v0.8.38 - Official Japan Macro Adapter Implementation and Validation

### Added

- Added optional official Japan macro adapter contracts for JGB yield curve, Japan CPI/core CPI, and BOJ/call-rate domestic short-rate context.
- Added fixture-backed parser tests and a contract-only `--japan-macro-dry-run` path so official macro handling can be validated without making live official fetches mandatory.
- Wired official macro outputs into Japan-resident multi-asset context as display-only inputs for domestic rate and inflation components.

### Scope

- Kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.35-v0.8.36 - Japan Resident Sample Coverage and Fetch Safe Probe

### Added

- Added sample-only synthetic coverage for `2510.T`, `1343.T`, `1540.T`, `1321.T`, and `EURJPY=X` so Japan-resident context can be exercised without relying on live data.
- Added targeted tests confirming sample-only acquisition, JPY bond, Japan REIT, gold JPY proxy, Japanese equity, and FX context remain display-only and conservative.
- Ran a limited existing-path fetch probe for the five newly added tickers; each was handled by the existing yfinance path without introducing mandatory network behavior.

### Scope

- Kept JGB curve, Japan CPI, and BOJ official adapters deferred; kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.34 - Japan Resident Series Inventory and Config Wiring

### Added

- Documented the Japan-resident real-data series inventory, separating currently available FX/Japanese equity/foreign bond/USD gold inputs from deferred JGB curve, CPI, BOJ rate, and JPY-strength adapter work.
- Added optional config/ticker wiring for `EURJPY=X`, `1321.T`, `2510.T`, `1343.T`, and `1540.T` through the existing acquisition path.
- Updated candidate-layer recognition so configured domestic JPY bond, Japanese REIT, and domestic gold proxy series can feed display-only Japan-resident context when available.

### Scope

- Kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.30-v0.8.33 - Japan Resident Data Expansion Fast Track

### Added

- Added a display-only Japan-resident asset context inventory covering domestic JPY bonds, JGB yield curve context, USD/JPY FX context, Japanese equities, Japan inflation/rates, Japanese REIT, gold JPY proxy, foreign bonds, and cash/wait.
- Added conservative candidate-layer context fields for Japan-resident multi-asset rows without feeding them into `final_action` or `buy_readiness_score`.
- Added targeted tests for missing, failed, partial, sample-fallback, domestic JPY bond, Japanese equity, Japanese REIT, gold JPY proxy, foreign bond, and cash/wait context handling.

### Scope

- Kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.29 - Multi-Asset Real-Input Compatibility Hardening

### Changed

- Strengthened real-input compatibility coverage for GLD, GC=F, TIP, LQD, acquisition-log requested/used ticker mapping, availability overrides, and failed/partial acquisition statuses.
- Tightened candidate-layer fallback so failed or partial acquisition-log statuses do not create watch candidates.

### Scope

- Kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, pipeline behavior, report redesign, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.28 - Connect Multi-Asset Signals to Existing Real Data Inputs

### Changed

- Added a narrow candidate-layer adapter for existing acquisition-log style input so gold and bond candidates can use available local cache/report data when `asset_compare` or monitor rows are absent.
- Preserved conservative fallback behavior for unavailable, sample-fallback, missing, partial, and legacy-shaped multi-asset inputs.

### Scope

- Kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, pipeline behavior, report redesign, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.27 - Real-Data Shape Probe and Multi-Asset Report Display Adjustment

### Changed

- Probed existing local report/history output, sample-shaped candidate output, and v0.8.23 fixtures to confirm multi-asset rows can include unavailable gold/bond data, wait-state cash, and legacy rows without reason categories.
- Adjusted the existing multi-asset report section to show beginner-readable Japanese status and reason-category labels instead of raw internal values.

### Scope

- Kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, pipeline behavior, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.26 - Boundary Tests and Minimal Report Integration for Multi-Asset Signals

### Added

- Strengthened candidate-generation boundary coverage for gold, bond, cash/wait, mixed partial data, missing data, unsupported asset classes, optional-field gaps, and explicit non-impact flags.
- Minimally surfaced multi-asset signal reason categories and caution text in the existing report multi-asset section.

### Scope

- Kept `final_action`, equity buy-readiness scoring, threshold JSON and decisions, reliability policy, buy blocker/card logic, buy window/candidate thresholds, risk labels, pipeline behavior, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.25 - Connect Multi-Asset Signal Prototype to Candidate Generation

### Added

- Connected the isolated multi-asset signal prototype to gold, bond, and cash/wait candidate generation without changing report UI or final decision behavior.
- Added candidate-layer regression coverage for signal-derived reason categories, conservative missing-data statuses, and explicit non-impact flags.

### Scope

- Kept equity candidate behavior, report UI, pipeline behavior, `final_action`, threshold JSON and decisions, reliability policy, buy-readiness calculation, buy blocker/card logic, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.24 - Multi-Asset Signal Prototype Model

### Added

- Added an isolated display-oriented prototype model for gold, bond, cash/wait, and partial-data multi-asset signal cases.
- Added targeted tests that use the v0.8.23 fixture contract and confirm conservative missing-data statuses, non-impact flags, and non-advice payload wording.

### Scope

- Kept report UI, `final_action`, threshold JSON and decisions, reliability policy, buy-readiness calculation, buy blocker/card logic, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.23 - Multi-Asset Signal Fixture and Missing-Data Policy

### Added

- Added compact synthetic fixture cases for future gold, bond, cash/wait, and mixed partial-data signal modeling.
- Documented missing-data policy, status vocabulary, reason categories, non-advice wording, and separation from equity buy readiness.
- Added a lightweight fixture schema guard for required cases, missing-data expectations, and non-advice case payloads.

### Scope

- Kept report UI, `final_action`, threshold JSON and decisions, reliability policy, buy-readiness calculation, buy blocker/card logic, CI, scripts, dependencies, generated reports, cache, release archives, tags, GitHub Release, and push out of scope.

## v0.8.22 - Multi-Asset Signal Design Inventory

### Added

- Documented future evaluation-axis inventory for gold, bonds, and cash/wait candidates without adding new scores or changing final decisions.
- Clarified separate gold, bond, and cash/wait signal axes, non-advice wording, and future implementation gates.

### Scope

- Kept report UI, `final_action`, threshold JSON and decisions, reliability policy, buy-readiness calculation, buy blocker/card logic, CI, scripts, dependencies, generated reports, cache, release archives, GitHub Release, and push out of scope.

## v0.8.21 - Multi-Asset Candidate Display Foundation

### Added

- Added a display-only multi-asset candidate foundation that separates equities, gold, bonds, and cash wait by asset-class role.
- Added report rendering for `資産クラス別の確認候補` with explicit caution text, source-data availability, role labels, and no final-action impact.
- Documented the fast-track design, existing ticker inventory, non-advice wording, out-of-scope boundaries, and future gold/bond score considerations.
- Added regression coverage for asset-class separation, missing-data rendering, no forbidden advice phrases, and unchanged final-action/readiness display fields.

### Scope

- Kept `final_action`, threshold JSON and decisions, reliability policy, buy-window/candidate thresholds, buy-readiness calculation, buy blocker/card logic, CI, scripts, dependencies, generated reports, cache, release archives, GitHub Release, and push out of scope.

## v0.8.17 - Actual Smoke Release Checklist Integration

### Added

- Documented optional `python project\main.py --actual-smoke` use in the GitHub publish readiness checklist for release-before and larger decision-score/report-card change review.
- Added an actual-smoke result template covering data source, fallback count, reliability, action layers, readiness score, risk stage, final action, and generated-output handling.
- Clarified how `--sample-only` and `--actual-smoke` differ, and why actual-data smoke remains a local optional check instead of a required CI gate.

### Scope

- Kept CI workflows, scripts, `--actual-smoke` runtime logic, buy-readiness/blocker/decision logic, `final_action`, threshold JSON and decisions, reliability policy, dependencies, generated reports, cache, and release archives unchanged.

## v0.8.16 - Actual Data Readiness Regression and Smoke Command

### Added

- Added a sanitized actual-data-derived caution/watch fixture that locks the v0.8.15 readiness-score regression boundary without committing generated reports or raw market histories.
- Added optional `--actual-smoke` local validation that reuses the newest acquired cached snapshot when available and otherwise attempts the normal fetch path.
- Added regression and CLI/cache-selection tests separating stable fixture coverage from optional network-dependent validation.

### Scope

- Kept buy-readiness/blocker/decision logic, `final_action`, threshold JSON and decisions, reliability policy, CI, security scripts, dependencies, generated reports, cache, and release archives unchanged.

## v0.8.15 - Buy Readiness Score Recalibration

### Fixed

- Recalibrated the explanatory buy-readiness score so caution-level rate and FX warnings do not collapse a monitored, normal-risk, high-reliability setup to a near-zero display score.
- Distinguished `rates_warning` caution severity from true high-severity rate shock and reduced duplicate score-shortfall penalization while preserving strong-blocker and data-quality low-score behavior.
- Added regression coverage for the observed caution scenario, high blockers, sample fallback, shortfall-only behavior, and unchanged decision-card action layers.

### Scope

- Kept `final_action`, threshold JSON and decisions, reliability policy, buy-window/candidate thresholds, risk labels, report layout, CI, security scripts, dependencies, generated reports, cache, and release archives unchanged.

## v0.8.11 - Buy Readiness Gauge Arc Origin Fix

### Fixed

- Aligned the beginner buy-readiness semicircle gauge to a true left-origin arc so very low displayed scores begin at the lower-left endpoint instead of appearing detached from the track.
- Added display regression coverage for missing, zero, low, middle, and high readiness-score values.

### Added

- Added a read-only HTML artifact inventory covering linked generated outputs, sample outputs, temporary QA renders, and future cleanup candidates without deleting generated files.

### Scope

- Kept readiness-score calculation, decision logic, threshold JSON, reliability policy, CI, security scripts, dependencies, generated reports, cache, and release archives unchanged.

## v0.8.10 - Explicit Current-Compatible pct_change Migration

### Fixed

- Replaced implicit percentage-change filling in risk-line feature generation with explicit forward-fill-compatible calculations to remove Pandas deprecation warnings without changing missing-value semantics.
- Verified compatible output across missing-value patterns and added warning-free feature regression coverage.

### Scope

- Kept strict missing-value propagation, threshold JSON, reliability policy, final-action behavior, readiness-score calculation, buy-decision logic, CI, security scripts, dependencies, generated reports, cache, and release archives out of scope.

## v0.8.9 - Feature Library Missing-Value Policy Review

### Added

- Documented the current-compatible and strict missing-value handling alternatives for risk-line feature percentage-change calculations.
- Added regression coverage showing that explicit forward fill reproduces current feature behavior while strict missing propagation changes the output.

### Scope

- Kept production feature calculation unchanged; FutureWarning removal remains a separately validated follow-up.
- Kept threshold JSON, reliability policy, final-action behavior, readiness-score calculation, buy-decision logic, CI, security scripts, dependencies, generated reports, cache, and release archives unchanged.

## v0.8.8 - Runtime Backtest Index Alignment Hotfix

### Fixed

- Aligned risk-line backtest frame and label inputs on their common index before time-split and walk-forward mask evaluation, preventing startup maintenance failures when their available dates differ.
- Added regression coverage for differing frame/label lengths, partially overlapping indexes, and missing target rows.

### Scope

- Kept threshold JSON, reliability policy, final-action behavior, readiness-score calculation, buy-decision logic, CI, security scripts, dependencies, generated reports, cache, and release archives unchanged.
- Left the existing `pct_change` warning behavior unchanged because adopting `fill_method=None` changes feature semantics for input series containing internal missing values.

## v0.8.4 - Multi-Scenario Report UI Snapshot QA

### Added

- Added synthetic multi-scenario coverage for standard monitoring, near-candidate, wait, insufficient-data, no-candidate, and long-blocker beginner UI rendering states.
- Added snapshot QA documentation covering 1366px, 1024px, and 768px temporary render checks.

### Changed

- Confirmed the v0.8.3 HTML/CSS layout needs no additional product UI changes after multi-scenario QA.

### Security

- Confirmed the beginner top sections continue to exclude internal decision terms and investment-advice or outcome-guarantee wording.
- Kept JavaScript, external libraries, decision logic, threshold JSON, `reliability_policy`, `final_action`, `buy_readiness_score` calculation, CI, scanner configuration, allowlists, generated reports, cache, and release archives out of scope.

## v0.8.3 - Report UI Visual QA / Responsive Polish

### Changed

- Polished the beginner-friendly report top UI after generated HTML visual QA by keeping step-flow arrows inside the card bounds to avoid narrow overflow flags.
- Confirmed the `まず見るポイント` and 5-step `買い判断カード` remain HTML/CSS-only with no JavaScript or external library additions.

### Security

- Confirmed the top beginner sections avoid internal decision terms and investment-advice or outcome-guarantee wording.
- Kept decision logic, threshold JSON, `reliability_policy`, `final_action`, `buy_readiness_score` calculation, CI, scanner configuration, allowlists, generated reports, cache, and release archives out of scope.

## v0.8.2 - Beginner Summary HTML/CSS Implementation

### Added

- Added the beginner-readable `まず見るポイント` HTML section with six tiles for current judgment, buy-area state, market state, main reasons, next checks, and a beginner note.
- Added a 5-step `買い判断カード` HTML layout with a CSS-only readiness gauge and the required note that the score is not a success probability.
- Added report HTML tests for the new top sections and scoped internal-term exclusion.

### Changed

- Replaced the top `まず見る要約` and mixed `Buy Decision Card / 買い判断カード` HTML sections with Japanese-first beginner summary UI.
- Kept the implementation HTML/CSS-centered without adding JavaScript or external libraries.

### Security

- Kept decision logic, threshold JSON, `reliability_policy`, `final_action`, `buy_readiness_score` calculation, CI, scanner configuration, allowlists, generated reports, cache, and release archives out of scope.

## v0.8.1 - Report UI Redesign Plan

### Added

- Added a documentation-only report UI redesign plan for replacing the top `まず見る要約` and `Buy Decision Card / 買い判断カード` areas with beginner-readable `まず見るポイント` and a 5-step `買い判断カード`.
- Added Japanese display-label guidance for keeping internal terms out of the first screen while preserving existing decision outputs.
- Added a v0.8.2+ roadmap for HTML/CSS-first implementation and later progressive disclosure.

### Changed

- Clarified that v0.8.1 is a planning release and does not implement report generator changes.

### Security

- Confirmed that the plan does not change decision logic, threshold JSON, `reliability_policy`, CI, scanner configuration, allowlists, generated reports, cache, or release archives.

## v0.8.0 - Post-Publish Operation Baseline

### Added

- Added post-publish operation baseline documentation for GitHub Actions, GitHub Release, release package, scanner review, issue intake, and security finding intake.
- Added README and publish-doc links to the post-publish baseline.

### Changed

- Changed pytest temporary output to `.pytest_tmp` so clean CI checkouts do not require a pre-existing `.tmp` parent directory.
- Clarified drawdown summary typing so CI mypy on Python 3.11 accepts the diagnostic analysis module.

### Security

- Documented post-publish handling for non-blocking Gitleaks review, generated-output exclusion, and security finding intake without adding required scanner enforcement, scanner allowlists, or scanner configuration.

## v0.7.12 - GitHub Publish Final Dry Run

### Added

- Added final GitHub publish dry-run documentation.
- Added explicit final dry-run commands, forbidden diff checks, and publish stop conditions.

### Changed

- Linked README and publish readiness guidance to the final dry-run checklist.

### Security

- Confirmed final publish checks for security audit readiness, generated/cache/report exclusion, package manifest verification, and scanner finding handling without changing CI requirements or scanner configuration.

## v0.7.11 - Pre-Publish Integration Review

### Added

- Added a pre-publish integration review that maps CI, security audit, release packaging, manifest verification, optional scanner review, and scanner findings policy responsibilities.

### Changed

- Linked README and release-operation docs to the integrated pre-publish responsibility map.
- Replaced the stale optional-scanner TODO in the v0.7.3 hardening notes with references to the later scanner decision docs.

### Security

- Confirmed that scanner CI remains optional, findings are not written to the release package manifest, and generated/cache/release artifacts remain outside source control.

## v0.7.10 - Scanner Findings Integration Decision

### Added

- Added scanner findings integration decision documentation for optional Gitleaks CI findings.
- Added release review rules for verified, high-confidence, and unexplained scanner findings.

### Changed

- Clarified that optional Gitleaks CI findings are release review inputs, not standalone required CI gates.
- Clarified that scanner findings are recorded in CI logs, security audit outputs, and sanitized release review notes rather than `PACKAGE_MANIFEST.json`.

### Security

- Documented release stop conditions for optional scanner findings without adding `.gitleaks.toml`, allowlists, TruffleHog CI, or required Gitleaks enforcement.

## v0.7.9 - Gitleaks Optional CI Evaluation

### Added

- Added documentation for evaluating the optional Gitleaks CI trial.
- Added guidance for checking non-blocking behavior, CI logs, finding handling, and required-enforcement decision inputs.

### Changed

- Linked secret scanner adoption and publish readiness documentation to the v0.7.9 evaluation note.

### Security

- Documented that Gitleaks remains optional and non-blocking in v0.7.9.
- Documented that verified or high-confidence findings should stop public release review.
- Confirmed that required CI enforcement, `.gitleaks.toml`, and allowlist changes remain out of scope.

## v0.7.8 - Gitleaks Optional CI Trial

### Added

- Added a non-blocking GitHub Actions job for optional Gitleaks scanning.
- Documented Gitleaks CI trial behavior and release-stop handling for findings.

### Changed

- Clarified that Gitleaks CI is observational in v0.7.8 and is not a required release gate.

### Security

- Kept Gitleaks findings subject to manual review before release, without adding a default allowlist.

## v0.7.7 - CI Release Package Verification Integration

### Added

- Added latest release package auto-detection to release package verification.
- Added CI release package creation and manifest verification after dry-run validation.
- Added tests for latest release package detection.

### Changed

- Documented CI tagless package verification and release-tag verification guidance.

### Security

- Connected CI to the same generated/cache and forbidden-entry package verification used for local release checks.

## v0.7.6 - Release Package Manifest Verification

### Added

- Added release package verification tooling for source archives.
- Added automated checks for package manifest tag, commit, file count, required files, and forbidden entries.
- Added tests for release package verification behavior.

### Changed

- Linked publish readiness guidance to the release package verification command.

### Security

- Documented and automated checks for generated/cache, `.git`, `.env`, release recursion, and secret-adjacent package entries.

## v0.7.5 - Secret Scanner Adoption Decision

### Added

- Added secret scanner adoption guidance for Gitleaks and TruffleHog.
- Added local optional scanner commands for release workstations.
- Added release stop conditions for verified or high-confidence secret findings.

### Changed

- Clarified that Gitleaks is the preferred optional scanner and TruffleHog remains a candidate scanner.
- Linked publish readiness guidance to the secret scanner adoption documentation.

### Security

- Documented non-blocking scanner setup, escalation criteria, and public release stop conditions for secret findings.
- Documented that false positives should not be immediately allowlisted without rationale.

## v0.7.4 - GitHub Publish Readiness Checklist

### Added

- Added GitHub publish readiness checklist documentation.
- Added explicit release package manifest verification steps.
- Added known-warning handling for gitleaks/trufflehog and local pip check notes.

### Changed

- Linked README release guidance to the publish readiness checklist.

### Security

- Documented pre-publish checks for forbidden entries, generated/cache exclusion, secrets-adjacent files, and threshold/decision logic non-change verification.

## v0.7.3 - Release / Operation Hardening

### Added

- Added GitHub Actions CI for tests, linting, formatting checks, typing, dependency audit, security audit, and release package dry-run validation.
- Added a source-only release package script with generated/cache exclusion rules and a JSON manifest.
- Added sample-only documentation fixtures under `docs/sample/` for README references without committing live reports or cache.

### Changed

- Documented the shortest local run path, sample-only interpretation, Buy Decision Card reading notes, generated-file handling, and common misunderstandings.
- Kept v0.7.3 scoped to release and operational hardening without changing investment decision logic.

### Security

- Hardened the local security audit path for CI use and kept optional scanners as warnings when unavailable.
- Documented detect-secrets baseline handling and continued pip-audit usage for release checks.
