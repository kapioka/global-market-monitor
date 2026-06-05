from __future__ import annotations

from copy import deepcopy

import pytest

from project.japan_resident_integrated_context import build_japan_resident_integrated_risk_context
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
            "sector_adjustment_explain": [
                {"signal": "cap", "delta": 0.02},
                {"signal": "single_sector_dominance_warning", "delta": -0.01, "strength": "weak"},
            ],
        },
        "cycle": {"phase_label": "upswing", "phase_angle_deg": 10},
        "score": {
            "total_score": 0.7,
            "credit_stress_component": 0.62,
            "sector_integration_explain": [{"signal": "cap", "delta": -0.03}, {"signal": "broad_improvement", "delta": 0.14}],
        },
        "risk_thresholds": {"version": "2026-04-05-active-v1", "generated_at": "2026-04-05T12:00:00+09:00"},
        "risk_threshold_drift": {
            "summary": {"stable_count": 7, "watch_count": 2, "review_count": 1, "unavailable_count": 0, "review_targets": ["^VIX:danger"]}
        },
        "risk_threshold_review": {
            "status": "review",
            "review_recommended": True,
            "reasons": ["recalibration_due:120d", "drift_review_targets:^VIX:danger"],
        },
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
        "risk_line_confidence_audit": {
            "status": "display_only",
            "monitoring_scope_label": "米国・グローバル中心の危険監視",
            "fallback_review_rules": 10,
            "low_precision_rules": 7,
            "pass_rules": 2,
            "dxy_role": {"label": "米ドル指数は米国・グローバルのドル高ストレス確認に使います。"},
            "jpy_fx_role": {"label": "USDJPY/EURJPY は日本円で見た外貨建て資産の円換算影響確認に使います。"},
            "composite_trigger_relationship": "総合ストレス指数 48.2 は trigger path に含まれ、段階判定の補助根拠として表示されます。",
            "must_not_affect_final_action": True,
            "must_not_change_threshold_json": True,
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
        "buy_decision_card": {
            "final_action": "watch",
            "market_raw_action": "buy_window",
            "risk_adjusted_action": "watch",
            "buy_readiness_score": 72,
            "readiness_level": "near_candidate",
            "primary_blocker": "fx_risk",
            "secondary_blockers": ["sample_only"],
            "unlock_conditions": [
                {
                    "condition": "foreign_asset_fx_headwind の解消",
                    "target_state": "headwind flag clears",
                    "reason": "FX caution is the primary blocker.",
                },
                {
                    "condition": "USDJPY 4w change の沈静化",
                    "target_state": "change returns within threshold",
                    "reason": "FX shock should be rechecked before any candidate review.",
                },
            ],
            "confirmation_conditions_label": "次に確認する条件",
            "readiness_score_note": (
                "buy_readiness_score is not a probability, expected return, or success rate. "
                "It only explains how many buy-decision conditions are aligned."
            ),
            "sample_only_note": "sample-only のため final_action は wait に固定されています。",
            "affects_final_action": False,
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
        "internal_structure": {
            "structure_label": "Broad Improvement",
            "reason": "複数セクターで改善が広がっています。",
            "structure": {"breadth": "broad", "leadership": "balanced", "stability": "stable"},
            "structure_detail": {"consistency": "aligned", "momentum_quality": "stable"},
            "dominant_sector": "XLP",
            "dominance_strength": "weak",
            "dominance_components": {"concentration": "medium", "breadth_deficit": "medium", "top_gap": "high"},
            "dominance_reason_short": "少数セクターへ資金が集まっています、裾野の広がりはやや不足しています、先頭セクターの優位が明確です",
            "single_sector_dominance": True,
            "dispersion_score": 0.56,
            "watch_share": 0.75,
            "promising_share": 0.25,
            "counts": {"promising": 1, "watch": 0, "wait": 0, "peakout": 0},
        },
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
                {"ticker": "XLK", "label": "情報技術セクターETF", "kind": "sector"},
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


def _multi_asset_payload() -> dict:
    return {
        "title": "資産クラス別の確認候補",
        "summary": "株式・ゴールド・債券・現金待機を、同じ買い候補度に混ぜず役割別に整理します。",
        "disclaimer": "これは買い推奨ではなく、現在の市場状態を資産クラス別に整理したものです。外貨建て資産は為替の影響を受けます。",
        "affects_final_action": False,
        "affects_buy_readiness_score": False,
        "candidates": [
            {
                "asset_class": "equity",
                "asset_class_label": "株式候補",
                "symbol": "SPY",
                "display_name": "米国大型株ETF",
                "role": "growth",
                "role_label": "成長を取りに行く候補",
                "status": "candidate",
                "reason": "既存の資産比較で株式の相対状況を確認します。",
                "caution": "既存の最終判断を上書きしません。",
                "source_data_available": True,
                "metrics": {"momentum_12w": 0.12},
            },
            {
                "asset_class": "gold",
                "asset_class_label": "守り候補",
                "symbol": "GLD",
                "display_name": "金ETF",
                "role": "defensive",
                "role_label": "不安定時の守り候補",
                "status": "watch",
                "reason_category": "defensive_context",
                "reason": "株式と同じ買い候補度ではなく確認します。",
                "caution": "為替や商品価格の影響を受けます。",
                "caution_required": True,
                "must_not_affect_final_action": True,
                "must_not_affect_buy_readiness_score": True,
                "source_data_available": True,
                "metrics": {"momentum_12w": 0.04},
            },
            {
                "asset_class": "bond",
                "asset_class_label": "債券候補",
                "symbol": "AGG",
                "display_name": "総合債券ETF",
                "role": "diversification",
                "role_label": "金利低下・リスク回避時の確認候補",
                "status": "unavailable",
                "reason_category": "insufficient_data",
                "reason": "分散候補として扱います。",
                "caution": "株式候補とは別枠で見ます。",
                "caution_required": True,
                "must_not_affect_final_action": True,
                "must_not_affect_buy_readiness_score": True,
                "source_data_available": False,
                "metrics": {"momentum_12w": 0.02},
                "japan_resident_context_score": 12,
                "japan_resident_context_status": "unavailable",
                "japan_resident_reason_category": "insufficient_data",
                "japan_resident_context_components": {
                    "data_quality": 0,
                    "jpy_relevance": 3,
                    "domestic_rate": 0,
                    "fx": -8,
                    "inflation": 0,
                },
                "japan_resident_must_not_affect_final_action": True,
                "japan_resident_must_not_affect_buy_readiness_score": True,
            },
            {
                "asset_class": "jp_equity",
                "asset_class_label": "日本株候補",
                "symbol": "1306.T",
                "display_name": "TOPIX連動ETF",
                "role": "jp_growth",
                "role_label": "日本株の確認候補",
                "status": "informational",
                "reason_category": "jp_equity_context",
                "reason": "日本株を外貨建て株式と分けて確認します。",
                "caution": "日本株も市場全体の下落を受けます。",
                "caution_required": True,
                "must_not_affect_final_action": True,
                "must_not_affect_buy_readiness_score": True,
                "source_data_available": True,
                "metrics": {"current_value": 103.0, "change_4w": -3.7, "change_12w": -5.1, "trend_label": "weakening"},
                "japan_resident_context_score": 43,
                "japan_resident_context_status": "informational",
                "japan_resident_reason_category": "jp_equity_context",
                "japan_resident_context_components": {
                    "data_quality": 20,
                    "jpy_relevance": 15,
                    "domestic_rate": 0,
                    "fx": 0,
                    "inflation": 0,
                },
                "japan_resident_must_not_affect_final_action": True,
                "japan_resident_must_not_affect_buy_readiness_score": True,
            },
            {
                "asset_class": "bond_jpy",
                "asset_class_label": "円建て債券候補",
                "symbol": "JGB_CONTEXT",
                "display_name": "円建て債券確認",
                "role": "jpy_defensive",
                "role_label": "円建て守り候補",
                "status": "unavailable",
                "reason_category": "jpy_rate_context",
                "reason": "国内金利と円建て資産の確認用です。",
                "caution": "円建て債券も金利上昇時に価格が下がることがあります。",
                "caution_required": True,
                "must_not_affect_final_action": True,
                "must_not_affect_buy_readiness_score": True,
                "source_data_available": False,
                "metrics": {"limitations": ["missing_series"]},
                "japan_resident_context_score": 15,
                "japan_resident_context_status": "unavailable",
                "japan_resident_reason_category": "insufficient_data",
                "japan_resident_context_components": {
                    "data_quality": 0,
                    "jpy_relevance": 15,
                    "domestic_rate": -3,
                    "fx": 0,
                    "inflation": 0,
                },
                "japan_resident_must_not_affect_final_action": True,
                "japan_resident_must_not_affect_buy_readiness_score": True,
            },
            {
                "asset_class": "cash",
                "asset_class_label": "現金待機",
                "symbol": "CASH",
                "display_name": "現金待機",
                "role": "wait",
                "role_label": "条件がそろうまで待つ選択",
                "status": "wait",
                "reason_category": "wait_context",
                "reason": "条件がそろうまで待つ選択肢として表示します。",
                "caution": "無理に資産候補へ振り分けません。",
                "caution_required": True,
                "must_not_affect_final_action": True,
                "must_not_affect_buy_readiness_score": True,
                "source_data_available": True,
                "metrics": {},
            },
        ],
        "inventory": [],
    }


def _integrated_context_payload() -> dict:
    return build_japan_resident_integrated_risk_context(
        {
            "risk_lines": {
                "stage_key": "credit_spillover_initial",
                "stage_label": "信用波及初期",
                "summary": "米国・グローバルの危険ラインは注意段階です。",
                "composite_risk_score": 48.2,
            },
            "risk_line_confidence_audit": {
                "monitoring_scope_label": "米国・グローバル中心の危険監視",
                "dxy_role": {"label": "米ドル指数は米国・グローバルのドル高ストレス確認に使います。"},
                "jpy_fx_role": {"label": "USDJPY/EURJPY は日本円で見た外貨建て資産の円換算影響確認に使います。"},
            },
            "domestic_danger_context": {
                "domestic_danger_level": "watch",
                "domestic_danger_reasons": ["MOF JGB利回りは国内金利の補助危険確認に使われます。"],
                "domestic_watch_items": [
                    {
                        "group": "円建て債券",
                        "asset_group": "bond_jpy",
                        "name": "円建て債券確認",
                        "level": "watch",
                        "reason": "円建て債券は国内金利と価格推移を分けて補助確認します。",
                        "source": "multi_asset_candidates",
                    },
                    {
                        "group": "為替確認",
                        "asset_group": "fx",
                        "name": "米ドル円",
                        "level": "caution",
                        "reason": "USDJPY=X の実変化で外貨建て資産の円換算影響を確認します。",
                        "source": "japan_risk",
                    },
                ],
                "domestic_data_limitations": ["CPI は manual_file_missing のため補助危険値として扱いません。"],
            },
            "japan_risk": {"level": "moderate", "summary": "USDJPY=X は円建て換算影響の確認対象です。"},
            "japan_resident_context": {
                "jgb_yields": {"jgb_10y": 1.7},
                "macro_sources": {
                    "japan_cpi": {"status": "manual_file_missing"},
                    "boj_domestic_short_rate": {"status": "endpoint_not_resolved"},
                },
            },
        }
    )


def test_render_markdown_uses_real_newlines():
    text = render_markdown(_report())
    assert "`n" not in text
    assert "## まず見る要約" in text
    assert "Buy Decision Card / 買い判断カード" in text
    assert "成功確率・期待リターン・投資成功率ではありません" in text
    assert "TimesFM" not in text
    assert "- 最終判断: 監視" in text
    assert "危険ライン trigger path" in text
    assert "信頼度監査: 米国・グローバル中心の危険監視" in text
    assert "fallback_review=10 / low_precision=7 / pass=2" in text
    assert "DXY と円建てFX" in text
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

    assert "glance-summary" in html
    assert "まず見るポイント" in html
    assert "買い判断カード" in html
    assert "初心者向けひとこと" in html
    assert "これは成功確率ではありません" in html
    assert "SPY" in html
    assert "XLK" in html
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
    assert "米国・グローバル中心の危険監視" in html
    assert "米ドル指数は米国・グローバルのドル高ストレス確認に使います。" in html
    assert "USDJPY/EURJPY は日本円で見た外貨建て資産の円換算影響確認に使います。" in html
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


def test_render_html_beginner_top_sections_hide_internal_terms():
    html = render_html(_report())
    start = html.index('<section class="glance-summary"')
    end = html.index('<section class="hero-card"', start)
    top_html = html[start:end]

    assert "まず見るポイント" in top_html
    assert "買い判断カード" in top_html
    assert "今の判断" in top_html
    assert "買い場か？" in top_html
    assert "市場の状態" in top_html
    assert "主な理由" in top_html
    assert "次に見るもの" in top_html
    assert "初心者向けひとこと" in top_html
    assert "現在の判断" in top_html
    assert "理由" in top_html
    assert "危険度" in top_html
    assert "買い候補" in top_html
    assert "今すること" in top_html
    assert "これは成功確率ではありません" in top_html
    assert "SPY" in top_html
    assert "XLK" in top_html

    forbidden_terms = [
        "raw/final buy_window",
        "raw/final buy_candidate",
        "diagnostic only",
        "proposed / candidate",
        "trigger path",
        "live_data_sufficient",
        "sample-only",
        "final_action",
        "buy_readiness_score",
    ]
    for term in forbidden_terms:
        assert term not in top_html

    advice_terms = ["買うべき", "今が買い", "利益が出る", "安全に買える"]
    for term in advice_terms:
        assert term not in top_html


@pytest.mark.parametrize(("score", "rendered_score"), [(None, 0), (0, 0), (1, 1), (32, 32), (60, 60), (85, 85), (100, 100)])
def test_render_html_readiness_gauge_renders_score_from_left_origin(score, rendered_score):
    report = deepcopy(_report())
    report["buy_decision_card"]["buy_readiness_score"] = score
    html = render_html(report)
    start = html.index('<section class="buy-decision-flow"')
    end = html.index('<section class="hero-card"', start)
    top_html = html[start:end]

    assert f'style="--score:{rendered_score}"' in top_html
    assert f'aria-label="買い候補度 {rendered_score} / 100"' in top_html
    assert "これは成功確率ではありません" in top_html
    assert "from 270deg" in html
    assert "calc(var(--score) * 1.8deg)" in html


@pytest.mark.parametrize(
    ("scenario", "mutate", "required_text"),
    [
        ("standard", lambda report: None, ["監視継続", "SPY", "XLK"]),
        (
            "near_candidate",
            lambda report: report["buy_decision_card"].update(
                {"final_action": "buy_candidate", "buy_readiness_score": 86, "primary_blocker": "insufficient_recovery"}
            ),
            ["材料待ち", "回復の決め手が不足"],
        ),
        (
            "wait",
            lambda report: report["buy_decision_card"].update(
                {"final_action": "wait", "buy_readiness_score": 18, "primary_blocker": "market_stress"}
            ),
            ["見送り", "市場ストレスが残る"],
        ),
        (
            "insufficient_data",
            lambda report: (
                report["buy_decision_card"].update({"final_action": "wait", "primary_blocker": "sample_only"}),
                report["data_reliability"].update({"decision_allowed": False, "reason": "実データ不足のため参考表示に限定します。"}),
            ),
            ["確認用データが含まれる"],
        ),
        (
            "no_candidates",
            lambda report: report["investment_candidates"].update(
                {"candidate_tickers": [], "preferred_asset_class": None, "preferred_sector": None}
            ),
            ["候補なし"],
        ),
        (
            "long_blocker",
            lambda report: report["buy_decision_card"].update(
                {
                    "primary_blocker": (
                        "回復確認に必要な複数の材料がまだ十分にそろっておらず、" "市場ストレスと為替の影響をあわせて確認する必要があります"
                    )
                }
            ),
            ["回復確認に必要な複数の材料がまだ十分にそろっておらず"],
        ),
    ],
)
def test_render_html_beginner_top_sections_support_synthetic_scenarios(scenario, mutate, required_text):
    report = deepcopy(_report())
    mutate(report)
    html = render_html(report)
    start = html.index('<section class="glance-summary"')
    end = html.index('<section class="hero-card"', start)
    top_html = html[start:end]

    assert scenario
    for text in ["まず見るポイント", "買い判断カード", "初心者向けひとこと", "これは成功確率ではありません"]:
        assert text in top_html
    for text in required_text:
        assert text in top_html
    for text in [
        "raw/final buy_window",
        "raw/final buy_candidate",
        "diagnostic only",
        "proposed / candidate",
        "trigger path",
        "live_data_sufficient",
        "sample-only",
        "final_action",
        "buy_readiness_score",
        "買うべき",
        "今が買い",
        "利益が出る",
        "安全に買える",
    ]:
        assert text not in top_html


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
    assert '<div class="l">安定</div>' in html
    assert '<div class="l">監視</div>' in html
    assert '<div class="l">要確認</div>' in html
    assert '<div class="l">未取得</div>' in html
    assert "しきい値レビュー" in html
    assert "先回り候補" in html
    assert "レジーム先回り" in html
    assert "生活コスト上昇警戒" in html
    assert "legacy 買い検討ゾーン" in html
    assert "レジーム減点 0.0" in html
    assert "補足レポート 以下は監査性と詳細確認" not in html
    assert '<section class="section">' not in html
    assert "historyEmbedPayload" not in html
    assert "threshold proposal" not in html


def test_render_markdown_includes_multi_asset_candidates_without_changing_decision_fields():
    report = deepcopy(_report())
    report["multi_asset_candidates"] = _multi_asset_payload()
    before_action = report["buy_decision_card"]["final_action"]
    before_score = report["buy_decision_card"]["buy_readiness_score"]

    markdown = render_markdown(report)

    assert "## 資産クラス別の確認候補" in markdown
    assert "株式候補: SPY" in markdown
    assert "守り候補: GLD" in markdown
    assert "債券候補: AGG" in markdown
    assert "日本株候補: 1306.T" in markdown
    assert "円建て債券候補: JGB_CONTEXT" in markdown
    assert "現金待機: CASH" in markdown
    assert "分類: 守り候補の確認" in markdown
    assert "分類: データ不足" in markdown
    assert "日本居住者向け確認: 状態: 参考表示 / 分類: 日本株の確認" in markdown
    assert "国内金利" in markdown
    assert "為替" in markdown
    assert "国内インフレ" in markdown
    assert "状態: データ不足" in markdown
    assert "状態: 待機" in markdown
    assert "現在値=103" in markdown
    assert "4週=-3.7" in markdown
    assert "制約=missing_series" in markdown
    assert "これは買い推奨ではなく" in markdown
    assert "final_action への影響: False" in markdown
    assert "buy_readiness_score への影響: False" in markdown
    assert report["buy_decision_card"]["final_action"] == before_action
    assert report["buy_decision_card"]["buy_readiness_score"] == before_score
    section = markdown[markdown.index("## 資産クラス別の確認候補") : markdown.index("## 先回り候補")]
    for forbidden in ("買うべき", "今が買い", "安全", "利益が出る", "確実", "推奨銘柄"):
        assert forbidden not in section


def test_render_html_includes_multi_asset_candidates_table():
    report = deepcopy(_report())
    report["multi_asset_candidates"] = _multi_asset_payload()

    html = render_html(report)

    assert "資産クラス別の確認候補" in html
    assert "株式候補" in html
    assert "守り候補" in html
    assert "債券候補" in html
    assert "日本株候補" in html
    assert "円建て債券候補" in html
    assert "現金待機" in html
    assert "守り候補の確認" in html
    assert "日本居住者向け確認" in html
    assert "日本株の確認" in html
    assert "国内金利" in html
    assert "為替" in html
    assert "国内インフレ" in html
    assert "データ不足" in html
    assert "待機判断の補助" in html
    assert "現在値=103" in html
    assert "4週=-3.7" in html
    assert "制約=missing_series" in html
    assert "為替や商品価格の影響を受けます。" in html
    section = html[html.index("資産クラス別の確認候補") : html.index("先回り候補")]
    assert "unavailable" not in section
    assert "final_action への影響: False" in html


def test_render_outputs_include_japan_resident_integrated_risk_context():
    report = deepcopy(_report())
    report["japan_resident_integrated_risk_context"] = _integrated_context_payload()

    markdown = render_markdown(report)
    html = render_html(report)
    supplement = render_supplement_dashboard_html(report)

    for rendered in (markdown, html, supplement):
        assert "日本在住者向け統合リスク文脈" in rendered
        assert "米国・グローバル" in rendered
        assert "USDJPY/EURJPY" in rendered
        assert "国内インフレデータ品質" in rendered
        assert "final_action への影響" in rendered
        assert "buy_readiness_score への影響" in rendered
        assert "False" in rendered
        assert "manual_file_missing" in rendered


def test_render_html_groups_core_supplemental_data_limits_and_acquisition_status():
    report = deepcopy(_report())
    report["japan_resident_integrated_risk_context"] = _integrated_context_payload()

    html = render_html(report)

    assert "判断とリスク文脈の読み分け" in html
    assert "本体判断" in html
    assert "補助判断" in html
    assert "グローバル危険ライン" in html
    assert "データ制約・取得状況" in html
    assert "final_action" in html
    assert "買い候補度" in html
    assert "manual_file_missing" in html
    assert "proxy_fallback=1" in html


def test_render_supplement_dashboard_includes_domestic_danger_context():
    report = deepcopy(_report())
    report["domestic_danger_context"] = {
        "domestic_danger_level": "caution",
        "domestic_danger_reasons": ["MOF JGB利回りは国内金利の補助危険確認に使われます。"],
        "domestic_watch_items": [
            {
                "group": "円建て債券",
                "name": "円建て債券確認",
                "symbol": "2510.T",
                "status": "ok",
                "level": "caution",
                "reason": "円建て債券は国内金利上昇時に価格下落リスクがあるため、国内金利文脈で補助確認します。",
                "metrics": "価格メトリクス未接続",
                "limitations": ["price_metrics_missing"],
                "caution": "債券は金利上昇時に価格が下がることがあります。",
            },
            {
                "group": "国内REIT",
                "name": "国内REIT確認",
                "symbol": "1343.T",
                "status": "ok",
                "level": "caution",
                "reason": "国内REITは米国REITとは分けて確認します。",
                "metrics": "4週=-5.0 / 12週=-9.0",
                "limitations": [],
                "caution": "債券は金利上昇時に価格が下がることがあります。",
            },
            {
                "group": "円建て金",
                "name": "純金上場信託",
                "symbol": "1540.T",
                "status": "ok",
                "level": "watch",
                "reason": "円建て金は金価格と為替の文脈を分けて補助確認します。",
                "metrics": "4週=-4.2 / 傾向=weakening",
                "limitations": [],
                "caution": "円建て資産と外貨建て資産では、為替の影響が異なります。",
            },
        ],
        "domestic_data_limitations": [
            "CPI は manual_file_missing のため、japan_cpi.csv または安定した公開系列がない限り補助危険値として扱いません。",
            "BOJ短期金利 は endpoint_not_resolved のため、boj_short_rate.csv または安定した公開系列がない限り補助危険値として扱いません。",
        ],
        "uses_domestic_values": True,
        "must_not_affect_final_action": True,
        "must_not_affect_buy_readiness_score": True,
    }

    html = render_supplement_dashboard_html(report)
    markdown = render_markdown(report)

    for text in ("国内文脈の補助危険確認", "円建て債券", "2510.T", "国内REIT", "1343.T", "円建て金", "1540.T"):
        assert text in html
        assert text in markdown
    assert "final_action への影響: False" in html
    assert "buy_readiness_score への影響: False" in html
    assert "manual_file_missing" in html
    assert "endpoint_not_resolved" in html
    assert "price_metrics_missing" in html
    assert "price_metrics_missing" in markdown


def test_render_html_handles_legacy_multi_asset_candidate_shape_with_safe_labels():
    report = deepcopy(_report())
    payload = _multi_asset_payload()
    payload["candidates"][3].pop("reason_category")
    payload["candidates"][3]["status"] = "neutral"
    report["multi_asset_candidates"] = payload

    html = render_html(report)

    assert "参考表示" in html
    assert "補助確認" in html
    assert "neutral" not in html
    assert "これは買い推奨ではなく" in html


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
