from __future__ import annotations

from project.report_generator import render_html, render_markdown



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
        },
        "cycle": {"phase_label": "upswing", "phase_angle_deg": 10},
        "score": {"total_score": 0.7, "credit_stress_component": 0.62},
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
            "action": "buy_window",
            "second_leg_risk": "low",
            "adjusted_score": 0.7,
            "regime_penalty": 0.0,
            "risk_off_relief_applied": False,
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
    assert "\n## サマリー\n" in text
    assert "データ取得状況" in text
    assert "接続診断" in text
    assert "fc.yahoo.com" in text
    assert "生活必需品" in text
    assert "ラベル 有望" in text
    assert "米国大型株ETF" in text
    assert "信用監視" in text
    assert "インフレ監視" in text
    assert "米国ハイイールド債ETF" in text
    assert "WTI原油先物" in text
    assert "信用収縮警戒" in text
    assert "判定理由" in text
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
    assert "- 判定用スコア: 0.7" in text
    assert "内部警告件数" in text
    assert "危険ライン段階とは別の判定" in text
    assert '<span style="color:#1f2933;"><strong>信用波及初期</strong></span>' in text


def test_render_html_contains_japanese_explanations():
    html = render_html(_report())
    assert "市場レジーム" in html
    assert "データ取得状況" in html
    assert "接続診断" in html
    assert "配布 exe" in html
    assert "代替ティッカーで取得" in html
    assert "生活必需品" in html
    assert "簡易ローテーション図" in html
    assert "sector-arrow" in html
    assert "正規化長" in html
    assert "有望" in html
    assert "米国大型株ETF" in html
    assert "S&amp;P500連動ETF" in html
    assert "信用監視" in html
    assert "インフレ監視" in html
    assert "米国ハイイールド債ETF" in html
    assert "WTI原油先物" in html
    assert "信用収縮警戒" in html
    assert "判定理由" in html
    assert "投資候補" in html
    assert "観察候補" in html
    assert "先回り候補" in html
    assert "仕込み候補" in html
    assert "レジーム先回り候補" in html
    assert "公益事業セクターETF" in html
    assert "日本株ETF" in html
    assert "金ETF" in html
    assert "危険ライン監視" in html
    assert "信用波及初期" in html
    assert "VIX指数" in html
    assert "警告レイヤー" in html
    assert "生活コスト上昇警戒" in html
    assert "信用ストレス補助 0.62" in html
    assert "判定用スコアは 0.70" in html
    assert "レジーム減点 0.0" in html
    assert "内部警告件数" in html
    assert "危険ライン段階とは別の判定" in html
    assert "risk-badge caution" in html
