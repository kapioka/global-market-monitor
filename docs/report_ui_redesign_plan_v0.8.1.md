# Report UI Redesign Plan v0.8.1

v0.8.1 is a documentation-only UI redesign plan for the top of `report.html`.

The goal is to redesign `まず見る要約` and `Buy Decision Card / 買い判断カード` into a beginner-readable `まず見るポイント` section and a 5-step `買い判断カード`. This plan does not change decision logic, threshold JSON, `reliability_policy`, `buy_readiness_score`, `final_action`, CI, scanner settings, generated reports, cache, or release archives.

## Current Problems

- The top of the report contains too much text for a first glance.
- English labels and internal terms appear before the reader understands the state.
- It is not immediately clear which items a beginner should inspect first.
- `Buy Decision Card / 買い判断カード` explains useful details, but it exposes implementation-oriented labels such as `final`, `raw`, `risk_adjusted`, `primary_blocker`, and `unlock_conditions` too early.
- Diagnostic and candidate wording can look more decisive than intended if it appears in the top summary.

## New UI Purpose

- Let a beginner understand the current situation in about 3 seconds.
- Keep the top area focused on state confirmation, not investment advice.
- Keep every decision exactly as the existing logic calculates it.
- Move internal terms to lower detail sections or documentation.
- Show the same facts with clearer Japanese labels and a calmer visual hierarchy.

## Design Risks and Countermeasures

### Risk: UI Improvement Can Look Like Decision Improvement

Large labels such as `買い場か？` and `今すること` can look like investment advice if the wording is too direct.

Countermeasures:

- Prefer `監視継続`, `まだ早い`, `材料待ち`, and `次の確認を待つ`.
- Avoid `買い推奨`, `買う`, `今すぐ`, and similar action-command wording.
- Keep a visible note that `買い候補度` is not a success probability, expected return, or investment success rate.
- Keep the self-responsibility and no-automated-trading notices in the report.
- State in docs that this is a display-layer redesign and does not affect `final_action`.

### Risk: `report_generator.py` Can Become Too Large

The current HTML report is centered in `project/report_generator.py`. Adding more HTML, CSS, and explanatory text there can make the file harder to maintain.

Countermeasures for v0.8.2:

- Replace only the target top sections first.
- Use clearly separated CSS class names for the redesign.
- Keep the implementation small enough to review against the existing report output.
- Consider component extraction only after the first implementation is stable.
- Stop if a clean implementation appears to require broad report-generator restructuring.

### Risk: JavaScript Can Distract From First-Glance Reading

The goal is quick comprehension. Animation, complex interaction, external libraries, or chart JavaScript would add risk without helping the first implementation.

Countermeasures:

- Keep v0.8.2 HTML/CSS-first.
- Do not add external libraries or CDN dependencies.
- Do not add complex chart JavaScript.
- Reserve optional detail toggles, tooltips, and score-gauge accessibility helpers for v0.8.3 or later.

## New Section Structure

### まず見るポイント

`まず見るポイント` replaces `まず見る要約` as the first scan area.

It should answer:

- What is the current status?
- Is this a buy-area signal or still a watch state?
- Is the market calm, recovering, stressed, or uncertain?
- What is the main reason for the current judgment?
- What should the reader inspect next?
- What is the beginner-friendly one-line interpretation?

### 買い判断カード

`買い判断カード` replaces the current mixed English/Japanese `Buy Decision Card / 買い判断カード` title and turns the decision path into five visible steps:

1. 現在の判断
2. 理由
3. 危険度
4. 買い候補
5. 今すること

The card remains explanatory only. It must not add a stronger action, recommendation, automation trigger, or hidden decision layer.

## まず見るポイント Tile Proposal

The top section should use six small tiles:

| Tile | Purpose | Example label direction |
| --- | --- | --- |
| 今の判断 | Show the current official state | 監視継続 / 待機 / 要確認 |
| 買い場か？ | Explain whether conditions are early, close, or insufficient | まだ早い / 候補に近い / 条件不足 |
| 市場の状態 | Summarize the regime in plain Japanese | 通常 / 回復途中 / 不安定 / 警戒 |
| 主な理由 | Show the main plain-language blocker or support reason | 金利ショックの影響が残る |
| 次に見るもの | Point to the next useful checks | SPY / XLK / 危険ライン |
| 初心者向けひとこと | Give a short non-advisory interpretation | 今は急がず、材料がそろうまで様子を見る局面です |

Tile copy should be short. The top row should not explain every detail. Detailed values can stay lower in the report or in supplementary documentation.

## 5-Step Buy Decision Card Proposal

The card should read left to right on desktop and stack cleanly on small screens:

| Step | Title | Content direction |
| --- | --- | --- |
| 1 | 現在の判断 | The official status using Japanese display labels |
| 2 | 理由 | The main reason the action is not stronger, written as plain Japanese |
| 3 | 危険度 | A low/medium/high risk display derived from existing report fields |
| 4 | 買い候補 | Candidate symbols or sectors, framed as reference checks |
| 5 | 今すること | A non-advisory next-review action such as waiting for confirmation |

The readiness score can remain visible as `買い候補度`, but it must be labeled as an explanatory score, not a probability or expected return.

## Display Label Replacement Policy

Use a display mapper or equivalent presentation layer so internal values can stay unchanged while the top UI uses beginner-readable Japanese.

| Internal or current label | Top UI label |
| --- | --- |
| `final action` / `final_action` | 最終判断 |
| `diagnostic only` | 参考情報 / 診断用 |
| `buy_window` | 買い場サイン |
| `buy_candidate` | 買い候補 |
| `primary blocker` / `primary_blocker` | 主な見送り理由 |
| `buy_readiness_score` | 買い候補度 |
| `unlock_conditions` | 次に確認する条件 |
| `sample-only` | 表示確認用サンプル |

These replacements are presentation labels only. They must not rename data fields, change JSON contracts, or change calculation behavior in v0.8.2.

## Internal Terms to Remove From the Top Area

The first screen should not show these terms:

- raw/final `buy_window`
- raw/final `buy_candidate`
- proposed / candidate
- trigger path
- `live_data_sufficient`
- sample-only
- `market_raw_action`
- `risk_adjusted_action`
- diagnostic-only policy names such as `fx_soft_cap`

If these values remain useful, move them to detail sections, developer-facing docs, or lower diagnostic tables.

## HTML Direction

- Use semantic `section`, `article`, and `aside` elements.
- Add clear `aria-label` values to the top summary and buy decision sections.
- Keep headings Japanese-first.
- Keep internal values in data attributes or lower detail areas only when needed.
- Use a display mapper to convert internal values into Japanese labels before rendering the top UI.
- Keep the existing report generation flow intact for v0.8.2.
- Use a structure close to:
  - `section.glance-summary`
  - `div.glance-grid`
  - `article.glance-tile`
  - `section.buy-decision-flow`
  - `div.buy-flow-layout`
  - `article.buy-step`
  - `aside.readiness-panel`

## CSS Direction

- Use compact tiles for `まず見るポイント`.
- Use step cards for the 5-step `買い判断カード`.
- Keep visual density high enough for an operational dashboard, not a marketing page.
- Use restrained color states for status, warning, caution, and neutral information.
- Use a score gauge for `買い候補度`, with clear text saying it is not a success probability.
- Ensure responsive layout works as one row on wide screens and readable stacked rows on narrow screens.
- Avoid layouts that depend on external assets or network access.
- Keep print and local-file HTML stable by using simple CSS, fixed fallback colors, and robust spacing.
- Keep redesign class names separate from current summary classes so the change can be reviewed and reverted locally if needed.
- Candidate classes:
  - `.glance-summary`
  - `.glance-grid`
  - `.glance-tile`
  - `.buy-decision-flow`
  - `.buy-flow-layout`
  - `.buy-steps`
  - `.buy-step`
  - `.readiness-panel`
  - `.score-gauge`
  - `.chip-row`
  - `.tone-watch`
  - `.tone-wait`
  - `.tone-normal`
  - `.tone-reason`
  - `.tone-next`
  - `.tone-beginner`

## JS Direction

- v0.8.2 should use no new JavaScript unless rendering constraints make it unavoidable.
- Prefer HTML/CSS and server-side report generation for the first implementation.
- v0.8.3 or later can consider optional detail toggles, tooltips, or progressive disclosure.
- Any later JS must not calculate or override the official decision.
- If JS is later added, keep it limited to details disclosure, tooltip assistance, or accessibility support for already-rendered values.

## v0.8.2 and Later Roadmap

### v0.8.2 HTML/CSS Implementation

- Update `project/report_generator.py` only if implementation is explicitly approved for v0.8.2.
- Add the `まず見るポイント` layout.
- Convert the current card into the 5-step `買い判断カード`.
- Add a small display-label mapping layer for top-section Japanese labels.
- Keep `raw/final buy_window`, `raw/final buy_candidate`, diagnostic policy names, and trigger details out of the first screen.
- Keep all existing decision outputs and JSON fields unchanged.
- Verify generated `report.html` visually and with the existing test suite.

### v0.8.3 Progressive Disclosure

- Consider detail toggles for internal values.
- Consider tooltips for terms that still need explanation.
- Keep the default first view beginner-readable.

### Future Candidate Work

- Review `docs/how_to_read_report.md` and `docs/how_to_read_buy_decision.md` after the UI implementation lands.
- Consider screenshot-based regression checks only after the layout stabilizes.

## Acceptance Criteria

- The plan is documented in this file.
- README links to this plan as the v0.8.1 report UI redesign plan.
- CHANGELOG records v0.8.1 as documentation-only planning work.
- The v0.8.0 post-publish baseline points to v0.8.1 as the next UI planning candidate.
- No project logic, threshold JSON, reliability policy, CI, scanner configuration, generated reports, cache, or release archives are changed.
- The plan keeps wording non-advisory and does not describe automated trading.

## Not Doing in v0.8.1

- No `project/report_generator.py` implementation.
- No decision logic changes.
- No `final_action` changes.
- No `buy_readiness_score` calculation changes.
- No active/proposed threshold changes.
- No `buy_window` or `buy_candidate` threshold changes.
- No reintroduction of excluded forecasting features.
- No formal adoption of `fx_soft_cap` or regime-aware FX policy.
- No automated trading feature.
- No investment-advice wording.
- No CI required-gate changes.
- No `.gitleaks.toml` or allowlist changes.
- No generated report, cache, or release zip commits.
