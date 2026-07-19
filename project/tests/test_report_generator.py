from __future__ import annotations

from copy import deepcopy

import pytest

from project.japan_resident_integrated_context import build_japan_resident_integrated_risk_context
from project.report_generator import _domestic_candidate_rows_for_top, render_html, render_markdown, render_supplement_dashboard_html


def _report() -> dict:
    return {
        "title": "Test Report",
        "generated_at": "2026-03-19T21:00:00",
        "data_source": "sample",
        "runtime_context": {
            "is_frozen": True,
            "python_executable": r"Z:\portable\GlobalMarketMonitor\GlobalMarketMonitor.exe",
            "working_directory": r"Z:\portable\GlobalMarketMonitor",
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
            },
            {
                "ticker": "GC=F",
                "ticker_name_ja": "金先物",
                "current": 4172.9,
                "change_1w": 0.0,
                "change_4w": -0.085,
                "change_12w": -0.1029,
                "zscore": -0.1219,
                "signal_label": "中立",
            },
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


def _hindenburg_payload(signal: str = "active") -> dict:
    if signal == "missing":
        return {
            "status": "manual_file_missing",
            "current_signal": "unavailable",
            "current_signal_level": "unavailable",
            "is_currently_active": False,
            "is_active_as_of_latest_data": False,
            "stale_data": False,
            "data_latest_date": None,
            "as_of_date": "2026-01-20",
            "latest_date": None,
            "latest_trigger_date": None,
            "active_until": None,
            "active_window_days": 30,
            "trigger_dates": [],
            "active_periods": [],
            "criteria_latest": {},
            "criteria_passed": [],
            "criteria_failed": [],
            "criteria_unknown": [],
            "source_kind": "local_manual_file",
            "source_path": "project/manual_sources/hindenburg_breadth.csv",
            "limitations": ["手動CSV未設定"],
            "daily_signals": [],
            "must_not_affect_final_action": True,
            "must_not_affect_buy_readiness_score": True,
        }
    triggered = signal == "active"
    return {
        "status": "ok",
        "current_signal": "active" if triggered else "not_triggered",
        "current_signal_level": "active" if triggered else "normal",
        "is_currently_active": triggered,
        "is_active_as_of_latest_data": triggered,
        "stale_data": False,
        "data_latest_date": "2026-01-20",
        "as_of_date": "2026-01-20",
        "latest_date": "2026-01-20",
        "latest_trigger_date": "2026-01-15" if triggered else None,
        "active_until": "2026-02-14" if triggered else None,
        "active_window_days": 30,
        "trigger_dates": ["2026-01-02", "2026-01-15"] if triggered else [],
        "active_periods": (
            [
                {
                    "period_start": "2026-01-02",
                    "period_end": "2026-02-14",
                    "trigger_day_count": 2,
                    "latest_trigger_date": "2026-01-15",
                }
            ]
            if triggered
            else []
        ),
        "criteria_latest": {
            "uptrend": {"state": "passed"},
            "new_highs_threshold": {"state": "passed"},
            "new_lows_threshold": {"state": "passed"},
            "negative_mcclellan": {"state": "passed"},
            "high_low_balance": {"state": "passed"},
        },
        "criteria_passed": ["uptrend", "new_highs_threshold", "new_lows_threshold", "negative_mcclellan", "high_low_balance"],
        "criteria_failed": [],
        "criteria_unknown": [],
        "new_highs_pct": 3.1,
        "new_lows_pct": 3.0,
        "threshold_pct": 2.8,
        "mcclellan_oscillator": -12.0,
        "index_trend": "index_above_50d",
        "source_kind": "local_manual_file",
        "source_path": "project/manual_sources/hindenburg_breadth.csv",
        "limitations": [],
        "daily_signals": [
            {
                "date": "2026-01-15",
                "triggered": triggered,
                "criteria_summary": "passed=5 / failed=0 / unknown=0",
                "new_highs_pct": 3.1,
                "new_lows_pct": 3.0,
                "mcclellan_oscillator": -12.0,
            }
        ],
        "must_not_affect_final_action": True,
        "must_not_affect_buy_readiness_score": True,
    }


def test_render_markdown_uses_real_newlines():
    text = render_markdown(_report())
    assert "`n" not in text
    assert "## まず見る要約" in text
    assert "## 買い判断カード" in text
    assert "成功確率・期待リターン・投資成功率ではありません" in text
    assert "TimesFM" not in text
    assert "- 最終判断: 監視" in text
    assert "危険ラインの発火経路" in text
    assert "信頼度監査: 米国・グローバル中心の危険監視" in text
    assert "暫定レビュー=10 / 精度不足=7 / 通過=2" in text
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
    assert "しきい値レビュー" not in text
    assert "しきい値提案" not in text
    assert "しきい値利用方針" not in text
    assert "しきい値ルール認証" not in text


def test_render_html_includes_first_read_summary():
    text = render_markdown(_report())
    html = render_html(_report())

    assert "approved-report-dashboard" in html
    assert "main-dashboard-shell" in html
    assert "decision-hero" in html
    assert "readiness-card" in html
    assert "context-stack" in html
    assert "hindenburg-lamp-card" in html
    assert "glance-summary" in html
    assert "reading-guide" in html
    assert "まず見る：今日の判断" in html
    assert "候補は「買う銘柄」ではなく、次に観察する対象" in html
    assert "本体判断" in html
    assert "補助確認" in html
    assert "グローバルリスク" in html
    assert "日本在住者向け文脈" in html
    assert "データ制約" in html
    assert "ヒンデンブルグオーメン" in html
    assert "詳細は補足レポートで確認" in html
    assert "本レポートは市場のモニタリングを目的としており" in html
    assert html.count('class="monitor-note-segment"') == 2
    assert "買い判断カード" in html
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
    assert "実データ取得率: 75%" in text
    assert "データ品質上限: 監視継続 / 信頼度上限 0.45" in text
    assert "代替取得内訳: 代替ティッカー=1 / サンプル代替=1 / 未取得=0" in text
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
    assert "信用波及初期" in text
    assert "VIX指数" in text
    assert "警告レイヤー" in text
    assert "生活影響警告 / 注意" in text
    assert "信用環境は持ち直し寄りです。" in text
    assert "判定用スコアは 0.70" in text
    assert "- 旧判定用スコア: 0.7" in text
    assert "- 上昇再開の証拠: confirmed (0.74)" in text
    assert "- 騙し上昇の警戒: caution" in text
    assert "- 新判断: 監視継続" in text
    assert "- 旧スポット投資判断: 買い検討ゾーン" in text
    assert "- 最終判断: 監視継続 / 判定モード 証拠形成中・注意" in text
    assert "内部警告件数" in text
    assert "危険ライン段階とは別の判定" in text
    assert '<span style="color:#1f2933;"><strong>信用波及初期</strong></span>' in text


def test_render_html_shows_oil_directional_context_instead_of_generic_zero_risk():
    report = _report()
    report["risk_lines"]["indicators"].append(
        {
            "ticker": "CL=F",
            "ticker_name_ja": "WTI原油先物",
            "current": 76.54,
            "change_1w": -0.04,
            "change_4w": -0.18,
            "change_12w": -0.22,
            "zscore": -1.2,
            "line_level": "normal",
            "line_level_label": "通常",
            "pressure_score": 0.0,
            "warning_line": "roc_8w:0.095138",
            "danger_line": "level_and_roc_8w:0.903846",
            "extreme_line": "roc_2w:0.084365",
            "line_reason": "本判定に使える採用済み基準には未到達です。",
            "oil_context": {
                "overall_status": "normal",
                "inflation_pressure_score": 0.0,
                "demand_collapse_score": 42.0,
                "oil_decline_pressure_score": 80.0,
                "wti_return_20d": -0.18,
                "risk_signal_allowed": True,
                "data_quality": "valid",
                "quality_flags": ["valid"],
                "limitations": ["原油下落単独では需要崩壊シグナルにせず、株式と信用の確認を待ちます"],
                "reason": "原油は下落方向の圧力がありますが、株式・信用市場の同時悪化が揃っていないため、需要崩壊シグナルにはしていません。",
            },
        }
    )

    html = render_html(report)

    assert "インフレ方向圧力 0/100" in html
    assert "需要減速方向 42/100" in html
    assert "4週変化 -18.0%" in html
    assert "危険度 0/100" not in html


def test_render_html_shows_top_data_provenance_strip():
    report = _report()
    report["data_provenance"] = {
        "data_mode_label": "キャッシュ使用",
        "price_basis_date": "2026-06-19",
        "retrieved_at": "2026-06-20T21:07:09",
        "live_fetch_performed": False,
        "live_fetch_label": "ライブ更新なし",
        "freshness_status": "fresh",
        "freshness_label": "営業日基準で正常",
    }

    html = render_html(report)

    top = html[: html.index('<section class="approved-report-dashboard main-dashboard-shell"')]
    assert "データ更新:" not in top
    assert "データモード" in top
    assert "キャッシュ使用" in top
    assert "価格基準日" in top
    assert "2026-06-19" in top
    assert "取得日時" in top
    assert "2026-06-20 21:07 JST" in top
    assert "ライブ更新なし" in top
    assert "営業日基準で正常" in top


def test_render_html_beginner_top_sections_hide_internal_terms():
    html = render_html(_report())
    start = html.index('<section class="approved-report-dashboard main-dashboard-shell"')
    end = html.index('<div class="mini-grid report-ops-grid">', start)
    top_html = html[start:end]
    regime_index = top_html.index("市場レジーム")
    supplemental_index = top_html.index('<section class="supplemental-signal-strip"')
    context_index = top_html.index("判断とリスク文脈の読み分け")
    beginner_html = top_html[:context_index]

    assert "本体判断" in top_html
    assert "買い候補度" in top_html
    assert "補助確認" in top_html
    assert "グローバルリスク" in top_html
    assert "日本在住者向け文脈" in top_html
    assert "データ制約" in top_html
    assert "ヒンデンブルグオーメン" in top_html
    assert "次の確認条件" in top_html
    assert "買い候補" in top_html
    assert "これは成功確率ではありません" in top_html
    assert "単独では売買判断に使いません" in top_html
    assert "詳細は補足レポートで確認" in top_html
    assert "SPY" in top_html
    assert "XLK" in top_html
    assert regime_index < supplemental_index < context_index
    assert "summary-choice-grid" not in top_html
    assert "<table" not in beginner_html
    assert "危険ライン詳細" not in beginner_html

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
        assert term not in beginner_html

    advice_terms = ["買うべき", "今が買い", "利益が出る", "安全に買える"]
    for term in advice_terms:
        assert term not in top_html


@pytest.mark.parametrize(("score", "rendered_score"), [(None, 0), (0, 0), (1, 1), (32, 32), (60, 60), (85, 85), (100, 100)])
def test_render_html_readiness_gauge_renders_score_from_left_origin(score, rendered_score):
    report = deepcopy(_report())
    report["buy_decision_card"]["buy_readiness_score"] = score
    html = render_html(report)
    start = html.index('<section class="approved-report-dashboard main-dashboard-shell"')
    end = html.index('<div class="dashboard-grid detail-summary-grid">', start)
    top_html = html[start:end]

    assert f'style="--score:{rendered_score}"' in top_html
    assert f'aria-label="買い候補度 {rendered_score} / 100"' in top_html
    assert "これは成功確率ではありません" in top_html
    assert "width:calc(var(--score) * 1%)" in html


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
            "inflation_shock",
            lambda report: report["buy_decision_card"].update({"primary_blocker": "inflation_shock"}),
            ["インフレショックの影響が残る"],
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
    start = html.index('<section class="approved-report-dashboard main-dashboard-shell"')
    end = html.index('<div class="dashboard-grid detail-summary-grid">', start)
    top_html = html[start:end]

    assert scenario
    for text in ["本体判断", "補助確認", "買い候補度", "これは成功確率ではありません"]:
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
        "in横ばいion shock",
        "買うべき",
        "今が買い",
        "利益が出る",
        "安全に買える",
    ]:
        assert text not in top_html


def test_render_html_contains_japanese_explanations():
    html = render_html(_report())
    assert "市場レジーム" in html
    assert "生成日時" in html
    assert "データ更新:" not in html
    assert "スポット投資判断" in html
    assert "セクター概要" in html
    assert "アラート" in html
    assert "データ健全性" in html
    assert "データ品質上限" in html
    assert "代替ティッカー=1 / サンプル代替=1 / 未取得=0" in html
    assert "sample_fallback_present" in html
    assert "しきい値提案" not in html
    assert "しきい値レビュー" not in html
    assert "しきい値利用方針" not in html
    assert "しきい値ルール認証" not in html
    assert "レジーム補助" in html
    assert "上昇再開 確認済み / 警戒 注意" in html
    assert "上昇再開の証拠" in html
    assert "騙し上昇の警戒" in html
    assert "レジーム減点はなく、判定用スコアは 0.70" in html
    assert "先回り候補" in html
    assert "レジーム先回り" in html
    assert "生活コスト上昇警戒" in html
    assert "旧判断 買い検討ゾーン" in html
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
    assert "最終判断への影響: いいえ" in markdown
    assert "買い候補度への影響: いいえ" in markdown
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
    assert "最終判断への影響: いいえ" in html


def test_render_outputs_include_risk_line_proof_and_diagnostic_rule_status():
    report = deepcopy(_report())
    indicator = report["risk_lines"]["indicators"][0]
    indicator.update(
        {
            "accepted_rule": {
                "stage": "danger",
                "feature": "level_percentile",
                "value": 1.0,
                "threshold": 0.903846,
                "direction": "higher",
                "source": "historical_quantile",
                "confidence": "medium",
            },
            "diagnostic_rule_hits": [
                {
                    "stage": "extreme",
                    "feature": "roc_z_1w",
                    "value": 1.3605,
                    "threshold": 1.148726,
                    "direction": "higher",
                    "source": "fallback_review",
                    "confidence": "fallback_review",
                    "reason": "fallback_review thresholds are diagnostic only and cannot affect final action.",
                }
            ],
        }
    )

    markdown = render_markdown(report)
    html = render_html(report)

    for rendered in (markdown, html):
        assert "本判定根拠" in rendered
        assert "参考・除外" in rendered
        assert "level_percentile=1" in rendered
        assert "roc_z_1w=1.3605" in rendered
        assert "暫定レビュー" in rendered


def test_render_html_top_candidate_card_keeps_domestic_candidates_inside_existing_three_blocks():
    report = deepcopy(_report())
    payload = _multi_asset_payload()
    for row in payload["candidates"]:
        if row.get("asset_class") == "bond_jpy":
            row.update(
                {
                    "symbol": "2510.T",
                    "source_data_available": True,
                    "metrics": {"current_value": 90.0, "change_4w": -1.1, "change_12w": -4.2, "trend_label": "weakening"},
                }
            )
    payload["candidates"].append(
        {
            "asset_class": "reit_jp",
            "asset_class_label": "国内REIT候補",
            "symbol": "1343.T",
            "display_name": "国内REIT ETF",
            "role": "real_asset_income",
            "role_label": "国内不動産・利回り確認",
            "status": "informational",
            "reason_category": "jp_reit_context",
            "reason": "国内REITを株式・債券とは別に確認します。",
            "caution": "REITは金利上昇の影響を受けます。",
            "source_data_available": True,
            "metrics": {"current_value": 90.0, "change_4w": -2.2, "trend_label": "weakening"},
        }
    )
    report["multi_asset_candidates"] = payload

    html = render_html(report)
    start = html.index('<section class="first-read-card candidate-summary-card">')
    end = html.index("</section>", start)
    candidate_card = html[start:end]

    assert candidate_card.count('class="candidate-mini-block"') == 3
    assert candidate_card.count("candidate-chip-row compact domestic") == 3
    for text in ("1306.T", "2510.T", "1343.T", "4週 -3.7%", "4週 -1.1%", "4週 -2.2%"):
        assert text in candidate_card
    assert "資産クラス別の確認候補" not in candidate_card


def test_top_domestic_candidate_buckets_use_distinct_existing_calculation_shapes():
    report = {
        "regime": {"regime_label": "transition"},
        "multi_asset_candidates": {
            "candidates": [
                {
                    "asset_class": "jp_equity",
                    "symbol": "1306.T",
                    "source_data_available": True,
                    "metrics": {"change_4w": -1.5, "momentum_12w": -2.0, "max_drawdown": -12.0},
                },
                {
                    "asset_class": "bond_jpy",
                    "symbol": "2510.T",
                    "source_data_available": True,
                    "metrics": {"change_4w": 0.8, "momentum_12w": -3.0, "max_drawdown": -9.0},
                },
                {
                    "asset_class": "reit_jp",
                    "symbol": "1343.T",
                    "source_data_available": True,
                    "metrics": {"change_4w": 2.5, "momentum_12w": -7.0, "max_drawdown": -16.0},
                },
            ]
        },
    }

    main_symbols = [row["symbol"] for row in _domestic_candidate_rows_for_top(report, "main")]
    recovery_symbols = [row["symbol"] for row in _domestic_candidate_rows_for_top(report, "recovery")]
    regime_symbols = [row["symbol"] for row in _domestic_candidate_rows_for_top(report, "regime")]

    assert main_symbols == ["1306.T", "2510.T", "1343.T"]
    assert recovery_symbols == ["1343.T", "2510.T"]
    assert regime_symbols == ["1343.T", "2510.T", "1306.T"]


def test_top_domestic_candidate_uses_valid_domestic_metric_fallback_when_primary_is_suspicious():
    report = {
        "regime": {"regime_label": "transition"},
        "multi_asset_candidates": {
            "candidates": [
                {
                    "asset_class": "jp_equity",
                    "symbol": "1306.T",
                    "source_data_available": True,
                    "metrics": {"change_4w": 4.8, "change_12w": -88.7, "limitations": ["split_or_discontinuity_suspected"]},
                }
            ]
        },
        "domestic_market_metrics": {
            "by_symbol": {
                "1306.T": {
                    "symbol": "1306.T",
                    "asset_group": "jp_equity",
                    "is_available": True,
                    "change_4w": 4.8,
                    "limitations": ["split_or_discontinuity_suspected"],
                },
                "1321.T": {
                    "symbol": "1321.T",
                    "asset_group": "jp_equity",
                    "is_available": True,
                    "change_4w": 1.4,
                    "momentum_12w": 3.2,
                    "max_drawdown": -4.5,
                    "limitations": [],
                },
            }
        },
    }

    rows = _domestic_candidate_rows_for_top(report, "main")

    assert [row["symbol"] for row in rows] == ["1321.T"]
    assert rows[0]["metric_text"] == "4週 1.4%"


def test_render_outputs_include_japan_resident_integrated_risk_context():
    report = deepcopy(_report())
    report["japan_resident_integrated_risk_context"] = _integrated_context_payload()

    markdown = render_markdown(report)
    html = render_html(report)
    supplement = render_supplement_dashboard_html(report)

    for rendered in (markdown, supplement):
        assert "日本在住者向け統合リスク文脈" in rendered
        assert "米国・グローバル" in rendered
        assert "USDJPY/EURJPY" in rendered
        assert "国内インフレデータ品質" in rendered
        assert "最終判断への影響" in rendered
        assert "買い候補度への影響" in rendered
        assert "いいえ" in rendered
        assert "手動CSV未設定" in rendered
        assert "manual_file_missing" not in rendered
    assert "日本在住者向け統合リスク文脈" not in html
    assert "日本在住者向け文脈" in html
    assert "手動CSV未設定" in html
    assert "manual_file_missing" not in html


def test_render_html_groups_core_supplemental_data_limits_and_acquisition_status():
    report = deepcopy(_report())
    report["japan_resident_integrated_risk_context"] = _integrated_context_payload()
    report["decision_boundary_experiment"] = {
        "enabled": False,
        "baseline": {"final_action": "watch", "buy_readiness_score": 72},
        "experimental": {
            "final_action": "watch",
            "adjusted_buy_readiness_score": 64,
            "supplemental_warning_level": "caution",
            "suggested_adjustment": "experimental_caution_score_discount",
        },
        "diff": {"score_delta": -8, "raw_score_delta": -8, "clamped_score_delta": -8, "action_changed": False},
        "must_not_affect_production_default": True,
    }

    html = render_html(report)

    assert "判断とリスク文脈の読み分け" in html
    assert "本体判断" in html
    assert "補助判断" not in html
    assert "アラート" in html
    assert "グローバル危険ライン" in html
    assert "データ制約・取得状況" in html
    assert "実験比較" in html
    assert "最終判断" in html
    assert "買い候補度" in html
    assert "基準 72 → 実験値 64 / 差分 調整前 -8 / 上限適用後 -8" in html
    assert "手動CSV未設定" in html
    assert "代替ティッカーで取得=1" in html


def test_render_markdown_includes_decision_boundary_experiment_without_action_change():
    report = deepcopy(_report())
    report["decision_boundary_experiment"] = {
        "enabled": False,
        "baseline": {"final_action": "watch", "buy_readiness_score": 72},
        "experimental": {
            "final_action": "watch",
            "adjusted_buy_readiness_score": 64,
            "supplemental_warning_level": "caution",
            "suggested_adjustment": "experimental_caution_score_discount",
        },
        "diff": {
            "score_delta": -8,
            "raw_score_delta": -8,
            "clamped_score_delta": -8,
            "clamp_reason": "not_clamped",
            "action_changed": False,
        },
        "must_not_affect_production_default": True,
    }

    markdown = render_markdown(report)

    assert "判断境界の実験比較" in markdown
    assert "有効化: いいえ" in markdown
    assert "基準の最終判断: 監視継続" in markdown
    assert "実験後の買い候補度: 64" in markdown
    assert "調整前スコア差分: -8" in markdown
    assert "上限適用後スコア差分: -8" in markdown
    assert "上限理由: not_clamped" in markdown
    assert "判断変更: いいえ" in markdown
    assert "本番既定値への影響: いいえ" in markdown


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
            {
                "group": "日本株",
                "name": "TOPIX ETF",
                "symbol": "1306.T",
                "status": "ok",
                "level": "unavailable",
                "reason": "国内株式は外貨建て株式とは分け、日本株確認として補助表示します。指標: 4週=3.7 / 12週=-89.0 / 最大DD=-90.0",
                "metrics": "4週=3.7 / 12週=-89.0 / 最大DD=-90.0",
                "limitations": ["split_or_discontinuity_suspected", "risk_signal_excluded"],
                "caution": "異常値疑いがある場合は補助危険判定に使いません。",
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
    assert "最終判断への影響: いいえ" in html
    assert "買い候補度への影響: いいえ" in html
    assert "手動CSV未設定" in html
    assert "取得先未確定" in html
    assert "価格指標未接続" in html
    assert "価格指標未接続" in markdown
    assert "分割・データ断絶の疑い" in html
    assert "分割・データ断絶の疑い" in markdown
    assert "12週変化: 異常値疑いのため非採用" in html
    assert "12週変化: 異常値疑いのため非採用" in markdown
    assert "最大DD: 異常値疑いのため参考外" in html
    assert "最大DD: 異常値疑いのため参考外" in markdown
    assert "12週=-89.0" not in html
    assert "12週=-89.0" not in markdown
    assert "最大DD=-90.0" not in html
    assert "最大DD=-90.0" not in markdown


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
    assert "supplement-dashboard-shell" in html
    assert "evidence-summary-grid" in html
    assert "supplement-evidence-grid" in html
    assert "supplement-reading-guide" in html
    assert "まず確認する5つの要点" in html
    assert "判断の根拠" in html
    assert "データ品質" in html
    assert "補足レポート" in html
    assert "本体判断ではなく、補助確認と検証用の詳細です" in html
    assert "本体判断への影響なし" in html
    assert "report.html" in html
    assert "履歴" in html
    for nav_label in ["危険ライン", "日本在住者文脈", "国内文脈", "ヒンデンブルグオーメン", "データ取得", "しきい値", "実行環境", "履歴"]:
        assert nav_label in html
    for class_name in [
        "risk-line-detail-section",
        "resident-context-detail-section",
        "domestic-context-detail-section",
        "hindenburg-history-section",
        "episode-chronicle-launch-section",
        "data-acquisition-section",
        "threshold-audit-section",
        "runtime-diagnostics-section",
        "history-browser-section",
    ]:
        assert class_name in html
    assert "データ品質上限" in html
    assert "実データ 75%" in html
    assert "元:" not in html
    for section in [
        "危険ライン詳細と信頼度監査",
        "日本在住者文脈（統合）詳細",
        "国内文脈（危険シグナル）詳細",
        "ヒンデンブルグオーメンのトリガー / 発動履歴",
        "市場警戒年代記",
        "資産クラス / 候補証拠",
        "データ取得状況",
        "しきい値の使用状況と認証",
        "実行環境 / 接続診断",
        "履歴ブラウザ",
    ]:
        assert section in html
    assert "decision-hero" not in html
    assert "SPY" in html
    assert "USDJPY=X" in html
    assert "生活コスト上昇警戒" in html


def test_render_outputs_include_active_hindenburg_omen_without_decision_impact():
    report = deepcopy(_report())
    report["hindenburg_omen_context"] = _hindenburg_payload("active")
    before_action = report["buy_decision_card"]["final_action"]
    before_score = report["buy_decision_card"]["buy_readiness_score"]

    markdown = render_markdown(report)
    html = render_html(report)
    supplement = render_supplement_dashboard_html(report)

    assert "ヒンデンブルグオーメンが点灯中です。" in markdown
    assert "単独では売買判断に使いません" in markdown
    assert "発動期間: 2026-01-02 から 2026-02-14" in markdown
    assert "ヒンデンブルグオーメン" in html
    assert "点灯中" in html
    assert "ヒンデンブルグオーメン" in supplement
    assert report["buy_decision_card"]["final_action"] == before_action
    assert report["buy_decision_card"]["buy_readiness_score"] == before_score


def test_supplement_opens_ready_episode_chronicle_in_separate_window_without_decision_impact():
    report = deepcopy(_report())
    before_action = report["buy_decision_card"]["final_action"]
    before_score = report["buy_decision_card"]["buy_readiness_score"]
    report["risk_engine_v2_episode_chronicle"] = {
        "status": "ready",
        "freshness_status": "current",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "promotion_allowed": False,
        "page_filename": "risk_engine_v2_episode_chronicle.html",
        "episode_count": 18,
        "mature_count": 16,
        "pending_count": 2,
        "latest_event_title": "2026年7月17日 — 警戒局面",
        "generated_at": "2026-07-19T00:00:00+00:00",
    }

    supplement = render_supplement_dashboard_html(report)

    hindenburg_index = supplement.index("4. ヒンデンブルグオーメン")
    chronicle_index = supplement.index("5. 市場警戒年代記")
    asset_index = supplement.index("6. 資産クラス / 候補証拠")
    assert hindenburg_index < chronicle_index < asset_index
    assert 'href="risk_engine_v2_episode_chronicle.html"' in supplement
    assert 'target="_blank"' in supplement
    assert 'rel="noopener"' in supplement
    assert supplement.count('href="risk_engine_v2_episode_chronicle.html"') == 2
    hero = supplement.split('<section class="supplement-hero"', 1)[1].split("</section>", 1)[0]
    assert 'href="risk_engine_v2_episode_chronicle.html"' in hero
    assert '<span class="supplement-chip">補助確認</span>' not in hero
    assert hero.index("データ制約") < hero.index("本体判断への影響なし")
    assert hero.index("本体判断への影響なし") < hero.index("市場警戒年代記を別窓で開く")
    assert hero.index("市場警戒年代記を別窓で開く") < hero.index("本体レポートへ戻る")
    assert "2026年7月17日 — 警戒局面" in supplement
    assert report["buy_decision_card"]["final_action"] == before_action
    assert report["buy_decision_card"]["buy_readiness_score"] == before_score


def test_supplement_disables_episode_chronicle_when_contract_is_not_ready():
    report = deepcopy(_report())
    report["risk_engine_v2_episode_chronicle"] = {
        "status": "invalid",
        "reason": "証拠成果物が古いため開けません",
        "page_filename": "risk_engine_v2_episode_chronicle.html",
    }

    supplement = render_supplement_dashboard_html(report)

    assert "市場警戒年代記は現在開けません" in supplement
    assert 'aria-disabled="true"' in supplement
    assert 'href="risk_engine_v2_episode_chronicle.html"' not in supplement
    assert supplement.count('aria-disabled="true"') == 2
    hero = supplement.split('<section class="supplement-hero"', 1)[1].split("</section>", 1)[0]
    assert "市場警戒年代記は現在開けません" in hero
    assert '<span class="supplement-chip">補助確認</span>' not in hero
    assert "証拠成果物が古いため開けません" in supplement
    assert "10. 履歴ブラウザ" in supplement


def test_render_outputs_include_inactive_and_missing_hindenburg_states():
    inactive = deepcopy(_report())
    inactive["hindenburg_omen_context"] = _hindenburg_payload("inactive")
    missing = deepcopy(_report())
    missing["hindenburg_omen_context"] = _hindenburg_payload("missing")

    inactive_markdown = render_markdown(inactive)
    missing_html = render_html(missing)

    assert "ヒンデンブルグオーメン: 点灯なし" in inactive_markdown
    assert "ヒンデンブルグオーメン: 未取得" in missing_html
    assert "市場幅CSVが未設定のため判定できません" in missing_html


def test_hindenburg_report_includes_history_and_experimental_labels():
    report = deepcopy(_report())
    payload = _hindenburg_payload("missing")
    payload.update(
        {
            "status": "data_unavailable",
            "state": "UNINITIALIZED",
            "source_kind": "builtin_provider_chain",
            "failure_code": "ALL_PROVIDERS_UNAVAILABLE",
            "history_progress_label": "蓄積履歴: 0 / 39営業日",
            "automatic_acquisition": {
                "label": "自動取得・実験的",
                "attempted": True,
                "eligible": True,
                "success_label": False,
                "reason": "ELIGIBLE",
            },
            "provider_attempts": [
                {
                    "provider_id": "barchart_market_momentum",
                    "provider_label": "Barchart Market Momentum",
                    "status": "failed",
                    "failure_code": "ISSUE_COUNTS_NOT_AVAILABLE",
                }
            ],
            "providers_attempted_count": 1,
        }
    )
    report["hindenburg_omen_context"] = payload

    markdown = render_markdown(report)
    html = render_supplement_dashboard_html(report)

    assert "自動取得・実験的（未成立）" in markdown
    assert "蓄積履歴: 0 / 39営業日" in markdown
    assert "取得成功=いいえ" in markdown
    assert "自動取得・実験的" in html


def test_render_outputs_include_stale_hindenburg_state_without_active_notice():
    report = deepcopy(_report())
    payload = _hindenburg_payload("active")
    payload.update(
        {
            "current_signal": "unconfirmed",
            "current_signal_level": "notice",
            "is_currently_active": False,
            "is_active_as_of_latest_data": True,
            "stale_data": True,
            "data_latest_date": "2026-01-20",
            "as_of_date": "2026-02-10",
            "limitations": ["市場幅CSVの最新日が古いため、現在の点灯状態は判定できません。最新日: 2026-01-20"],
        }
    )
    report["hindenburg_omen_context"] = payload

    markdown = render_markdown(report)
    html = render_html(report)

    assert "ヒンデンブルグオーメン: データが古いため現在点灯は未確定" in markdown
    assert "市場幅CSVの最新日が古いため、現在の点灯状態は判定できません" in html
    assert "判定基準日: 2026-02-10" in markdown
    assert "データ鮮度不足: はい" in markdown
    assert "Hindenburg Omen が点灯中です。" not in markdown


def test_hindenburg_report_wording_avoids_panic_and_advice_terms():
    report = deepcopy(_report())
    report["hindenburg_omen_context"] = _hindenburg_payload("active")

    rendered = render_markdown(report)
    hindenburg_section = rendered.split("## ヒンデンブルグオーメン / 市場幅の補助確認", 1)[1]

    for forbidden in ["暴落確定", "暴落予測", "売るべき", "買うべき", "今が買い", "推奨銘柄"]:
        assert forbidden not in hindenburg_section
