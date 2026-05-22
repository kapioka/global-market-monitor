# fx_soft_cap regime analysis

`fx_soft_cap` 系の guard 候補が、特定期間だけで良く見えていないかを確認するための診断。

regime は初期実装では以下に分ける。

- 2020 crash/recovery
- 2022 rate shock
- 2023 recovery
- 2024-2026 recent regime

各 regime で見る項目:

- count
- overblocked
- correctly_blocked
- missed_good
- 13w / 26w excess return
- worst DD

`without_equity_trend_guard` が 2024-2026 だけでなく、2020年や2022年の悪い局面でも壊れないかを確認する。

この分析は採用判断の前段であり、final action や reliability policy は変更しない。
