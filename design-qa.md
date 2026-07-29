# Signal Canvas redesign QA

## 判定

合格。P0 / P1 / P2 の未解決事項はありません。

## 比較対象

- 選択モック: `C:\Users\akiso\.codex\generated_images\019fadc1-847d-7783-bf67-e99c52fca556\call_3JZ2IPXekj4plWURdxLRjrTr.png`
- 実装比較: `C:\Users\akiso\.codex\visualizations\2026\07\29\019fadc1-847d-7783-bf67-e99c52fca556\design-comparison.png`
- 本体 1536 × 1024: `C:\Users\akiso\.codex\visualizations\2026\07\29\019fadc1-847d-7783-bf67-e99c52fca556\report-wide-1536.png`
- 本体 1366 × 900（補足を下段表示）: `C:\Users\akiso\.codex\visualizations\2026\07\29\019fadc1-847d-7783-bf67-e99c52fca556\report-wrap-1366.png`
- 本体 390 × 844: `C:\Users\akiso\.codex\visualizations\2026\07\29\019fadc1-847d-7783-bf67-e99c52fca556\report-mobile-top-390.png`
- 補足 1536 × 1024: `C:\Users\akiso\.codex\visualizations\2026\07\29\019fadc1-847d-7783-bf67-e99c52fca556\supplement-wide-1536.png`
- 補足 390 × 844: `C:\Users\akiso\.codex\visualizations\2026\07\29\019fadc1-847d-7783-bf67-e99c52fca556\supplement-mobile-390.png`

## 確認結果

- レイアウト: 広幅では本体と補足要約を約 58:42 で並べ、1480px 以下では補足を本体の下へ回した。補足単体は広幅で詳細 1–5 / 6–10 の2列、1280px 以下で1列になる。
- 情報導線: 「今日の判断 → 観察候補 → セクター概要 → 危険ライン・補助確認 → 履歴」の順序を維持した。既存セクター四象限、2週前・先週・現在の位置、移動軌跡も残っている。
- コンテンツ保持: 本体と補足の既存セクションを削除していない。補足詳細は10セクションすべて表示される。
- レスポンシブ: 1536、1366、390px でページ全体の横方向オーバーフローなし。モバイルの詳細表だけはカード内で横スクロールできる。
- 可読性: モバイルで詰まっていた補足の読み方欄を1列へ修正し、本体見出しの不自然な単語分割も抑えた。
- 操作・アクセシビリティ: 補足リンクはキーボードフォーカス表示を持ち、セクションリンクと年代記リンクが有効。コンソール警告・エラーは検出されなかった。
- 市場警戒年代記: 保存済み成果物は鮮度にかかわらず「保存済みを閲覧可能」となり、別窓リンクを常時表示する。`3日以内`、`公開条件`、`更新待` は生成HTMLに含まれない。
- 保護対象: `final_action`、`spot_signal.action_decision`、しきい値設定・レビュー値をレンダリング前後で比較し、変更がないことをテストした。

## 許容した差

- P3（意図的）: 選択モックより本体上部が縦に長い。既存の判断理由、候補説明、取得制約を削除しない要件を優先したためで、判断と補足の左右関係、配色、視線順はモックに合わせている。
