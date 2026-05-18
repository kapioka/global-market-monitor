from __future__ import annotations

from project.report_generator import render_html, render_markdown, render_supplement_dashboard_html



def _report() -> dict:
    return {
        "title": "Test Report",
        "generated_at": "2026-03-19T21:00:00",
        "data_source": "sample",
        "runtime_context": {
            "is_frozen": True,
            "python_executable": r"E:\dist\GlobalMarketMonitor\GlobalMarketMonitor.exe",
            "working_directory": r"E:\dist\GlobalMarketMonitor",
        },
        "fetch_diagnostics": {
            "summary": {
                "source": "sample",
                "failed_attempt_count": 2,
                "suspected_network_issue": True,
            },
            "suspected_hosts": ["fc.yahoo.com"],
            "failure_samples": ["Failed to connect to fc.yahoo.com port 443"],
        },
        "regime": {
            "regime_label": "risk_on",
            "trend_strength": 30.0,
            "momentum_12w": 0.12,
            "max_drawdown": -0.05,
            "credit_regime_flag": "neutral",
            "sector_adjustment_explain": [{"signal": "cap", "delta": 0.02}, {"signal": "single_sector_dominance_warning", "delta": -0.01, "strength": "weak"}],
        },
        "cycle": {"phase_label": "upswing", "phase_angle_deg": 10},
        "score": {"total_score": 0.7, "credit_stress_component": 0.62, "sector_integration_explain": [{"signal": "cap", "delta": -0.03}, {"signal": "broad_improvement", "delta": 0.14}]},
        "risk_thresholds": {"version": "2026-04-05-active-v1", "generated_at": "2026-04-05T12:00:00+09:00"},
        "risk_threshold_drift": {"summary": {"stable_count": 7, "watch_count": 2, "review_count": 1, "unavailable_count": 0, "review_targets": ["^VIX:danger"]}},
        "risk_threshold_review": {"status": "review", "review_recommended": True, "reasons": ["recalibration_due:120d", "drift_review_targets:^VIX:danger"]},
        "risk_threshold_maintenance": {"status": "completed", "elapsed_seconds": 2.4, "proposal_generated_this_run": True},
        "risk_lines": {
            "stage_key": "credit_spillover_initial",
            "stage_label": "信用波及初期",
            "summary": "かなり悪化したが、まだ全面的な信用危機本番ではなく、金利・原油ショックが信用へ波及し始めた段階です。",
            "composite_risk_score": 48.2,
            "danger_count": 1,
            "extreme_count": 0,
            "reasons": ["インフレショック、金利上昇、株安の組み合わせが同時進行しています。"],
            "indicators": [
                {
                    "ticker": "^VIX",
                    "ticker_name_ja": "VIX指数",
                    "current": 29.9,
                    "change_1w": 0.08,
                    "change_4w": 0.12,
                    "zscore": 1.4,
                    "line_level_label": "警戒ライン接近",
                    "warning_line": 25.0,
                    "danger_line": 30.0,
                    "extreme_line": 35.0,
                    "line_reason": "現在値 29.90 を基準ラインと比較した判定です。",
                }
            ],
        },
        "spot_signal": {
            "action": "watch",
            "legacy_action": "buy_window",
            "second_leg_risk": "low",
            "adjusted_score": 0.7,
            "legacy_adjusted_score": 0.7,
            "regime_penalty": 0.0,
            "risk_off_relief_applied": False,
            "recovery_evidence": {"score": 0.74, "grade": "confirmed", "summary": "回復確認は強めです。"},
            "blocker_assessment": {"level": "caution", "summary": "まだ騙し上昇を警戒して買い判断を抑えるべき状態です。"},
            "action_decision": {
                "raw_action": "buy_window",
                "action": "watch",
                "raw_confidence": 0.74,
                "confidence": 0.45,
                "confidence_cap": 0.45,
                "reliability_cap_applied": True,
                "cap_reason": ["sample_fallback_present"],
                "max_action": "watch",
                "mode": "evidence_building_with_caution_capped_by_reliability",
            },
            "sector_adjustment_explain": [{"signal": "cap", "delta": -0.01}, {"signal": "cyclical_improving", "delta": 0.01}],
            "rationale": [
                "市場レジームは risk_on です。",
                "サイクル位相は upswing です。",
                "合成スコアは 0.70 です。",
                "レジーム減点はなく、判定用スコアは 0.70 です。",
                "信用面では HYG/LQD 比率が改善しており、信用環境は持ち直し寄りです。",
                "インフレ面では大きな加速はまだ見えず、継続監視の段階です。",
            ],
        },
        "sector_rotation": {
            "table": [
                {
                    "ticker": "XLP",
                    "sector_name_ja": "生活必需品",
                    "return_12w": 0.03,
                    "rank": 1,
                    "rotation_phase": "leading",
                    "rotation_phase_ja": "先導",
                }
            ],
            "history": [
                {
                    "sector": "XLP",
                    "x_2w_ago": -0.3,
                    "y_2w_ago": 0.2,
                    "x_1w_ago": 0.1,
                    "y_1w_ago": 0.6,
                    "x_current": 0.55,
                    "y_current": 1.0,
                    "avg_length_12w": 0.45,
                }
            ],
        },
        "internal_structure": {"structure_label": "Broad Improvement", "reason": "複数セクターで改善が広がっています。", "structure": {"breadth": "broad", "leadership": "balanced", "stability": "stable"}, "structure_detail": {"consistency": "aligned", "momentum_quality": "stable"}, "dominant_sector": "XLP", "dominance_strength": "weak", "dominance_components": {"concentration": "medium", "breadth_deficit": "medium", "top_gap": "high"}, "dominance_reason_short": "少数セクターへ資金が集まっています、裾野の広がりはやや不足しています、先頭セクターの優位が明確です", "single_sector_dominance": True, "dispersion_score": 0.56, "watch_share": 0.75, "promising_share": 0.25, "counts": {"promising": 1, "watch": 0, "wait": 0, "peakout": 0}},
        "next_candidates": [{"ticker": "XLP", "sector_name_ja": "生活必需品", "candidate_label": "有望"}],
        "peakout_sectors": [{"ticker": "XLE", "sector_name_ja": "エネルギー", "candidate_label": "失速警戒"}],
        "market_structure_comment": "複数セクターで改善が広がっており、内部の裾野が広がっています。",
        "asset_compare": [
            {
                "asset_class": "US_Stocks",
                "ticker": "SPY",
                "ticker_name_ja": "米国大型株ETF",
                "momentum_12w": 0.12,
                "annualized_volatility": 0.2,
                "max_drawdown": -0.1,
            }
        ],
        "credit_monitor": [
            {
                "ticker": "HYG",
                "ticker_name_ja": "米国ハイイールド債ETF",
                "current": 79.8,
                "change_1w": -0.006,
                "change_4w": -0.012,
                "change_12w": 0.021,
                "zscore": -0.8,
                "signal_label": "弱含み",
            },
            {
                "ticker": "HYG/LQD",
                "ticker_name_ja": "ハイイールド債/投資適格債 比率",
                "current": 0.737,
                "change_1w": -0.007,
                "change_4w": -0.016,
                "change_12w": 0.005,
                "zscore": -1.1,
                "signal_label": "信用収縮警戒",
            },
        ],
        "inflation_monitor": [
            {
                "ticker": "CL=F",
                "ticker_name_ja": "WTI原油先物",
                "current": 82.4,
                "change_1w": 0.021,
                "change_4w": 0.076,
                "change_12w": 0.102,
                "zscore": 1.3,
                "signal_label": "インフレ圧力上昇",
            }
        ],
        "japan_risk": {
            "available": True,
            "level": "moderate",
            "flags": ["yen_weakness"],
            "summary": "USDJPY は円安進行です。外貨資産では SPY の4週円建てリターンが 0.04、為替寄与が 0.02 です。",
            "usd_jpy": {
                "ticker": "USDJPY=X",
                "ticker_name_ja": "米ドル円",
                "current": 150.2,
                "change_1w": 0.01,
                "change_4w": 0.04,
                "change_12w": 0.08,
                "zscore": 1.2,
                "signal_label": "円安進行",
            },
            "foreign_assets": [
                {
                    "asset_class": "US_Stocks",
                    "ticker": "SPY",
                    "ticker_name_ja": "米国大型株ETF",
                    "usd_return_4w": 0.02,
                    "jpy_return_4w": 0.04,
                    "fx_contribution_4w": 0.02,
                    "jpy_max_drawdown": -0.08,
                    "signal_label": "円安寄与が大きい",
                }
            ],
        },
        "analogues": [],
        "investment_candidates": {
            "tier": "watch",
            "label": "観察候補",
            "summary": "まだ強い推奨ではないものの、追う価値のある候補です。",
            "preferred_asset_class": {
                "asset_class": "US_Stocks",
                "ticker": "SPY",
                "ticker_name_ja": "米国大型株ETF",
                "momentum_12w": 0.12,
            },
            "preferred_sector": {
                "ticker": "XLP",
                "sector_name_ja": "生活必需品",
                "return_12w": 0.03,
                "rotation_phase_ja": "先導",
            },
            "candidate_tickers": [
                {"ticker": "SPY", "label": "米国大型株ETF", "kind": "asset"},
                {"ticker": "XLP", "label": "生活必需品", "kind": "sector"},
            ],
            "rationale": ["スポット投資判断は buy_window です。"],
        },
        "recovery_candidates": {
            "tier": "build",
            "label": "仕込み候補",
            "summary": "下落後の反転初期として監視したい候補があります。",
            "preferred_asset_class": {
                "label": "Gold",
                "ticker": "GLD",
                "ticker_name_ja": "金ETF",
                "momentum_4w": 0.03,
            },
            "preferred_sector": {
                "ticker": "XLV",
                "ticker_name_ja": "ヘルスケアセクターETF",
                "momentum_4w": 0.028,
            },
            "candidate_tickers": [
                {"ticker": "GLD", "label": "金ETF", "kind": "asset"},
                {"ticker": "XLV", "label": "ヘルスケアセクターETF", "kind": "sector"},
            ],
            "rationale": ["資産候補 GLD は 4週 +0.0300、12週 -0.0200、最大DD -0.1400 です。"],
        },
        "regime_leading_candidates": {
            "tier": "priority",
            "label": "レジーム先回り候補",
            "summary": "次のレジームで効きやすい資産・地域・セクターの候補があります。",
            "preferred_sector": {
                "ticker": "XLU",
                "ticker_name_ja": "公益事業セクターETF",
                "momentum_4w": 0.021,
                "momentum_12w": 0.012,
            },
            "preferred_region": {
                "ticker": "EWJ",
                "ticker_name_ja": "日本株ETF",
                "momentum_4w": 0.02,
                "momentum_12w": 0.015,
            },
            "preferred_asset_class": {
                "ticker": "GLD",
                "ticker_name_ja": "金ETF",
                "momentum_4w": 0.019,
                "momentum_12w": 0.011,
            },
            "candidate_tickers": [
                {"ticker": "XLU", "label": "公益事業セクターETF", "kind": "sector", "reason": "改善で4週改善、12週は過熱前"},
                {"ticker": "EWJ", "label": "日本株ETF", "kind": "region", "reason": "地域全体で短期改善、まだ過熱前"},
                {"ticker": "GLD", "label": "金ETF", "kind": "asset", "reason": "資産クラスで短期改善、まだ過熱前"},
            ],
            "rationale": ["現レジーム transition に対して XLU はテーマ相性 1.00 です。"],
        },
        "alerts": [
            {
                "id": "living_cost_pressure",
                "category": "life",
                "severity": "moderate",
                "title": "生活コスト上昇警戒",
                "message": "資源価格と為替の影響で生活関連コストの上振れに注意が必要です。",
                "evidence": ["CL=F", "DX-Y.NYB"],
                "source_flags": ["inflation_shock_broad"],
            }
        ],
        "warnings": [],
        "data_reliability": {
            "level": "medium",
            "decision_allowed": True,
            "live_ratio": 0.75,
            "max_action": "watch",
            "confidence_cap": 0.45,
            "proxy_fallback_count": 1,
            "sample_fallback_count": 1,
            "unavailable_count": 0,
            "critical_failures": ["ACWI"],
            "reason_code": "sample_fallback_present",
            "reason": "一部系列にサンプル代替が含まれるため、buy_window は抑制します。",
        },
        "data_availability": [
            {
                "requested_ticker": "SPY",
                "requested_ticker_name_ja": "米国大型株ETF",
                "used_ticker": "VOO",
                "used_ticker_name_ja": "S&P500連動ETF",
                "status": "proxy_fallback",
                "provider": "yfinance",
                "message": "proxy fallback used: VOO",
                "alternatives": ["VOO", "IVV"],
                "alternatives_name_ja": ["S&P500連動ETF", "S&P500連動ETF"],
            }
        ],
    }


def test_render_markdown_uses_real_newlines():
    text = render_markdown(_report())
    assert "`n" not in text
    assert "## まず見る要約" in text
    assert "- 最終判断: 監視" in text
    assert "危険ライン trigger path" in text
    assert "\n## サマリー\n" in text
    assert "データ取得状況" in text
    assert "接続診断" in text
    assert "fc.yahoo.com" in text
    assert "生活必需品" in text
    assert "ラベル 有望" in text
    assert "セクターローテーション内部構造" in text
    assert "市場内部構造コメント" in text
    assert "次候補セクター" in text
    assert "失速警戒セクター" in text
    assert "補助反映要約" in text
    assert "レジーム: 単独主導警戒 / 強度=弱 / 減点=-0.01" in text
    assert "総合評価: 広がり改善 / 加点=+0.14" in text
    assert "スポット判定: 景気敏感改善 / 加点=+0.01" in text
    assert "内部構造要約: 裾野は広い / 主導は分散 / 動きは継続" in text
    assert "単独主導理由: 少数セクターへ資金が集まっています、裾野の広がりはやや不足しています、先頭セクターの優位が明確です" in text
    assert "相対広がり指標: watch_share=0.75 / promising_share=0.25" in text
    assert "相対広がり要約: 裾野は十分 / 有望比率は中程度" in text
    assert "単独主導内訳: 集中=中 / 裾野不足=中 / 先頭優位=高" in text


def test_render_html_includes_first_read_summary():
    text = render_markdown(_report())
    html = render_html(_report())

    assert "first-read-summary" in html
    assert "まず見る要約" in html
    assert "米国大型株ETF" in text
    assert "信用監視" in text
    assert "インフレ監視" in text
    assert "円建て・為替リスク" in text
    assert "USDJPY=X" in text
    assert "円安寄与が大きい" in text
    assert "米国ハイイールド債ETF" in text
    assert "WTI原油先物" in text
    assert "信用収縮警戒" in text
    assert "判定理由" in text
    assert "live 取得率: 75%" in text
    assert "データ品質上限: 監視継続 / confidence 上限 0.45" in text
    assert "代替取得内訳: proxy=1 / sample=1 / unavailable=0" in text
    assert "重要系列不足: ACWI" in text
    assert "データ品質による降格: あり / 理由 sample_fallback_present" in text
    assert "投資候補" in text
    assert "観察候補" in text
    assert "先回り候補" in text
    assert "仕込み候補" in text
    assert "レジーム先回り候補" in text
    assert "公益事業セクターETF" in text
    assert "日本株ETF" in text
    assert "金ETF" in text
    assert "危険ライン監視" in text
    assert "信用波及初期" in text
    assert "VIX指数" in text
    assert "警告レイヤー" in text
    assert "生活影響警告 / 注意" in text
    assert "信用環境は持ち直し寄りです。" in text
    assert "判定用スコアは 0.70" in text
    assert "- legacy 判定用スコア: 0.7" in text
    assert "- 上昇再開の証拠: confirmed (0.74)" in text
    assert "- 騙し上昇の警戒: caution" in text
    assert "- 新判断: 監視継続" in text
    assert "- legacy スポット投資判断: 買い検討ゾーン" in text
    assert "- 最終判断: 監視継続 / mode evidence_building_with_caution" in text
    assert "内部警告件数" in text
    assert "危険ライン段階とは別の判定" in text
    assert '<span style="color:#1f2933;"><strong>信用波及初期</strong></span>' in text


def test_render_html_contains_japanese_explanations():
    html = render_html(_report())
    assert "市場レジーム" in html
    assert "補足ダッシュボード" in html
    assert "スポット投資判断" in html
    assert "セクター概要" in html
    assert "アラートレイヤー" in html
    assert "データ健全性" in html
    assert "データ品質上限" in html
    assert "proxy=1 / sample=1 / unavailable=0" in html
    assert "sample_fallback_present" in html
    assert "しきい値提案" in html
    assert "上昇再開 確認済み / 警戒 注意" in html
    assert "上昇再開の証拠" in html
    assert "騙し上昇の警戒" in html
    assert "レジーム減点はなく、判定用スコアは 0.70" in html
    assert "ステータス<strong>要確認</strong>" in html
    assert "<div class=\"l\">安定</div>" in html
    assert "<div class=\"l\">監視</div>" in html
    assert "<div class=\"l\">要確認</div>" in html
    assert "<div class=\"l\">未取得</div>" in html
    assert "しきい値レビュー" in html
    assert "先回り候補" in html
    assert "レジーム先回り" in html
    assert "生活コスト上昇警戒" in html
    assert "legacy 買い検討ゾーン" in html
    assert "レジーム減点 0.0" in html
    assert "補足レポート 以下は監査性と詳細確認" not in html
    assert "<section class=\"section\">" not in html
    assert "historyEmbedPayload" not in html
    assert "threshold proposal" not in html


def test_render_supplement_dashboard_html_maps_all_source_sections():
    html = render_supplement_dashboard_html(_report())
    assert "補足レポート ダッシュボード" in html
    assert "report.html" in html
    assert "履歴" in html
    assert "判定" in html
    assert "セクター" in html
    assert "市場監視" in html
    assert "監査" in html
    assert "データ品質上限" in html
    assert "live 75%" in html
    assert "元:" not in html
    for section in [
        "過去履歴ブラウズ",
        "セクターローテーション",
        "判定理由",
        "危険ライン監視",
        "投資候補",
        "先回り候補",
        "レジーム先回り候補",
        "セクターローテーション内部構造",
        "資産クラス比較",
        "信用監視",
        "インフレ監視",
        "円建て・為替リスク",
        "警告レイヤー",
        "類似局面",
        "データ取得状況",
        "接続診断",
        "警告",
    ]:
        assert section in html
    assert "supplementHistoryPayload" in html
    assert "SPY" in html
    assert "HYG/LQD" in html
    assert "USDJPY=X" in html
    assert "生活コスト上昇警戒" in html
