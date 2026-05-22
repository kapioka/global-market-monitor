# report reading notes

## Buy Window Diagnostics

`raw buy_window` は市場だけを見た買い場候補、`final buy_window` は安全ガードまで通した最終表示です。

FXによる買い場降格は診断対象です。future return が不足するケースは `inconclusive` として扱い、policy 変更の根拠にはしません。

## buy_candidate near-miss

`buy_candidate near-miss` は、買い場候補に近かったが条件が1〜2個足りなかった履歴です。

`buy_candidate` が0件でも、near-miss の主な不足条件を見ることで、条件が厳しすぎるのか、市場環境が弱いのかを切り分けます。

## FX soft-cap diagnostic

`fx_soft_cap` は採用済み policy ではありません。通常レポートで表示される場合も diagnostic only です。

`fx_soft_cap` は、為替リスクがある買い場を `buy_window` ではなく `buy_candidate` として見える化する候補です。final action には影響しません。

`FX soft-cap watchlist` は、future data が揃うまでの追跡リストです。ready for review が増えるまでは adoption decision は基本 `hold` です。

`FX soft-cap historical replay` は、過去価格による検証補助です。過去類似ケースの件数や成績は採用判断の材料であって、final action ではありません。

`Conditional FX soft-cap diagnostics` は、一律 `fx_soft_cap` を避け、どの条件なら `buy_candidate` として見てもよいかを比較する診断です。best candidate が表示されても、affects final action は false です。

`FX soft-cap DD guard diagnostics` は、historical replay で残った deep drawdown を除外できるかを見る診断です。worst DD が改善しても、final action には自動反映しません。

`FX soft-cap balanced guard` は、deep DD を防ぎつつ missed good を減らすための中間候補です。表示される場合も diagnostic only です。

`FX soft-cap long-range diagnostics` は、2024年以降だけでなく 2020 / 2022 / 2023 / 2024-2026 の局面別に guard 候補を比較する診断です。`without_equity_trend_guard` が良く見えても、複数局面で悪化しないことを確認するまでは adoption decision は `hold` です。

`Regime-aware FX diagnostics` は、rate shock / risk-off では FX soft-cap を許さず、normal / recovery では診断上の `buy_candidate` 候補として扱えるかを見る比較です。表示される best candidate は採用済みルールではなく、final action には影響しません。
