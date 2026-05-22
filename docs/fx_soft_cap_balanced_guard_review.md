# fx_soft_cap balanced guard review

`balanced_dd_guard` は、`combined_dd_guard` より取りこぼしを減らしつつ、一律 `fx_soft_cap` より deep DD を抑えるための診断候補です。

初期条件:

- ACWI/SPY relative strength が極端に悪いケースは除外
- `foreign_asset_fx_headwind` と ACWI 劣後が重なるケースは除外
- VIX / credit shock は除外
- 直近 DD と 4w return が悪いケースは除外
- recovery context が弱いケースは除外

この候補は採用ではありません。historical replay と current watchlist の両方で確認し、final action には反映しません。
