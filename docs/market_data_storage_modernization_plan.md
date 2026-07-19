# 市場データ保存基盤の長期運用・容量最適化計画

更新日: 2026-07-19

状態: Phase 2 shadow初回移行まで完了、primary切替前の容量改善待ち

対象: アプリ全体の市場時系列データ保存、互換出力、履歴参照

> この文書はデータ保存基盤の実装計画であり、Risk Engine V2 の進捗・昇格状態を更新する文書ではない。Risk Engine V2 の正本は `docs/risk_engine_v2_current_state.md` のままとする。

## 1. 結論

長期運用の標準構成を次のようにする。

- 日々蓄積する価格・指数・金利等の時系列は、ローカルの SQLite に正規化して保存する。
- 初回だけ検証済みの全履歴を取り込み、通常運用では新しい観測値と訂正値だけを追加する。
- 同じ日付・同じ指標・同じ値の再取得は重複保存しない。
- 後日値が訂正された場合は上書きせず、改訂番号を付けて履歴を残す。
- JSON は判断証拠、診断結果、エピソード、生成物メタデータに引き続き使用する。
- CSV は廃止せず、人が確認できる最新エクスポート、移行中の互換入力、非常時の復旧用に限定する。
- HTML/Markdown は表示用生成物として扱い、時系列データの正本にはしない。
- 実装は shadow 導入、照合、読み取り切替、保存量削減の順で進める。照合が終わる前に既存CSVを削除しない。

この構成は「配布後に利用者がデータベースを管理しなくても動くこと」と「10年、20年を越えても同じ全履歴を毎回複製しないこと」を両立する。SQLite はアプリ内蔵の保存部品として使い、利用者にSQL操作を求めない。

## 2. 現状確認と問題の切り分け

### 2.1 確認済みの現状

- レポート履歴は `project/report_runtime.py` で日単位に整理され、設定された定刻は現在 07:30 である。定刻の生成物がなければ、その日の最新1件を残す。
- 最新レポートは日次履歴とは別に更新される。
- 市場スナップショットは `project/snapshot_store.py` が実取得のたびに、全期間を含むCSVとメタデータJSONを新規保存する。
- 現在の市場スナップショット保管には同日複数件が存在し、日次1件への整理は実装されていない。
- 現在の作業環境では、市場スナップショット12件が合計約27.4 MB、1件平均約2.28 MBである。
- アプリにはヒンデンブルグ・オーメン用のSQLite実装が既にあり、スキーマ初期化、整合性検査、冪等登録、競合保持、バックアップの実例がある。
- Python標準ライブラリの `sqlite3` を使えるため、SQLite採用そのものに新しい配布依存は不要である。

### 2.2 容量増加の主因

現在の主因は「1日1件のレポート履歴」ではなく、「取得のたびに過去全期間を含む市場CSVを複製すること」である。同日1件だけに整理しても、毎日ほぼ同じ全履歴を再保存する構造は残る。

SQLiteを使うだけで自動的に圧縮されるわけではない。容量削減の本体は、次の保存規則にある。

1. 指標・日付ごとに一度だけ保存する。
2. 新しい日付だけを追加する。
3. 値が変わったときだけ改訂履歴を追加する。
4. 実行ごとの全履歴複製をやめる。

### 2.3 代替方式の比較

| 方式 | 容量 | 差分更新 | 過去時点再現 | 配布・保守 | 採否 |
|---|---:|---:|---:|---:|---|
| SQLite | 小さい | 得意 | 得意 | Python標準、単一ファイル | 採用 |
| gzip圧縮CSV/JSONL | 小さめ | 苦手 | 実装次第 | 単純だが検索・訂正が重い | 非常用のみ |
| Parquet | 非常に小さい | 追記・訂正に設計が必要 | 実装次第 | `pyarrow` 等の追加依存 | 実測後の将来候補 |
| DuckDB + Parquet | 非常に小さい | 得意 | 得意 | ネイティブ依存と配布検証が増える | 現時点では見送り |
| 全履歴CSVを日次保存 | 大きい | 不得意 | ファイル単位 | 確認しやすいが重複が大きい | 段階的廃止 |

最初からParquetやDuckDBを加えず、既存アプリ内に実績があり配布負担の小さいSQLiteで問題を解く。将来、SQLite単体の実測容量や速度が目標を外れた場合だけ、冷たい過去データのParquet退避を再評価する。

## 3. ゴール、非ゴール、保護境界

### 3.1 ゴール

- 20年以上の運用でも、実行回数に比例して全履歴ファイルが増えない。
- 初回全履歴取込後は、新規観測と訂正だけが増える。
- 同一入力の再実行が冪等であり、行数・容量を不必要に増やさない。
- 「その当時に分かっていた値」で過去局面を再現できる。
- データ破損時に最後の正常DBまたは互換CSVから復旧できる。
- 通常利用者はSQL、バックアップ、VACUUM、スキーマ移行を意識しない。
- 既存レポート、replay、年代記が段階移行中も動作する。

### 3.2 非ゴール

- 今回の保存基盤変更だけで取得元の全APIを作り直さない。
- レポートJSON、診断JSON、HTMLをすべてDB内のBLOBへ移さない。
- 初期段階で過去CSVを削除しない。
- UIや判断ロジックを保存形式に合わせて変更しない。
- 実測なしにParquet、DuckDB、外部DBサーバーを追加しない。

### 3.3 変更禁止・維持条件

- `final_action`、`reliability_policy`、threshold JSON、buy-window / buy-candidate policyを変更しない。
- `risk_engine_v2.mode=shadow`、`promotion_allowed=False`、`policy_status=diagnostic_only_not_promoted` を維持する。
- 診断・証拠整合性の改善をproduction decision logicへ接続しない。
- 同一市場入力に対するproduction判断が保存形式の切替前後で一致することを必須にする。
- DB、バックアップ、WAL、移行一時ファイルはGit追跡および配布パッケージへの同梱対象にしない。
- commit、push、tag、release、既存履歴削除はそれぞれ別のユーザー承認を必要とする。

## 4. 目標アーキテクチャ

### 4.1 保存先

標準保存先:

```text
%LOCALAPPDATA%\GlobalMarketMonitor\market_data\market_data.sqlite3
```

テスト・高度な運用向けに、環境変数 `GLOBAL_MARKET_MONITOR_DB_PATH` で上書きできるようにする。`LOCALAPPDATA` が使えない環境では、既存ヒンデンブルグ保存先と同じ方針でユーザーホーム配下へフォールバックする。

### 4.2 データの責務分離

| データ | 運用上の正本 | 役割 |
|---|---|---|
| 市場時系列 | SQLite | 長期保存、差分更新、改訂、as-of参照 |
| 取得実行履歴 | SQLite | 成否、件数、入力fingerprint、警告 |
| 判断・診断証拠 | JSON | 人と検証コードが読む不変成果物 |
| 年代記エピソード | JSON + HTML | 証拠束と閲覧画面 |
| 最新市場エクスポート | CSV + JSON | 人による確認、互換、非常復旧 |
| レポート表示 | HTML / Markdown | 再生成可能な表示物 |

移行中は既存CSV/JSONを正本とし、SQLiteはshadowで照合する。全ゲート通過後に限り、市場時系列の運用上の正本をSQLiteへ切り替える。JSON証拠の正本性は変更しない。

### 4.3 データフロー

```text
取得元
  ↓
取得結果の正規化・検証
  ↓
SQLite transaction ──→ 新規観測 / 改訂 / 実行記録
  ↓ commit後
最新CSV + metadata JSONを原子的に更新
  ↓
既存レポート / replay / 年代記
```

shadow期間は既存CSV保存も続け、SQLiteから再構成したフレームと値・範囲・欠損・SHAを比較する。

## 5. SQLiteデータモデル

実装時の名称は既存命名と整合させるが、最低限次の構造を持たせる。

### 5.1 `schema_migrations`

- `version` INTEGER PRIMARY KEY
- `applied_at` TEXT NOT NULL
- `app_version` TEXT

DB起動時に一方向のスキーマ移行を行う。未知の新しいスキーマは書き込みを止め、破壊的な自動ダウングレードをしない。

### 5.2 `series`

- `series_id` TEXT PRIMARY KEY
- `source_id` TEXT NOT NULL
- `source_type` TEXT NOT NULL
- `frequency` TEXT NOT NULL
- `value_kind` TEXT NOT NULL
- `created_at` TEXT NOT NULL
- `metadata_json` TEXT

ティッカー名だけで一意にせず、取得元と値種別を含む安定IDを使う。将来の名称変更は別名メタデータで吸収する。

### 5.3 `ingestion_runs`

- `run_id` TEXT PRIMARY KEY
- `observed_at` TEXT NOT NULL
- `source` TEXT NOT NULL
- `input_fingerprint` TEXT NOT NULL
- `status` TEXT NOT NULL
- `row_count` INTEGER NOT NULL
- `inserted_count` INTEGER NOT NULL
- `revised_count` INTEGER NOT NULL
- `warning_json` TEXT
- `completed_at` TEXT

同じ入力fingerprintの成功済み実行を再処理しても観測値を増やさない。

### 5.4 `observations`

- `series_id` TEXT NOT NULL
- `observation_date` TEXT NOT NULL
- `revision` INTEGER NOT NULL
- `value` REAL
- `observed_at` TEXT NOT NULL
- `run_id` TEXT NOT NULL
- `value_hash` TEXT NOT NULL
- `quality_json` TEXT
- PRIMARY KEY (`series_id`, `observation_date`, `revision`)

必要な索引:

- (`series_id`, `observation_date`)
- (`run_id`)
- (`observed_at`)

最新値用の `current_observations` viewを用意し、各series/dateの最大revisionを返す。過去時点参照は、指定された取得時刻以前の最大revisionを選ぶ。

### 5.5 `artifact_registry`

- `artifact_type`
- `artifact_path`
- `sha256`
- `generated_at`
- `source_run_id`
- `status`

大きなJSONやHTML本体をDBへ入れず、生成物の場所・SHA・由来だけを索引化する。DBと証拠成果物を一体化し過ぎない。

## 6. 取込・改訂・欠損の規則

### 6.1 初回取込

1. 現在の検証済み最新CSVを読み込む。
2. 日付、列、重複、型、範囲、欠損表現を正規化する。
3. 新規DBまたは一時DBの単一transactionへ全履歴を登録する。
4. SQLiteから同じワイドフレームを再構成する。
5. 元CSVと、列集合、日付範囲、非欠損数、値、fingerprintを比較する。
6. `PRAGMA integrity_check` が `ok` であることを確認する。
7. 全一致したDBだけを候補DBとして採用する。

不一致なら既存CSV運用を継続し、候補DBは正本にしない。

### 6.2 通常更新

- 取得結果が全履歴で返ってきても、DB側で差分を計算し、新規・改訂だけを保存する。
- これによりネットワーク取得範囲の最適化前でも、ディスク容量の改善は先に得られる。
- 次段階で、取得adapterが対応する系列は `最新観測日 - revision_window_days` から取得する。
- 改訂確認窓の初期案は90日とし、各取得元の訂正特性を実測して短縮・延長する。
- 定期監査では低頻度でより長い範囲を再確認し、取りこぼした訂正を検出する。

### 6.3 冪等・改訂

- 同じseries/date/value_hash: 何も追加しない。
- 同じseries/dateで値が変化: `revision + 1` を追加する。
- 新しいdate: revision 1として追加する。
- 欠損の再取得: 既存値を自動削除しない。
- 明示的な削除訂正が必要な場合: 将来のtombstone規則を別スキーマ版で導入し、通常欠損と区別する。
- 同一run内で相反する値: transactionを中止し、fail-closedで競合を記録する。

### 6.4 point-in-time再現

年代記、replay、holdoutで先読みを防ぐため、通常の「現在最新値」取得と「指定時点で利用可能だった値」取得を別APIにする。

- `load_current_frame(...)`: 現時点の最新revision
- `load_frame_as_of(observed_at=...)`: 指定時刻以前に入手済みの最新revision

年代記の指標選定では、エピソード当時に取得可能だった情報だけを使う。後から確定したデータで当時の選定理由を書き換えない。

## 7. 容量・保持・バックアップ方針

### 7.1 通常保持

- SQLite本体: 1件
- SQLiteバックアップ: 正常な直近2世代
- 最新市場CSV: 1件を原子的に置換
- リリース基準CSV: 明示的な版ごとに必要な1件
- 取得実行メタデータ: SQLite内に小さく保持
- 日次レポート履歴: 現在の日次1件規則を当面維持

### 7.2 容量制御

- 毎回の全履歴CSV新規作成を、最新CSVの原子的置換へ切り替える。
- `-wal` は正常終了時または閾値超過時にcheckpointする。
- `VACUUM` は毎回行わず、削除後の空き率またはDBサイズ閾値を満たす保守時だけ実行する。
- revision履歴は無条件削除しない。異常に多い系列を診断対象として報告する。
- 目標は「繰り返し全履歴保存と比べ80%以上小さいこと」かつ「同じ入力を再実行してDBサイズが実質増えないこと」とする。
- 実装時に 20年×100系列×日次値と、実データの両方で容量を測り、推測値ではなく結果を記録する。

### 7.3 バックアップと破損時動作

1. 書込み前にDBの起動時整合性を確認する。
2. スキーマ移行前と保持削除前にSQLite backup APIでバックアップする。
3. 新しいバックアップの整合性確認後にだけ、3世代目を削除する。
4. 本体破損時は自動上書きせず、最後の正常バックアップをread-onlyで検証する。
5. 復旧できない場合は最新互換CSVでレポート継続を試み、DB書込みを停止して診断を出す。
6. 最後の正常DB、最後の正常CSV、破損DBを同時に削除しない。

## 8. 設定案

実装時に既存設定ローダーへ、後方互換のある既定値として追加する。

```yaml
market_data_storage:
  mode: legacy_csv          # legacy_csv / shadow_sqlite / sqlite_primary
  revision_window_days: 90
  retention_enabled: false
  keep_full_snapshot_count: 2
  backup_count: 2
  integrity_check_on_start: true
  latest_csv_export: true
```

- 初期リリースでは `legacy_csv` または `shadow_sqlite` を既定にし、いきなりprimaryへしない。
- `retention_enabled` は照合完了までfalseを維持する。
- primary切替後もCSV fallbackと最新CSV exportを残す。
- 設定欠落時に安全でないprimaryや削除有効へ倒れない。

## 9. 詳細実装更新プラン

### Phase 0: 契約固定と基準取得

目的: 実装前の比較基準と変更禁止面を固定する。

作業:

- Git状態と既存未コミット変更を記録し、他タスクの変更を上書きしない。
- 現在の市場スナップショット件数、同日重複、サイズ、列、日付範囲をmanifest化する。
- 最新CSVと対応JSONのSHA-256を保存する。
- production判断の比較に使う既存fixtureと代表ケースを特定する。
- Risk Engine V2のshadow三条件と保護対象ファイルの値を検証用に固定する。
- 現在のレポート履歴日次整理は別問題として変更しない。

受入条件:

- 実装前後を比較できるmachine-readableな基準がある。
- 保護境界の変更が0件である。

### Phase 1: SQLiteコア層

主な追加候補:

- `project/market_data_provider.py`: 保存先解決、時刻、環境変数
- `project/market_data_store.py`: 接続、schema、transaction、insert/query、integrity、backup
- `project/tests/test_market_data_store.py`

作業:

- ヒンデンブルグDBの安全な既存パターンを共通設計の参考にする。
- schema migration、series登録、run登録、冪等upsert、revision追加を実装する。
- current/as-of queryを実装する。
- 一時DBでのみ単体テストする。
- 同時二重起動時はSQLite transactionとtimeoutで破損を防ぎ、無制限リトライしない。

受入条件:

- 同一入力2回で観測行数が増えない。
- 訂正値で旧revisionが残る。
- as-of queryが未来revisionを返さない。
- transaction途中の例外で部分登録が残らない。
- integrity check、backup、backup復元が通る。

### Phase 2: 既存CSV移行器

主な追加候補:

- `project/market_data_migration.py`
- `project/tests/test_market_data_migration.py`

作業:

- 最新検証済みCSVを一時DBへ取り込む。
- CSVのwide形式とDBのlong形式を双方向変換する。
- 列集合、index timezone、浮動小数点、NaN表現を明文化する。
- 再構成CSVのfingerprintを、正規化規則を通して比較する。
- 古い複数CSVの全取込はしない。初回は最新全履歴を基準にし、必要な過去取得時点は対応JSONから別途索引化する。

受入条件:

- 実スナップショットをコピーした一時データで全値一致する。
- 同じCSVの再取込が冪等である。
- 途中失敗時に既存CSVと既存DBが変化しない。
- migration結果から元の互換フレームを再構成できる。

### Phase 3: shadow dual-write

主な更新候補:

- `project/snapshot_store.py`
- `project/main.py`
- `project/pipeline.py`
- `project/config.yaml`
- 関連する既存テスト

作業:

- `shadow_sqlite` では既存CSV保存を維持したままSQLiteにも保存する。
- レポート生成の読み取り元はまだ既存CSV/FetchResultのままにする。
- 両者を再構成して、系列、日付、値、欠損、範囲、source metadataを照合する。
- 不一致は診断に出すが、既存production判断へ接続しない。
- DB失敗時はCSV側を壊さず、continue-on-errorの既存契約に沿って処理する。

受入条件:

- 同一取得結果からCSVとDBが一致する。
- DBを意図的に失敗させても既存レポート結果が変わらない。
- 連続実行でDBに重複行が増えない。
- final_action等の保護値がbaselineと一致する。

### Phase 4: shadow dual-read canary

作業:

- primary系処理は既存フレームを使いつつ、DBから同条件のフレームを読み、結果を比較する。
- 対象はまず1つの読み取り経路に限定する。
- 差異があれば日付、series、revision、source runまで追跡できる診断を出す。
- 最低でも通常、欠損、訂正、同日複数実行、破損DB、旧CSVのみのケースを通す。

受入条件:

- 代表fixtureと現在の実データで読み取り一致する。
- candidate側でproduction判断の不変性が確認できる。
- mismatchが0でない限りprimaryへ進まない。

### Phase 5: SQLite primaryと互換CSV

作業:

- `sqlite_primary` で市場時系列読み取りをDBへ切り替える。
- 成功transaction後にだけ最新CSVを一時ファイルから原子的置換する。
- DB読取失敗時は最後の正常DB、次に最新互換CSVの順で安全にfallbackする。
- fallback発生は明示し、黙って古いデータを最新扱いしない。
- threshold replay、reconstructed replay等の直接CSV参照はadapter経由に置換する。ただしCLIの `--input-prices` は検証・再現用として維持する。

受入条件:

- DB primaryと旧CSVの結果が一致する。
- fallback時のprovenanceが成果物に残る。
- 既存CLIの明示CSV入力が引き続き動く。
- Risk Engine V2のshadow契約とproduction判断が変わらない。

### Phase 6: 保持削減の有効化

前提: Phase 0-5の全ゲート、バックアップ復元、実データ照合が完了していること。

作業:

- まずdry-runで削除候補manifestを生成する。
- ユーザー確認後にのみ `retention_enabled=true` を検討する。
- 実行ごとの全履歴CSV新規作成を停止し、最新CSVの原子的置換へ移行する。
- 既存重複スナップショットは、SHA、DB取込済み、対応metadata、復元可能性を確認してから整理する。
- 最低限、最新正常CSV、リリース基準CSV、正常DB、DBバックアップ2世代を残す。

受入条件:

- 削除前後の復元テストが通る。
- 保持対象以外の削除が0件である。
- 30日相当の反復実行で全履歴ファイル数が増えない。
- DBの増加量が新規観測・実改訂に対応している。

### Phase 7: 年代記・分析利用

作業:

- 市場警戒年代記はイベント期間に必要なseriesと期間だけDBから取得する。
- ACWIを基準に、その局面で説明力のある最大4指標を追加し、合計最大5系列にする。
- 指標選定はpoint-in-timeデータ、利用可能率、変化量、異常度、局面との関連証拠で行う。
- 後知恵を避けるため、当時存在しなかったrevisionや未来データを選定に使わない。
- 選定series、revision、run_id、期間、理由、欠損を年代記JSONへ保存する。

受入条件:

- 同じepisode入力から選定が決定的に再現できる。
- 最大5系列を超えない。
- 不足時に無関係な指標で穴埋めしない。
- 保存形式変更が評価・production decision logicへ影響しない。

### Phase 8: 配布・長期運用検証

作業:

- PyInstaller onedirでクリーン初回起動を確認する。
- 旧版のCSVだけを持つ環境からのupgradeを確認する。
- DBを持つ次回起動、schema migration、backup復元を確認する。
- DB/WAL/backupが配布sourceやrelease zipへ混入しないことを確認する。
- セキュリティ/プライバシーチェックを実施する。
- 20年×100系列の合成データと現実データでサイズ、取込時間、照会時間を測定する。

受入条件:

- Codexなしで `run_main.bat` からDB初期化・更新・互換出力まで動く。
- clean install、upgrade、corruption fallbackが通る。
- 配布物に利用者DBやローカル履歴が入らない。
- 容量目標と許容起動時間を実測で満たす。

## 10. 検証マトリクス

| 領域 | 必須確認 |
|---|---|
| schema | 初回作成、再起動、段階migration、未知version拒否 |
| ingestion | 新規、同一再実行、訂正、欠損、競合、transaction rollback |
| parity | series、日付、値、NaN、範囲、fingerprint |
| point-in-time | future revision除外、指定時点再現 |
| recovery | integrity failure、backup、CSV fallback、古いデータ明示 |
| capacity | 同一実行で無増加、30日simulation、20年simulation |
| compatibility | 明示CSV入力、既存report、replay、年代記 |
| protection | final_action、閾値、buy policy、Risk Engine shadow三条件 |
| distribution | clean run、upgrade、release除外、秘密/個人データ非混入 |

実装中は変更箇所に直接関係するテストだけを各ループで実行する。Phaseの終端、primary切替、保持削除、配布前だけ検証範囲を広げる。

## 11. ゴールループ

実装は次の固定ループで進め、作業が増殖しないようにする。

1. **Goal**: 現在のPhaseの受入条件を1つの明確なゴールとして宣言する。
2. **Observe**: 必要なファイル、既存契約、baselineだけを読む。
3. **Change**: managerが当該Phaseの最小差分だけを書く。
4. **Verify**: 直接影響するテストと比較を一度まとめて行う。
5. **Compare**: 受入条件とbaselineに対する差分を機械的に判定する。
6. **Repair**: 失敗した項目だけを直し、影響する検証だけを再実行する。
7. **Close**: 証拠、未解決、次Phaseの開始条件を記録して終了する。

1 Phaseにつき修正ループは原則2回までとする。2回で収束しない、または保護境界・データ損失・parity mismatchに触れた場合は自動的に次へ進まず、原因と選択肢を提示して停止する。

## 12. 実装時の子エージェント分担

実装時に独立調査の価値が調整コストを上回る場合だけ使用する。managerが全書込み、統合、Git操作、最終判断を所有する。

### 推奨構成

- **manager**: 計画、guard/lease、全ファイル編集、統合、テスト、最終報告。
- **read-only探索役**: `snapshot_store.py`、取得経路、直接CSV参照箇所の限定inventory。変更は禁止。
- **read-onlyレビュー役**: schema、migration、fallback、保持削除の失敗モード確認。変更は禁止。
- **最終統合監査役**: primary切替や保持削減など高リスク節目だけ。日常修正の重複レビューには使わない。

### 運用規則

- 書込みを伴うマルチエージェント工程前にmanual mixed leaseを取得する。
- 子は子孫を起動しない。operator-only scriptを実行しない。
- 同じファイル群を複数の子へ重複調査させない。
- 子への入力は目的、対象ファイル、禁止事項、返却形式、停止条件だけに絞る。
- 子の結論をそのまま変更にせず、managerが現在の作業ツリーと照合して採否を決める。
- 完了時は自分のleaseだけをexact releaseし、session/lock残留がないことを確認する。

## 13. レート・コンテキスト効率化

- この文書を実装判断の起点にし、毎回背景を再説明しない。
- Phaseごとに必要なファイルだけを読む。全リポジトリ再探索はPhase 0で一度だけ行う。
- schema、移行、consumer一覧を別々の長文チャットへ重複展開しない。
- 変更前baselineと変更後結果は短いmachine-readable manifestで比較する。
- 単体テスト、統合テスト、配布確認を混ぜず、失敗箇所に対応する層だけ再実行する。
- storageが安定する前にブラウザ表示や画像調整を始めない。
- live取得はunit/migration検証に使わず、fixtureと現在のローカルスナップショットをコピーした一時領域で行う。
- 子エージェントは原則1人、独立した二系統の監査が必要なときだけ2人にする。
- routineな成功確認のためだけに高コストの最終監査役を使わない。
- 各Phase終端で「確認済み」「実装済み未確認」「ユーザー承認待ち」を分け、次回は未完了だけを読む。

## 14. 停止条件とユーザー確認点

次の場合は自動継続しない。

- CSVとDBの値、日付範囲、欠損、revision再現が一致しない。
- production判断または保護境界に差分が出る。
- 既存正常DB/CSVを失う可能性がある。
- 既存スナップショット削除、保持削減有効化へ進む。
- live取得、commit、push、tag、releaseが必要になる。
- 新しい配布依存を追加する必要が生じる。
- 2回の修正ループでPhaseの受入条件を満たさない。

## 15. 実装開始時の正確な再開点

1. この文書、`docs/risk_engine_v2_current_state.md`、Git状態を読む。
2. 現在の未コミット変更を所有者不明のユーザー変更として保持する。
3. 子エージェントを使うならguard/leaseを取得し、read-only scopeを固定する。
4. Phase 0のbaseline manifestを作る。
5. Phase 1のSQLiteコアと単体テストだけを実装する。
6. Phase 1受入条件が通るまで、Phase 2以降や既存CSV削除へ進まない。

最初の実装単位は「SQLiteコア + 一時DB単体テスト」であり、既存実行経路、取得範囲、レポート表示、production判断にはまだ接続しない。これにより、手戻りが起きても既存アプリ動作と利用者データに影響を与えない。

## 16. 実装進捗

### 2026-07-19 - Phase 0 / Phase 1

状態: 完了、focused-validation-passed。

- `docs/market_data_storage_baseline.json` に、実装前Git位置、12組の市場スナップショット、同日重複、最新CSV/metadataのSHA256、列・期間・容量、保護対象hashをmachine-readableに固定した。
- `project/market_data_provider.py` に、標準保存先と環境変数overrideを追加した。
- `project/market_data_store.py` に、未来schema拒否、一方向schema初期化、系列定義、取得run、append-only revision、current/as-of読取、有限busy待ち、transaction rollback、全行integrity check、SQLite backup APIによる検証付きbackup/restoreを実装した。
- 同一fingerprint再実行、同値再取込、A→B→A訂正、欠損維持、batch競合、NaN/未来日付、途中失敗rollback、write lock、backup復元を一時DBだけで確認した。
- Phase 1 focused testsは、Phase 2との統合後に関連42件pass、Black/Ruff/mypy/compileall pass。既存CSV、既存metadata、利用者DB、取得経路、production判断は変更していない。

次の開始条件: Phase 2のCSV移行器を実装し、最新検証済みCSVのコピーから再構成したwide frameが列、日付、値、NaN、fingerprintで一致することを一時領域で証明する。一致後に限り、既存CSVを残したまま標準保存先へshadow初回移行する。

### 2026-07-19 - Phase 2

状態: shadow初回移行完了、focused-validation-passed。primary切替と保持削減は未承認・未実施。

- `project/market_data_migration.py` に、legacy CSV/metadataのSHA検証、wide/long正規化、Asia/Tokyoの旧naive取得時刻のUTC正規化、一時候補DBへの取込、系列集合・日付集合・件数を含む完全parity、integrity検査、合格候補だけのno-clobber配置を実装した。
- fixtureでは完全往復、同一入力no-change、誤SHA、重複日、全欠損日、parity注入失敗、未知の既存DBを変更せず拒否、配置競合時の相手DB保持、古い・同時刻の訂正拒否を確認した。
- 実CSV canaryは48系列、13,009日、142,884非欠損値、1971-01-08から2026-07-17まで完全一致した。再実行はDB SHAが変わらない`no_change`だった。
- 同じ検証済み入力を標準保存先へshadow移行した。既存DBは存在しなかったため上書きやbackup対象はなく、元CSV/metadataはbyte-identicalで残っている。結果は`docs/market_data_storage_migration_result.json`に保存した。
- 標準DBの再検証はimmutable read-only接続で行い、再実行後もDB SHAはbyte-identical、WAL/SHM副作用は0件だった。
- 最終focused validationは関連42件pass、Black/Ruff/mypy/compileall pass。最終監査指摘の「未知DB初期化」「新規作成競合」「配置競合上書き」「時系列逆行revision」「部分集合parity」「全欠損系列parity」はすべてfail-closedまたは完全往復へ修正した。
- 初期DBは54,616,064 bytesで、現在の12組のsnapshot archive 29,051,227 bytesより大きい。この時点では容量目標を満たしていないため、retention、旧snapshot削除、SQLite primary、既存読取経路の切替は行わない。

次の開始条件: Phase 3でshadow dual-writeを実装する前に、row表現、hash/qualityの重複格納、index構成を実測し、revision/as-of契約を損なわず初期DB容量を改善する。または、現在サイズを許容する明示判断と長期simulationの合格証拠を得る。いずれの場合も既存CSV経路を維持したまま進める。
