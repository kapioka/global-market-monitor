# experimental TimesFM evaluation

TimesFM diagnostic work was evaluated during v0.7.1 preparation, but it is not included in the v0.7.1 product surface.

Reasons:

- signal_quality: not_useful
- false_supportive_count: 11
- correctly_blocked special risk high rate: 0.0%
- added forecast diagnostics reduced explainability for v0.7.1
- final_action must remain based on active thresholds and reliability policy

TimesFM must not affect final_action, buy_candidate, buy_window, fx_soft_cap, or regime-aware candidates in v0.7.1. Future TimesFM work should happen on a separate branch as optional research only.
