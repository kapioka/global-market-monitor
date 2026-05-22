# FX risk policy review

This is diagnostic-only. Current final action policy is unchanged.

## Taxonomy

- `note_only`: keep the action, but show an execution note for smaller staged execution and yen-impact confirmation.
- `soft_cap`: cap `buy_window` to `buy_candidate`; keep `buy_candidate` available.
- `hard_cap`: cap `buy_candidate` / `buy_window` to `watch` or below.

## Replay candidates

- `current`: current behavior.
- `fx_note_only`: FX caution / moderate are notes only.
- `fx_soft_cap`: FX moderate/headwind caps `buy_window` to `buy_candidate`.
- `fx_high_only_block`: only high/shock FX risk blocks strong actions.

Do not change `risk_line_thresholds_active.json`, `risk_line_thresholds_proposed.json`, reliability policy, or final action policy from this review alone.

## fx_soft_cap diagnostic

`fx_soft_cap` is the current preferred diagnostic candidate because it does not turn FX moderate/headwind into `buy_window`. It caps `buy_window` to `buy_candidate`.

`buy_candidate` is not a buy instruction. It means a staged, small-size, yen-impact-aware candidate that still needs future return, excess return, and drawdown validation.

Track diagnostic cases with `python -m project.fx_soft_cap_watchlist`. Adoption requires 13w/26w evidence and remains `hold` while future data is missing.

Historical backfill replay can shorten the waiting loop by checking past price-based similar cases before current watchlist cases reach 13w/26w. Even if historical replay looks favorable, `fx_soft_cap` remains diagnostic-only until current watchlist evidence also confirms it.

Conditional replay is the next layer after the one-size `fx_soft_cap` replay. It is used to avoid cases where FX caution was correctly blocking weak outcomes, while preserving cases where current policy likely overblocked a reasonable `buy_candidate`.
