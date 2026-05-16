from __future__ import annotations

import json
from pathlib import Path

from project.history_dashboard import load_history_entries, render_dashboard_html, write_dashboard



def _history_payload(generated_at: str, score: float, regime: str) -> dict:
    return {
        "title": "Test Report",
        "generated_at": generated_at,
        "data_source": "sample",
        "regime": {
            "regime_label": regime,
            "regime_score": score - 0.2,
            "credit_regime_flag": "credit_stress_severe" if regime == "credit_stress" else "neutral",
            "inflation_regime_flag": "inflation_shock_broad" if regime == "inflation_shock" else "neutral",
        },
        "cycle": {"phase_label": "upswing", "phase_angle_deg": 14.2},
        "score": {"total_score": score},
        "spot_signal": {
            "action": "buy_window" if score >= 0.6 else "watch",
            "second_leg_risk": "low",
            "adjusted_score": round(score - 0.05, 2),
            "regime_penalty": 0.05,
            "risk_off_relief_applied": regime == "risk_off" and score >= 0.48,
            "recovery_evidence": {"score": round(score - 0.02, 2), "grade": "confirmed" if score >= 0.6 else "building", "summary": "phase2"},
            "blocker_assessment": {"level": "none" if regime == "risk_on" else "caution", "summary": "phase2 blocker"},
            "action_decision": {"action": "buy_window" if regime == "risk_on" else "watch", "mode": "phase2"},
            "rationale": ["score check", "cycle check"],
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
        "sector_rotation": {
            "table": [
                {
                    "ticker": "XLE",
                    "sector_name_ja": "エネルギー",
                    "return_12w": 0.12,
                    "rank": 1,
                    "rotation_phase": "leading",
                    "rotation_phase_ja": "先導",
                }
            ],
            "history": [
                {
                    "sector": "XLE",
                    "x_2w_ago": 0.1,
                    "y_2w_ago": 0.2,
                    "x_1w_ago": 0.2,
                    "y_1w_ago": 0.4,
                    "x_current": 0.5,
                    "y_current": 0.8,
                    "avg_length_12w": 0.3,
                }
            ]
        },
        "asset_compare": [
            {
                "asset_class": "US_Stocks",
                "ticker": "SPY",
                "ticker_name_ja": "米国大型株ETF",
                "momentum_12w": 0.08,
                "annualized_volatility": 0.14,
                "max_drawdown": -0.12,
            }
        ],
        "warnings": [],
        "analogues": [],
        "investment_candidates": {
            "tier": "watch",
            "label": "観察候補",
            "summary": "まだ強い推奨ではないものの、追う価値のある候補です。",
            "preferred_asset_class": {"asset_class": "US_Stocks", "ticker": "SPY", "ticker_name_ja": "米国大型株ETF", "momentum_12w": 0.08},
            "preferred_sector": {"ticker": "XLE", "sector_name_ja": "エネルギー", "return_12w": 0.12, "rotation_phase_ja": "先導"},
            "candidate_tickers": [{"ticker": "SPY", "label": "米国大型株ETF", "kind": "asset"}],
            "rationale": ["スポット投資判断は watch です。"],
        },
        "recovery_candidates": {
            "tier": "build",
            "label": "仕込み候補",
            "summary": "下落後の反転初期として監視したい候補があります。",
            "preferred_asset_class": {"label": "Gold", "ticker": "GLD", "ticker_name_ja": "金ETF", "momentum_4w": 0.03},
            "preferred_sector": {"ticker": "XLV", "ticker_name_ja": "ヘルスケアセクターETF", "momentum_4w": 0.028},
            "candidate_tickers": [{"ticker": "GLD", "label": "金ETF", "kind": "asset"}],
            "rationale": ["資産候補 GLD は 4週 +0.0300、12週 -0.0200、最大DD -0.1400 です。"],
        },
        "regime_leading_candidates": {
            "tier": "priority",
            "label": "レジーム先回り候補",
            "summary": "次のレジームで効きやすい資産・地域・セクターの候補があります。",
            "preferred_sector": {"ticker": "XLU", "ticker_name_ja": "公益事業セクターETF", "momentum_4w": 0.021, "momentum_12w": 0.012},
            "preferred_region": {"ticker": "EWJ", "ticker_name_ja": "日本株ETF", "momentum_4w": 0.02, "momentum_12w": 0.015},
            "preferred_asset_class": {"ticker": "GLD", "ticker_name_ja": "金ETF", "momentum_4w": 0.019, "momentum_12w": 0.011},
            "candidate_tickers": [
                {"ticker": "XLU", "label": "公益事業セクターETF", "kind": "sector", "reason": "改善で4週改善、12週は過熱前"},
                {"ticker": "EWJ", "label": "日本株ETF", "kind": "region", "reason": "地域全体で短期改善、まだ過熱前"},
                {"ticker": "GLD", "label": "金ETF", "kind": "asset", "reason": "資産クラスで短期改善、まだ過熱前"},
            ],
            "rationale": ["現レジーム transition に対して XLU はテーマ相性 1.00 です。"],
        },
        "data_availability": [
            {
                "requested_ticker": "SPY",
                "requested_ticker_name_ja": "米国大型株ETF",
                "used_ticker": "VOO",
                "used_ticker_name_ja": "S&P500連動ETF",
                "status": "proxy_fallback",
                "message": "proxy fallback used",
                "alternatives": ["VOO"],
                "alternatives_name_ja": ["S&P500連動ETF"],
            }
        ],
    }


def test_load_history_entries_summarizes_reports(tmp_path: Path):
    history_dir = tmp_path / "reports" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    payload = _history_payload("2026-03-19T21:20:30", 0.61, "risk_on")
    (history_dir / "report_2026-03-19_212030.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    entries = load_history_entries(history_dir)
    assert len(entries) == 1
    assert entries[0]["regime"]["label"] == "リスクオン"
    assert entries[0]["top_sector"]["label"] == "エネルギー"
    assert entries[0]["availability_summary"]["issues"] == 1
    assert entries[0]["adjusted_score"] == 0.56
    assert entries[0]["regime_penalty"] == 0.05
    assert entries[0]["regime"]["credit_flag"] == "neutral"
    assert entries[0]["alerts"][0]["category_label"] == "生活影響警告"
    assert entries[0]["investment_candidates"]["label"] == "観察候補"
    assert entries[0]["recovery_candidates"]["label"] == "仕込み候補"
    assert entries[0]["regime_leading_candidates"]["label"] == "レジーム先回り候補"
    assert entries[0]["spot_signal"]["recovery_evidence"]["grade"] == "confirmed"
    assert entries[0]["spot_signal"]["blocker_assessment"]["level"] == "none"
    assert entries[0]["spot_signal"]["action_decision"]["action"] == "buy_window"


def test_write_dashboard_creates_interactive_html(tmp_path: Path):
    work_dir = tmp_path / "dashboard"
    history_dir = work_dir / "reports" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    first = _history_payload("2026-03-19T21:20:30", 0.61, "risk_on")
    second = _history_payload("2026-03-19T21:25:30", 0.42, "risk_off")
    (work_dir / "reports").mkdir(parents=True, exist_ok=True)
    (history_dir / "report_2026-03-19_212030.json").write_text(
        json.dumps(first, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (history_dir / "report_2026-03-19_212530.json").write_text(
        json.dumps(second, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (work_dir / "reports" / "report_summary.json").write_text(
        json.dumps(second, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    dashboard_path = write_dashboard(work_dir / "reports")
    html = dashboard_path.read_text(encoding="utf-8")

    assert dashboard_path.name == "dashboard.html"
    assert "Market History Dashboard" in html
    assert "今回の実行結果" in html
    assert "最新の実行結果" in html
    assert "過去履歴ブラウズ" in html
    assert "今回の実行は live 取得ではありません" in html
    assert "再生" in html
    assert "関係マップ" in html
    assert "警告レイヤー" in html
    assert "追随候補" in html
    assert "先回り候補" in html
    assert "レジーム先回り" in html
    assert "detailTableDisclosure" in html
    assert "container-type: inline-size" in html
    assert "SPY" in html
    assert "リスクオン" in html
    assert "リスクオフ" in html
    assert "信用ストレス" in html
    assert "インフレ系" in html
    assert "初期回復" in html
    assert "上昇再開の証拠" in html
    assert "騙し上昇の警戒" in html
    assert "新判断" in html
    assert "校正基準の見方" in html
    assert "主基準: daily_latest" in html
    assert "生活コスト上昇警戒" in html
    assert ".severity-inline.caution" in html
    assert "formatAlertSeverityInline" in html
    assert ".risk-stage-inline.caution" in html
    assert "formatRiskInline" in html
    assert "emphasizeRiskText" in html
    assert "formatActionInline" in html
    assert "nodeSpotSub" in html
    assert "nodeAlertsSub" in html
    assert "観察候補" in html
    assert "仕込み候補" in html
    assert "レジーム先回り候補" in html
    assert "追随候補の詳細" in html
    assert "先回り候補の詳細" in html
    assert "レジーム先回り候補の詳細" in html
    assert '"meta": {' in html
    assert '<polygon' in html
    assert 'report.html' in html
    assert '最新レポートを見る' in html
    assert '先々週・先週・今週の3点と2本のベクトル' in html


def test_render_dashboard_html_handles_empty_history():
    html = render_dashboard_html([])
    assert "履歴データがありません" in html
    assert '"history": []' in html
    assert '"current_run": null' in html
    assert '"primary_basis": "daily_latest"' in html
