from __future__ import annotations

import html
import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from project.action_schema import ACTION_LABELS_JA, action_label_ja
from project.history_dashboard import load_history_entries
from project.report_sections.data_quality_section import data_quality_html_rows, data_quality_markdown_lines
from project.sector_labeling import classify_sector_candidate
from project.sector_vector_analysis import calculate_sector_vectors

STATUS_LABELS = {
    "ok": "取得成功",
    "proxy_fallback": "代替ティッカーで取得",
    "sample_fallback": "サンプルデータ代替",
    "unavailable": "未取得",
}

ACTION_LABELS = ACTION_LABELS_JA

RISK_LABELS = {
    "extreme": "非常に高い",
    "high": "高い",
    "moderate": "中程度",
    "low": "低い",
}

REGIME_LABELS = {
    "risk_on": "リスクオン",
    "transition": "移行局面",
    "risk_off": "リスクオフ",
    "credit_stress": "信用ストレス",
    "early_recovery": "初期回復",
    "inflation_shock": "インフレショック",
    "stagflation_warning": "スタグフレーション警戒",
    "data_unavailable": "判定保留",
}

CYCLE_LABELS = {
    "upswing": "上昇局面",
    "late_cycle": "終盤局面",
    "recovery": "回復局面",
    "downswing": "下降局面",
    "insufficient_data": "データ不足",
}

DISPLAY_TOKEN_LABELS = {
    "transition": "移行局面",
    "late_cycle": "終盤局面",
    "upswing": "上昇局面",
    "downswing": "下降局面",
    "recovery": "回復局面",
    "risk_on": "リスクオン",
    "risk_off": "リスクオフ",
    "credit_stress": "信用ストレス",
    "early_recovery": "初期回復",
    "inflation_shock": "インフレショック",
    "stagflation_warning": "スタグフレーション警戒",
    "wait": "待機",
    "watch": "監視継続",
    "hold": "保留",
    "confirmed": "確認済み",
    "caution": "注意",
    "weak": "弱い",
    "active": "実運用",
    "diagnostic_only": "診断専用",
    "not_evaluable": "評価不能",
    "unavailable": "未取得",
    "informational": "参考表示",
    "flat": "横ばい",
    "rising": "上昇",
    "weakening": "弱含み",
    "manual_file_missing": "手動CSV未設定",
    "endpoint_not_resolved": "取得先未確定",
    "price_metrics_missing": "価格指標未接続",
    "split_or_discontinuity_suspected": "分割・データ断絶の疑い",
    "risk_signal_excluded": "危険シグナルから除外",
    "buy_window_count_is_zero": "買い検討ゾーンの件数不足",
    "insufficient_forward_return_evidence": "将来リターン検証の証拠不足",
    "no_trigger_evidence": "トリガー証拠なし",
    "confidence_fallback_review": "信頼度が暫定レビュー",
    "score_shortfall": "スコア不足",
    "recovery_evidence_weak": "回復証拠が弱い",
    "evidence_building_with_caution": "証拠形成中・注意",
    "sample_fallback_present": "サンプル代替あり",
    "fallback_review": "暫定レビュー",
    "low_precision": "精度不足",
    "pass": "通過",
    "failed": "失敗",
    "ISSUE_COUNTS_NOT_AVAILABLE": "市場幅件数を取得できません",
    "ACCESS_DENIED": "アクセス拒否",
    "MANDATORY_FIELD_MISSING": "必須項目不足",
}

DISPLAY_PHRASE_LABELS = {
    "recovery evidence weak": "回復証拠が弱い",
    "score shortfall": "スコア不足",
    "False": "いいえ",
    "True": "はい",
}

SECTION_EXPLANATIONS = {
    "regime": "市場レジームは、モメンタム、トレンド強度、最大ドローダウン、ボラティリティ圧縮をまとめて地合いを分類したものです。",
    "cycle": "サイクル判定は週次データの位相から、相場が上昇・終盤・回復・下降のどこに近いかを見る補助指標です。",
    "score": "合成スコアは 0 から 1 の範囲で、数値が高いほど押し目検討の条件が揃っていることを示します。",
    "spot": "スポット投資判定は、地合いとサイクルとドローダウンを合わせて、今すぐ強気に入るか、監視か、待機かを示します。",
    "sector": "セクターローテーションは 12 週騰落率の順位で、資金がどこへ向かっているかを見るための一覧です。簡易ローテーション図は、順位と騰落率を円上に置いた見やすい補助図です。",
    "asset": "資産クラス比較は、各資産の 12 週モメンタム、年率ボラティリティ、最大ドローダウンを並べて相対比較するものです。",
    "credit": "信用監視は、ハイイールド債、投資適格社債、その比率を週次変化率と z スコアで並べ、株価だけでは見えにくい信用市場の悪化や改善を補助的に見るものです。",
    "inflation": "インフレ監視は、原油、金、ドル指数を週次変化率と z スコアで並べ、物価圧力や安全資産選好が強まっていないかを見る補助セクションです。",
    "japan_risk": "円建て・為替リスクは、USDJPY と外貨建て資産の円建て換算を使い、日本円で見た実質的な値動きと為替寄与を確認する補助層です。",
    "risk_lines": "危険ライン監視は、VIX、MOVE、米10年、原油、ドル、SPY、HYG、LQD、HYG/LQD をまとめて、通常・警戒・危険ライン・非常に危険ラインのどこにあるかを示す判定層です。",
    "analogues": "類似局面は、直近 12 週の値動きに近い過去パターンを探し、その後 12 週の結果を参考情報として表示します。",
    "availability": "データ取得状況では、各系列が主系列で取れたか、代替ティッカーへ切り替わったか、サンプル代替か、完全未取得かを示します。",
    "diagnostics": "接続診断では、今回の実行が実データ取得だったか、配布版実行か、失敗時にどのホストや例外が出たかを後から追えるようにまとめます。",
    "decision_reasons": "判定理由は、地合い、サイクル、合成スコア、信用市場の補助情報を文章でつないだ要約です。数値一覧だけで見落としやすい悪化要因を先に読むために使います。",
    "candidates": "投資候補は、既存の地合い判定を前提に、相対強度の高い資産クラスや先導セクターを候補として整理する補助層です。強い推奨ではなく、優先候補・観察候補・候補なしの三段で示します。",
    "multi_asset_candidates": "資産クラス別の確認候補は、株式・ゴールド・債券・現金待機を同じ買い候補度に混ぜず、役割別に整理する補助層です。",
    "domestic_danger_context": "国内文脈の補助危険確認は、国内株式、円建て債券、国内REIT、円建て金、為替、JGB利回り、CPI/BOJ取得状況を、既存の危険ラインとは分けて見る表示専用の補助層です。",
    "japan_resident_integrated_risk_context": "日本在住者向け統合リスク文脈は、米国・グローバル危険ライン、国内危険文脈、為替、国内金利、国内インフレのデータ制約を一つに並べる表示専用の補助層です。",
    "hindenburg_omen": "ヒンデンブルグオーメンは米国市場幅の分裂を確認する補助指標です。単独では売買判断に使いません。",
    "recovery_candidates": "先回り候補は、今は強くなくても、下落後に改善初期へ入りつつある資産やセクターを拾う補助層です。安いだけでなく、短期の改善と深い調整の両方を見ます。",
    "regime_leading_candidates": "レジーム先回り候補は、次の地合いで効きやすいセクターテーマを拾う補助層です。価格の底打ちだけではなく、現レジームとの相性と直近の改善兆候を合わせて見ます。",
    "alerts": "警告レイヤーは、既存の市場判定を上書きせずに、内部ロジックがどこで警戒を発火しているかを見えるようにする補助層です。市場警告、生活影響警告、補足メモに分けて表示します。",
}


def write_reports(
    report: dict[str, Any],
    reports_dir: str | Path,
    sample_output_dir: str | Path | None = None,
) -> tuple[Path, Path, Path, Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    history_path = reports_path / "history"
    history_path.mkdir(parents=True, exist_ok=True)

    markdown_text = render_markdown(report)
    developer_markdown_text = render_developer_diagnostics_markdown(report)
    history_entries = load_history_entries(history_path)
    html_text = render_html(report, history_entries=history_entries)
    supplement_html_text = render_supplement_dashboard_html(report, history_entries=history_entries)
    timestamp = _timestamp_slug(report["generated_at"])

    markdown_path = reports_path / "report.md"
    html_path = reports_path / "report.html"
    developer_markdown_path = reports_path / "developer_diagnostics.md"
    supplement_html_path = reports_path / "supplement_dashboard.html"
    history_markdown_path = history_path / f"report_{timestamp}.md"
    history_html_path = history_path / f"report_{timestamp}.html"
    history_json_path = history_path / f"report_{timestamp}.json"

    markdown_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    developer_markdown_path.write_text(developer_markdown_text, encoding="utf-8")
    supplement_html_path.write_text(supplement_html_text, encoding="utf-8")
    history_markdown_path.write_text(markdown_text, encoding="utf-8")
    history_html_path.write_text(html_text, encoding="utf-8")

    if sample_output_dir is not None:
        sample_path = Path(sample_output_dir)
        sample_path.mkdir(parents=True, exist_ok=True)
        (sample_path / "report_sample.md").write_text(markdown_text, encoding="utf-8")
        (sample_path / "report_sample.html").write_text(html_text, encoding="utf-8")
        (sample_path / "developer_diagnostics_sample.md").write_text(developer_markdown_text, encoding="utf-8")
        (sample_path / "supplement_dashboard_sample.html").write_text(supplement_html_text, encoding="utf-8")

    return markdown_path, html_path, history_markdown_path, history_html_path, history_json_path


def _risk_stage_tone(stage_key: str | None) -> str:
    if stage_key == "extreme_danger_line_reached":
        return "extreme"
    if stage_key == "danger_line_reached":
        return "danger"
    if stage_key in {"credit_spillover_initial", "caution"}:
        return "caution"
    return "normal"


def _risk_label_tone(label: str | None) -> str:
    normalized = str(label or "").strip()
    lowered = normalized.lower()
    if "非常に危険" in normalized or "extreme" in lowered:
        return "extreme"
    if "危険" in normalized or "danger" in lowered:
        return "danger"
    if any(token in normalized for token in ("警戒", "警告")) or any(token in lowered for token in ("warning", "caution")):
        return "caution"
    return "normal"


def _risk_badge_markdown(label: str | None, tone: str) -> str:
    safe = html.escape(str(label or "-"))
    if tone == "extreme":
        return f'<span style="color:#c53030;"><strong>{safe}</strong></span>'
    if tone == "danger":
        return f'<span style="color:#c05621;"><strong>{safe}</strong></span>'
    if tone == "caution":
        return f'<span style="color:#1f2933;"><strong>{safe}</strong></span>'
    return f"**{safe}**"


def _risk_badge_html(label: str | None, tone: str) -> str:
    safe = html.escape(str(label or "-"))
    if tone == "normal":
        return f"<strong>{safe}</strong>"
    return f'<span class="risk-badge {tone}">{safe}</span>'


def _format_risk_threshold_markdown(value: Any) -> str:
    text = str(value or "-").replace("/", "\n  ")
    return text


def _format_risk_threshold_html(value: Any) -> str:
    text = html.escape(str(value or "-"))
    return text.replace("/", "<br>")


def _format_risk_threshold_beginner_html(value: Any) -> str:
    text = str(value or "-")
    if text == "-":
        return "-"
    parts = []
    metric_labels = {
        "drawdown_13w": "13週の下落率",
        "drawdown_zscore": "下落の大きさ",
        "roc_1w": "1週の変化率",
        "roc_2w": "2週の変化率",
        "roc_4w": "4週の変化率",
        "roc_8w": "8週の変化率",
        "roc_z_1w": "1週変化の強さ",
        "roc_z_2w": "2週変化の強さ",
        "roc_z_4w": "4週変化の強さ",
        "roc_z_8w": "8週変化の強さ",
        "level_percentile": "水準の高さ",
        "level_zscore": "水準の強さ",
        "level_and_roc_4w": "水準と4週変化",
        "level_and_roc_8w": "水準と8週変化",
    }
    for raw_part in text.split("/"):
        metric, sep, raw_number = raw_part.partition(":")
        label = metric_labels.get(metric.strip(), metric.strip())
        number = raw_number.strip() if sep else ""
        parts.append(f"{label}: {number}" if number else label)
    return "<br>".join(html.escape(part) for part in parts)


def _display_bool(value: Any) -> str:
    return "はい" if bool(value) else "いいえ"


def _localize_display_text(value: Any) -> str:
    if isinstance(value, bool):
        return _display_bool(value)
    text = str(value)
    for src, dst in sorted(DISPLAY_PHRASE_LABELS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(src, dst)
    for src, dst in sorted(DISPLAY_TOKEN_LABELS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(src, dst)
    text = text.replace("legacy 判定", "旧判定")
    text = text.replace("rule単位", "ルール単位")
    return text


def _threshold_rule_certification_markdown_lines(report: dict[str, Any]) -> list[str]:
    payload = report.get("threshold_rule_certification") or {}
    summary = payload.get("summary") or {}
    blocking = payload.get("top_blocking_reasons") or []
    reasons = ", ".join(_localize_display_text(row.get("reason")) for row in blocking[:4] if row.get("reason")) or "-"
    return [
        "## しきい値ルール認証",
        f"- 認証済みルール: {summary.get('certified_count', 0)}",
        f"- 条件付きルール: {summary.get('conditional_count', 0)}",
        f"- 診断専用: {summary.get('diagnostic_only_count', 0)}",
        f"- 保留 / 評価不能: {summary.get('hold_count', 0)} / {summary.get('not_evaluable_count', 0)}",
        f"- 最終判断への影響: {_display_bool(payload.get('currently_affects_final_action', False))}",
        f"- 主な阻害理由: {reasons}",
    ]


def _threshold_rule_certification_html(report: dict[str, Any]) -> str:
    payload = report.get("threshold_rule_certification") or {}
    summary = payload.get("summary") or {}
    blocking = payload.get("top_blocking_reasons") or []
    reasons = "".join(
        f"<li>{html.escape(_localize_display_text(row.get('reason', '-')))}: {html.escape(str(row.get('count', 0)))}</li>"
        for row in blocking[:4]
    )
    if not reasons:
        reasons = "<li>-</li>"
    return f"""
    <section class="card">
      <h2>しきい値ルール認証</h2>
      <ul>
        <li>認証済みルール: {html.escape(str(summary.get('certified_count', 0)))}</li>
        <li>条件付きルール: {html.escape(str(summary.get('conditional_count', 0)))}</li>
        <li>診断専用: {html.escape(str(summary.get('diagnostic_only_count', 0)))}</li>
        <li>保留 / 評価不能: {html.escape(str(summary.get('hold_count', 0)))} / {html.escape(str(summary.get('not_evaluable_count', 0)))}</li>
        <li>最終判断への影響: {html.escape(_display_bool(payload.get('currently_affects_final_action', False)))}</li>
      </ul>
      <p>主な阻害理由</p>
      <ul>{reasons}</ul>
    </section>
    """


def _multi_asset_candidate_markdown_lines(report: dict[str, Any]) -> list[str]:
    payload = report.get("multi_asset_candidates") or {}
    if not payload:
        return []
    lines = ["", "## 資産クラス別の確認候補", f"- {SECTION_EXPLANATIONS['multi_asset_candidates']}"]
    lines.append(f"- 要約: {payload.get('summary', '-')}")
    lines.append(f"- 注意: {payload.get('disclaimer', '-')}")
    lines.append(f"- 最終判断への影響: {_display_bool(payload.get('affects_final_action', False))}")
    lines.append(f"- 買い候補度への影響: {_display_bool(payload.get('affects_buy_readiness_score', False))}")
    for row in payload.get("candidates", []):
        metrics = row.get("metrics") or {}
        metric_text = _market_metric_summary(metrics)
        lines.append(
            "- {label}: {symbol} ({name}) / 役割: {role} / 状態: {status} / 分類: {category} / データ: {available} / 指標: {metrics}".format(
                label=row.get("asset_class_label", "-"),
                symbol=row.get("symbol", "-"),
                name=row.get("display_name", "-"),
                role=row.get("role_label", "-"),
                status=_multi_asset_status_label(row.get("status")),
                category=_multi_asset_reason_category_label(row.get("reason_category")),
                available="あり" if row.get("source_data_available") else "なし",
                metrics=metric_text,
            )
        )
        lines.append(f"  - 理由: {_localize_display_text(row.get('reason', '-'))}")
        lines.append(f"  - 注意: {_localize_display_text(row.get('caution', '-'))}")
        context_line = _japan_resident_context_markdown(row)
        if context_line:
            lines.append(f"  - 日本居住者向け確認: {context_line}")
    return lines


def _multi_asset_candidate_html(report: dict[str, Any]) -> str:
    payload = report.get("multi_asset_candidates") or {}
    if not payload:
        return ""
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('asset_class_label', '-')))}</td>"
        f"<td>{html.escape(str(row.get('symbol', '-')))}<br><span style='color:#52606d'>{html.escape(str(row.get('display_name', '-')))}</span></td>"
        f"<td>{html.escape(str(row.get('role_label', '-')))}</td>"
        f"<td>{html.escape(_multi_asset_status_label(row.get('status')))}</td>"
        f"<td>{'あり' if row.get('source_data_available') else 'なし'}</td>"
        f"<td>{html.escape(_localize_display_text(row.get('reason', '-')))}<br><span style='color:#52606d'>分類: {html.escape(_multi_asset_reason_category_label(row.get('reason_category')))} / 指標: {html.escape(_market_metric_summary(row.get('metrics') or {}))} / 注意: {html.escape(_localize_display_text(row.get('caution', '-')))}</span>{_japan_resident_context_html(row)}</td>"
        "</tr>"
        for row in payload.get("candidates", [])
    )
    if not rows:
        rows = "<tr><td colspan='6'>候補データなし</td></tr>"
    return f"""
    <section class=\"section\">
      <h2>資産クラス別の確認候補</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['multi_asset_candidates'])}</p>
      <p>{html.escape(str(payload.get('summary', '-')))}</p>
      <p><strong>注意:</strong> {html.escape(str(payload.get('disclaimer', '-')))}</p>
      <ul>
        <li>最終判断への影響: {html.escape(_display_bool(payload.get('affects_final_action', False)))}</li>
        <li>買い候補度への影響: {html.escape(_display_bool(payload.get('affects_buy_readiness_score', False)))}</li>
      </ul>
      <table>
        <thead><tr><th>資産クラス</th><th>候補</th><th>役割</th><th>状態</th><th>データ</th><th>理由と注意</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """


def _multi_asset_status_label(status: Any) -> str:
    labels = {
        "candidate": "株式候補",
        "watch": "確認中",
        "informational": "参考表示",
        "unavailable": "データ不足",
        "not_available": "データ不足",
        "wait": "待機",
        "neutral": "参考表示",
    }
    return labels.get(str(status), "確認中")


def _multi_asset_reason_category_label(category: Any) -> str:
    labels = {
        "defensive_context": "守り候補の確認",
        "rate_sensitive_context": "金利に敏感な確認",
        "jpy_rate_context": "円金利の確認",
        "jp_equity_context": "日本株の確認",
        "jp_reit_context": "国内REITの確認",
        "insufficient_data": "データ不足",
        "wait_context": "待機判断の補助",
        "partial_data_context": "部分データ",
    }
    return labels.get(str(category), "補助確認")


def _japan_resident_context_markdown(row: dict[str, Any]) -> str:
    if "japan_resident_context_score" not in row:
        return ""
    score = _display_number(row.get("japan_resident_context_score"))
    status = _multi_asset_status_label(row.get("japan_resident_context_status"))
    category = _multi_asset_reason_category_label(row.get("japan_resident_reason_category"))
    components = row.get("japan_resident_context_components") or {}
    component_text = _japan_resident_component_summary(components)
    return f"状態: {status} / 分類: {category} / 確認材料スコア: {score} / {component_text}"


def _japan_resident_context_html(row: dict[str, Any]) -> str:
    context = _japan_resident_context_markdown(row)
    if not context:
        return ""
    return f"<br><span style='color:#52606d'>日本居住者向け確認: {html.escape(context)}</span>"


def _market_metric_summary(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "利用可能な表示指標なし"
    if _has_suspicious_metric_limitation(metrics.get("limitations")):
        limitations = metrics.get("limitations")
        parts = ["12週変化: 異常値疑いのため非採用", "最大DD: 異常値疑いのため参考外"]
        if limitations:
            parts.append("制約=" + ",".join(_localize_display_text(item) for item in limitations))
        return " / ".join(parts)
    parts = []
    for key, label in (
        ("current_value", "現在値"),
        ("change_4w", "4週"),
        ("change_12w", "12週"),
        ("trend_label", "傾向"),
        ("max_drawdown", "最大DD"),
    ):
        value = metrics.get(key)
        if value is not None:
            parts.append(f"{label}={_localize_display_text(_display_number(value))}")
    limitations = metrics.get("limitations")
    if limitations:
        parts.append("制約=" + ",".join(_localize_display_text(item) for item in limitations))
    return " / ".join(parts) if parts else "利用可能な表示指標なし"


def _has_suspicious_metric_limitation(limitations: Any) -> bool:
    if limitations is None:
        return False
    if isinstance(limitations, str):
        items = [limitations]
    elif isinstance(limitations, list | tuple | set):
        items = [str(item) for item in limitations]
    else:
        items = [str(limitations)]
    suspicious_markers = {
        "split_or_discontinuity_suspected",
        "suspicious_price_move",
        "risk_signal_excluded",
    }
    return any(item in suspicious_markers for item in items)


def _japan_resident_component_summary(components: dict[str, Any]) -> str:
    if not components:
        return "国内金利/為替/インフレ: データ不足"
    labels = {
        "domestic_rate": "国内金利",
        "fx": "為替",
        "inflation": "国内インフレ",
        "jpy_relevance": "円建て文脈",
        "data_quality": "データ品質",
    }
    parts = [f"{label}={_display_number(components.get(key))}" for key, label in labels.items() if key in components]
    return " / ".join(parts) if parts else "国内金利/為替/インフレ: データ不足"


def _risk_line_confidence_audit_markdown_lines(audit: dict[str, Any]) -> list[str]:
    dxy_label = ((audit.get("dxy_role") or {}).get("label")) or "-"
    jpy_fx_label = ((audit.get("jpy_fx_role") or {}).get("label")) or "-"
    return [
        f"- 信頼度監査: {audit.get('monitoring_scope_label', '-')}",
        (
            "- 閾値由来: "
            f"暫定レビュー={audit.get('fallback_review_rules', 0)} / "
            f"精度不足={audit.get('low_precision_rules', 0)} / "
            f"通過={audit.get('pass_rules', 0)}"
        ),
        f"- DXY と円建てFX: {dxy_label} / {jpy_fx_label}",
        f"- 総合ストレス指数と危険ラインの発火経路: {_localize_display_text(audit.get('composite_trigger_relationship', '-')).replace('trigger path', '危険ラインの発火経路').replace('overlay', '補助判定')}",
    ]


def _risk_line_confidence_audit_html(audit: dict[str, Any]) -> str:
    if not audit:
        return ""
    items = "".join(
        f"<li>{html.escape(line[2:] if line.startswith('- ') else line)}</li>" for line in _risk_line_confidence_audit_markdown_lines(audit)
    )
    return f"<ul>{items}</ul>"


def _risk_accepted_rule_summary(row: dict[str, Any]) -> str:
    accepted = row.get("accepted_rule") or {}
    if not accepted:
        return str(row.get("line_reason") or "採用可能な発火基準なし")
    stage = _risk_stage_label(str(accepted.get("stage") or ""))
    feature = str(accepted.get("feature") or "-")
    value = _display_compact_number(accepted.get("value"), 4)
    threshold = _display_compact_number(accepted.get("threshold"), 4)
    direction = "以上" if str(accepted.get("direction") or "higher") == "higher" else "以下"
    confidence = _risk_confidence_label(accepted.get("confidence"))
    source = _risk_source_label(accepted.get("source"))
    return f"{stage}: {feature}={value} / 基準 {threshold} {direction} / 根拠 {source}・{confidence}"


def _risk_diagnostic_rule_summary(row: dict[str, Any]) -> str:
    hits = row.get("diagnostic_rule_hits") or []
    if not hits:
        return "なし"
    parts = []
    for hit in hits[:3]:
        stage = _risk_stage_label(str(hit.get("stage") or ""))
        feature = str(hit.get("feature") or "-")
        value = _display_compact_number(hit.get("value"), 4)
        threshold = _display_compact_number(hit.get("threshold"), 4)
        direction = "以上" if str(hit.get("direction") or "higher") == "higher" else "以下"
        confidence = _risk_confidence_label(hit.get("confidence"))
        reason = _risk_rule_reason_label(hit.get("reason"))
        reason_suffix = f" / {reason}" if reason else ""
        parts.append(f"{stage}: {feature}={value} / 基準 {threshold} {direction} / {confidence} のため参考扱い{reason_suffix}")
    return " ; ".join(parts)


def _risk_stage_label(stage: str) -> str:
    return {
        "warning": "警戒",
        "danger": "危険",
        "extreme": "非常に危険",
        "normal": "通常",
    }.get(stage, stage or "-")


def _risk_source_label(value: Any) -> str:
    return {
        "historical_quantile": "履歴検証",
        "fallback_review": "暫定レビュー",
        "not_evaluable": "active基準",
        "insufficient_data": "データ不足",
    }.get(str(value or ""), str(value or "-"))


def _risk_confidence_label(value: Any) -> str:
    return {
        "high": "高",
        "medium": "中",
        "low": "低",
        "fallback_review": "暫定レビュー",
        "not_evaluable": "証拠メタ不足",
    }.get(str(value or ""), str(value or "-"))


def _risk_rule_reason_label(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    if "fallback_review thresholds are diagnostic only" in text:
        return "診断専用の暫定基準"
    if "insufficient completed forward-return evidence" in text:
        return "完了した将来リターン証拠不足"
    if "weak evidence" in text:
        return "証拠が弱く本判定には注意"
    return text


def _hindenburg_signal_label(signal: Any) -> str:
    return {
        "triggered_today": "本日点灯",
        "active": "点灯中",
        "not_triggered": "点灯なし",
        "unconfirmed": "未確定",
        "unavailable": "未取得",
    }.get(str(signal or ""), "未取得")


def _hindenburg_status_label(status: Any) -> str:
    return {
        "ok": "取得成功",
        "partial": "一部未確定",
        "unavailable": "未取得",
        "manual_file_missing": "手動CSV未設定",
        "data_unavailable": "取得不可",
        "auto_fetch_error": "自動取得失敗",
        "insufficient_history": "履歴不足",
        "parse_error": "CSV解析エラー",
    }.get(str(status or ""), str(status or "-"))


def _hindenburg_state_label(state: Any) -> str:
    return {
        "UNINITIALIZED": "未初期化",
        "UPDATING": "更新中",
        "CONFIRMED": "前営業日終値ベース・確定",
        "NO_UPDATE": "最新確定データ取得済み",
        "STALE": "データが古いため判定保留",
        "INSUFFICIENT_HISTORY": "履歴不足のため判定不能",
        "GAP_BLOCKED": "途中営業日の欠損により更新保留",
        "INVALID_DATA": "入力データ不正",
        "UPDATE_FAILED": "更新失敗・前回確定値を表示",
        "MIGRATION_REQUIRED": "移行が必要",
    }.get(str(state or ""), str(state or "-"))


def _hindenburg_summary_text(payload: dict[str, Any]) -> str:
    signal = str(payload.get("current_signal") or "unavailable")
    state = str(payload.get("state") or "")
    if state in {"UNINITIALIZED"}:
        return "ヒンデンブルグオーメン: 未初期化。取得可能な市場幅データがまだありません。"
    if payload.get("failure_code") == "ALL_PROVIDERS_UNAVAILABLE" and payload.get("is_previous_confirmed_result"):
        return "ヒンデンブルグオーメン: 3候補すべて取得不可・前回確定値を表示"
    if payload.get("failure_code") == "ALL_PROVIDERS_UNAVAILABLE":
        return "ヒンデンブルグオーメン: 3候補すべて取得不可・判定不能"
    if state == "UPDATE_FAILED" and payload.get("is_previous_confirmed_result"):
        return "ヒンデンブルグオーメン: 更新取得不可・前回確定値を表示しています。"
    if state == "INSUFFICIENT_HISTORY":
        return "ヒンデンブルグオーメン: 履歴不足のため判定できません。"
    if state == "GAP_BLOCKED":
        return "ヒンデンブルグオーメン: 途中営業日の欠損により更新を保留しています。"
    if state == "INVALID_DATA":
        return "ヒンデンブルグオーメン: 入力データ不正のため判定できません。"
    if state == "MIGRATION_REQUIRED":
        return "ヒンデンブルグオーメン: SQLite状態の移行が必要です。"
    if payload.get("stale_data"):
        return "ヒンデンブルグオーメン: データが古いため現在点灯は未確定。市場幅CSVの最新日が古いため、現在の点灯状態は判定できません。"
    if signal in {"triggered_today", "active"}:
        return (
            "ヒンデンブルグオーメンが点灯中です。これは米国市場幅の分裂を確認する補助指標です。"
            "単独では売買判断に使いません。他の危険ライン、信用、ボラティリティ指標と併せて確認してください。"
        )
    if signal == "not_triggered":
        return "ヒンデンブルグオーメン: 点灯なし"
    if payload.get("status") == "manual_file_missing":
        return "ヒンデンブルグオーメン: 未取得。市場幅CSVが未設定のため判定できません。"
    return f"ヒンデンブルグオーメン: {_hindenburg_signal_label(signal)}"


def _hindenburg_source_label(payload: dict[str, Any]) -> str:
    source_kind = str(payload.get("source_kind") or "")
    auto = payload.get("automatic_acquisition") or {}
    if source_kind == "builtin_provider_chain" and auto.get("success_label"):
        return "自動取得・実験的"
    if source_kind == "builtin_provider_chain":
        return "自動取得・実験的（未成立）"
    if source_kind == "manual_daily_input":
        return "手入力から更新"
    if source_kind == "local_manual_file":
        return "手動CSVから更新"
    if source_kind == "auto_csv":
        return "設定CSVから更新"
    return "取得元未確定"


def _yes_no(value: Any) -> str:
    return "はい" if bool(value) else "いいえ"


def _hindenburg_criteria_label(value: Any) -> str:
    labels = {
        "uptrend": "上昇トレンド",
        "new_highs_threshold": "新高値数の条件",
        "new_lows_threshold": "新安値数の条件",
        "negative_mcclellan": "マクレラン指標がマイナス",
        "high_low_balance": "新高値と新安値の比率",
    }
    return labels.get(str(value), str(value))


def _hindenburg_criteria_list(values: Any) -> str:
    return ", ".join(_hindenburg_criteria_label(value) for value in (values or [])) or "-"


def _hindenburg_criteria_summary(value: Any) -> str:
    text = str(value or "-")
    replacements = {
        "passed=": "通過=",
        "failed=": "未達=",
        "unknown=": "不明=",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _hindenburg_manual_link_html() -> str:
    return (
        '<a class="manual-link" href="../../docs/hindenburg_omen_data_acquisition.md" '
        'target="_blank" rel="noopener noreferrer">手動取得方法を開く</a>'
    )


def _hindenburg_omen_markdown_lines(report: dict[str, Any]) -> list[str]:
    payload = report.get("hindenburg_omen_context") or {}
    if not payload:
        return []
    lines = [
        "",
        "## ヒンデンブルグオーメン / 市場幅の補助確認",
        f"- {SECTION_EXPLANATIONS['hindenburg_omen']}",
        f"- 状態: {_hindenburg_status_label(payload.get('status'))}",
        f"- 更新状態: {_hindenburg_state_label(payload.get('state'))}",
        f"- 取得区分: {_hindenburg_source_label(payload)}",
        f"- 履歴進捗: {payload.get('history_progress_label') or '-'}",
        f"- 確定市場日: {payload.get('confirmed_market_date') or '-'}",
        f"- 現在シグナル: {_hindenburg_signal_label(payload.get('current_signal'))}",
        f"- 通知: {_hindenburg_summary_text(payload)}",
        f"- データ最新日: {payload.get('data_latest_date') or payload.get('latest_date') or '-'}",
        f"- 判定基準日: {payload.get('as_of_date') or '-'}",
        f"- データ鮮度不足: {_yes_no(payload.get('stale_data', False))}",
        f"- 最新点灯日: {payload.get('latest_trigger_date') or '-'}",
        f"- 発動終了日: {payload.get('active_until') or '-'}",
        f"- 発動期間（日数）: {payload.get('active_window_days', '-')}",
        f"- 新高値比率: {_display_number(payload.get('new_highs_pct'))}% / 新安値比率: {_display_number(payload.get('new_lows_pct'))}% / 判定しきい値: {_display_number(payload.get('threshold_pct'))}%",
        f"- マクレラン指標: {_display_number(payload.get('mcclellan_oscillator'))}",
        f"- 条件通過: {_hindenburg_criteria_list(payload.get('criteria_passed'))}",
        f"- 条件未達: {_hindenburg_criteria_list(payload.get('criteria_failed'))}",
        f"- 条件不明: {_hindenburg_criteria_list(payload.get('criteria_unknown'))}",
        f"- 最終判断への影響: {_display_bool(not payload.get('must_not_affect_final_action', True))}",
        f"- 買い候補度への影響: {_display_bool(not payload.get('must_not_affect_buy_readiness_score', True))}",
    ]
    if payload.get("provider_label") or payload.get("providers_attempted_count"):
        lines.append(
            f"- 取得元: {payload.get('provider_label') or '-'} / 試行数: {payload.get('providers_attempted_count', 0)} / 前回確定値表示: {_display_bool(payload.get('is_previous_confirmed_result', False))}"
        )
    auto = payload.get("automatic_acquisition") or {}
    if auto:
        lines.append(
            f"- 自動取得: {auto.get('label', '自動取得・実験的')} / 試行済み={_yes_no(auto.get('attempted', False))} / 試行対象={_yes_no(auto.get('eligible', False))} / 取得成功={_yes_no(auto.get('success_label', False))} / 理由={_localize_display_text(auto.get('reason', '-'))}"
        )
    for attempt in (payload.get("provider_attempts") or [])[:3]:
        lines.append(
            "- 取得試行: {provider} / 状態 {status} / 失敗理由 {failure}".format(
                provider=attempt.get("provider_label") or attempt.get("provider_id") or "-",
                status=_localize_display_text(attempt.get("status") or "-"),
                failure=_localize_display_text(attempt.get("failure_code") or "-"),
            )
        )
    if payload.get("limitations"):
        lines.append("- データ制約: " + " / ".join(_localize_display_text(item) for item in payload.get("limitations", [])))
    if payload.get("trigger_dates"):
        lines.append("- 点灯日: " + ", ".join(str(value) for value in payload.get("trigger_dates", [])))
    for period in (payload.get("active_periods") or [])[-3:]:
        lines.append(
            "- 発動期間: {start} から {end} / 点灯日数 {count} / 最新点灯日 {latest}".format(
                start=period.get("period_start", "-"),
                end=period.get("period_end", "-"),
                count=period.get("trigger_day_count", "-"),
                latest=period.get("latest_trigger_date", "-"),
            )
        )
    for row in (payload.get("daily_signals") or [])[-5:]:
        lines.append(
            "- シグナル履歴: {date} / {triggered} / {summary} / 新高値 {highs}% / 新安値 {lows}% / マクレラン {mcclellan}".format(
                date=row.get("date", "-"),
                triggered="点灯" if row.get("triggered") else "点灯なし",
                summary=_hindenburg_criteria_summary(row.get("criteria_summary", "-")),
                highs=_display_number(row.get("new_highs_pct")),
                lows=_display_number(row.get("new_lows_pct")),
                mcclellan=_display_number(row.get("mcclellan_oscillator")),
            )
        )
    return lines


def _hindenburg_omen_panel_html(payload: dict[str, Any], esc: Any) -> str:
    if not payload:
        return ""
    tone = (
        "bad"
        if payload.get("current_signal") in {"triggered_today", "active"}
        else "warn" if payload.get("current_signal") == "unconfirmed" else ""
    )
    period_rows = [
        [
            esc(period.get("period_start", "-")),
            esc(period.get("period_end", "-")),
            esc(period.get("trigger_day_count", "-")),
            esc(period.get("latest_trigger_date", "-")),
        ]
        for period in (payload.get("active_periods") or [])[-3:]
    ]
    history_rows = [
        [
            esc(row.get("date", "-")),
            "点灯" if row.get("triggered") else "点灯なし",
            esc(_hindenburg_criteria_summary(row.get("criteria_summary", "-"))),
            esc(_display_number(row.get("new_highs_pct"))),
            esc(_display_number(row.get("new_lows_pct"))),
            esc(_display_number(row.get("mcclellan_oscillator"))),
        ]
        for row in (payload.get("daily_signals") or [])[-5:]
    ]
    limitations = "".join(f"<li>{esc(item)}</li>" for item in payload.get("limitations", [])) or "<li>-</li>"
    period_table = _hindenburg_table_html(["開始日", "終了日", "点灯日数", "最新点灯日"], period_rows, esc)
    history_table = _hindenburg_table_html(["日付", "状態", "条件", "新高値比率", "新安値比率", "マクレラン"], history_rows, esc)
    return f"""
    <section class="mini-panel hindenburg-panel">
      <h3>ヒンデンブルグオーメン <span class="manual-link-wrap">{_hindenburg_manual_link_html()}</span></h3>
      <div class="mini-content">
        <div class="metric {tone}">
          <span>現在</span><strong>{esc(_hindenburg_signal_label(payload.get('current_signal')))}</strong>
        </div>
        <p>{esc(_hindenburg_summary_text(payload))}</p>
        <div class="inline-note">
          更新状態 {esc(_hindenburg_state_label(payload.get('state')))} / 確定市場日 {esc(payload.get('confirmed_market_date') or '-')} / 前回確定値表示 {esc(_display_bool(payload.get('is_previous_confirmed_result', False)))}<br>
          取得区分 {esc(_hindenburg_source_label(payload))} / 履歴進捗 {esc(payload.get('history_progress_label') or '-')}<br>
          取得元 {esc(payload.get('provider_label') or '-')} / 取得試行数 {esc(payload.get('providers_attempted_count', 0))}<br>
          データ最新日 {esc(payload.get('data_latest_date') or payload.get('latest_date') or '-')} / 判定基準日 {esc(payload.get('as_of_date') or '-')} / データ鮮度不足 {esc(_yes_no(payload.get('stale_data', False)))}<br>
          最新点灯日 {esc(payload.get('latest_trigger_date') or '-')} / 発動終了日 {esc(payload.get('active_until') or '-')}<br>
          新高値比率 {esc(_display_number(payload.get('new_highs_pct')))}% / 新安値比率 {esc(_display_number(payload.get('new_lows_pct')))}% / マクレラン {esc(_display_number(payload.get('mcclellan_oscillator')))}
        </div>
        <p>データ制約</p>
        <ul>{limitations}</ul>
        {period_table}
        {history_table}
      </div>
    </section>
    """


def _hindenburg_table_html(headers: list[str], rows: list[list[Any]], esc: Any) -> str:
    if not rows:
        return ""
    header_html = "".join(f"<th>{esc(header)}</th>" for header in headers)
    row_html = "".join("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows)
    return f"<div class='table-wrap'><table><thead><tr>{header_html}</tr></thead><tbody>{row_html}</tbody></table></div>"


def _domestic_danger_markdown_lines(report: dict[str, Any]) -> list[str]:
    payload = report.get("domestic_danger_context") or {}
    if not payload:
        return []
    lines = [
        "",
        "### 国内文脈の補助危険確認",
        f"- {SECTION_EXPLANATIONS['domestic_danger_context']}",
        f"- 判定: {_domestic_danger_level_label(payload.get('domestic_danger_level'))}",
        f"- 最終判断への影響: {_display_bool(not bool(payload.get('must_not_affect_final_action', True)))}",
        f"- 買い候補度への影響: {_display_bool(not bool(payload.get('must_not_affect_buy_readiness_score', True)))}",
    ]
    for reason in payload.get("domestic_danger_reasons", []):
        lines.append(f"- 理由: {_localize_display_text(reason)}")
    for row in payload.get("domestic_watch_items", []):
        reason = _domestic_danger_reason_text(row)
        row_limitations = row.get("limitations") or []
        limitation_text = f" / 制約: {', '.join(_localize_display_text(item) for item in row_limitations)}" if row_limitations else ""
        lines.append(
            "- {group}: {name} ({symbol}) / 状態: {status} / 補助判定: {level} / 理由: {reason}".format(
                group=row.get("group", "-"),
                name=row.get("name", "-"),
                symbol=row.get("symbol", "-"),
                status=_localize_display_text(row.get("status", "-")),
                level=_domestic_danger_level_label(row.get("level")),
                reason=f"{reason}{limitation_text}",
            )
        )
        lines.append(f"  - 注意: {_localize_display_text(row.get('caution', '-'))}")
    for limitation in payload.get("domestic_data_limitations", []):
        lines.append(f"- データ制約: {_localize_display_text(limitation)}")
    return lines


def _domestic_danger_level_label(level: Any) -> str:
    labels = {
        "normal": "通常",
        "watch": "確認",
        "caution": "注意",
        "unavailable": "データ不足",
    }
    return labels.get(str(level), "確認")


def _domestic_danger_table_html(payload: dict[str, Any], small_table: Any, esc: Any) -> str:
    def reason_with_metrics(row: dict[str, Any]) -> str:
        limitations = row.get("limitations") or []
        limitation_text = f" / 制約: {', '.join(_localize_display_text(item) for item in limitations)}" if limitations else ""
        return f"{_localize_display_text(_domestic_danger_reason_text(row))}{limitation_text}"

    rows = [
        [
            esc(row.get("group", "-")),
            esc(row.get("symbol", "-")),
            esc(row.get("name", "-")),
            esc(_domestic_danger_level_label(row.get("level"))),
            esc(reason_with_metrics(row)),
            esc(_localize_display_text(row.get("caution", "-"))),
        ]
        for row in payload.get("domestic_watch_items", [])
    ]
    return small_table(["分類", "系列", "名称", "補助判定", "理由", "注意"], rows)


def _domestic_danger_reason_text(row: dict[str, Any]) -> str:
    reason = str(row.get("reason", "-"))
    if _has_suspicious_metric_limitation(row.get("limitations")):
        metric_text = "12週変化: 異常値疑いのため非採用 / 最大DD: 異常値疑いのため参考外"
        if "指標:" in reason:
            return reason.split("指標:", maxsplit=1)[0].rstrip(" /") + f" / 指標: {metric_text}"
        return f"{reason} / 指標: {metric_text}"
    if "指標:" in reason:
        return reason
    return f"{reason} / 指標: {row.get('metrics', '-')}"


def _domestic_danger_panel_html(payload: dict[str, Any], small_table: Any, esc: Any, source_chip: Any) -> str:
    if not payload:
        return ""
    reason_items = (
        "".join(f"<li>{esc(_localize_display_text(reason))}</li>" for reason in payload.get("domestic_danger_reasons", [])) or "<li>-</li>"
    )
    limitation_items = (
        "".join(f"<li>{esc(_localize_display_text(item))}</li>" for item in payload.get("domestic_data_limitations", []))
        or "<li>追加のデータ制約はありません。</li>"
    )
    table = _domestic_danger_table_html(payload, small_table, esc)
    return (
        '<section class="panel mt"><h3>国内文脈の補助危険確認 {source}</h3>'
        "<p>{summary}</p>"
        '<ul class="compact-list">'
        "<li>補助判定: {level}</li>"
        "<li>国内資産: {asset_level}</li>"
        "<li>為替: {fx_level}</li>"
        "<li>国内金利・マクロ: {macro_level}</li>"
        "<li>国内値を使用: {uses_values}</li>"
        "<li>国内価格指標を使用: {uses_price_metrics}</li>"
        "<li>国内マクロ値を使用: {uses_macro_values}</li>"
        "<li>制約・代替データのみ: {uses_fallback_only}</li>"
        "<li>最終判断への影響: {final_action}</li>"
        "<li>買い候補度への影響: {readiness}</li>"
        "</ul>"
        '<div class="table-wrap mt">{table}</div>'
        '<h3 class="mt">国内文脈の理由</h3><ul class="compact-list">{reasons}</ul>'
        '<h3 class="mt">国内マクロ取得制約</h3><ul class="compact-list">{limitations}</ul>'
        "</section>"
    ).format(
        source=source_chip("国内文脈の補助危険確認"),
        summary=esc(SECTION_EXPLANATIONS["domestic_danger_context"]),
        level=esc(_domestic_danger_level_label(payload.get("domestic_danger_level"))),
        asset_level=esc(_domestic_danger_level_label(payload.get("domestic_asset_level"))),
        fx_level=esc(_domestic_danger_level_label(payload.get("domestic_fx_level"))),
        macro_level=esc(_domestic_danger_level_label(payload.get("domestic_macro_level"))),
        uses_values=esc(_display_bool(payload.get("uses_domestic_values", False))),
        uses_price_metrics=esc(_display_bool(payload.get("uses_domestic_price_metrics", False))),
        uses_macro_values=esc(_display_bool(payload.get("uses_domestic_macro_values", False))),
        uses_fallback_only=esc(_display_bool(payload.get("uses_only_fallback_or_limitations", False))),
        final_action=esc(_display_bool(not bool(payload.get("must_not_affect_final_action", True)))),
        readiness=esc(_display_bool(not bool(payload.get("must_not_affect_buy_readiness_score", True)))),
        table=table,
        reasons=reason_items,
        limitations=limitation_items,
    )


def _japan_resident_integrated_context_markdown_lines(report: dict[str, Any]) -> list[str]:
    payload = report.get("japan_resident_integrated_risk_context") or {}
    if not payload:
        return []
    lines = [
        "",
        "### 日本在住者向け統合リスク文脈",
        f"- {SECTION_EXPLANATIONS['japan_resident_integrated_risk_context']}",
        f"- 統合補助判定: {_domestic_danger_level_label(payload.get('combined_context_level'))}",
        f"- 米国・グローバル: {_domestic_danger_level_label(payload.get('global_risk_level'))}",
        f"- 国内: {_domestic_danger_level_label(payload.get('domestic_risk_level'))}",
        f"- 為替: {_domestic_danger_level_label(payload.get('fx_risk_level'))}",
        f"- 国内金利: {_domestic_danger_level_label(payload.get('rate_risk_level'))}",
        f"- 国内インフレデータ品質: {_localize_display_text(payload.get('inflation_data_quality', '-'))}",
        f"- 最終判断への影響: {_display_bool(not bool(payload.get('must_not_affect_final_action', True)))}",
        f"- 買い候補度への影響: {_display_bool(not bool(payload.get('must_not_affect_buy_readiness_score', True)))}",
    ]
    for reason in payload.get("primary_reasons", []):
        lines.append(f"- 理由: {_localize_display_text(reason)}")
    for row in payload.get("watch_items", []):
        lines.append(
            "- {group}: 補助判定 {level} / {summary} / 取得元={source}".format(
                group=row.get("group", "-"),
                level=_domestic_danger_level_label(row.get("level")),
                summary=_localize_display_text(row.get("summary", "-")),
                source=_localize_display_text(row.get("source", "-")),
            )
        )
    for limitation in payload.get("data_limitations", []):
        lines.append(f"- データ制約: {_localize_display_text(limitation)}")
    lines.append(f"- 注記: {_localize_display_text(payload.get('caveat', '-'))}")
    return lines


def _japan_resident_integrated_context_panel_html(payload: dict[str, Any], small_table: Any, esc: Any, source_chip: Any) -> str:
    if not payload:
        return ""
    level_rows = [
        ["統合補助判定", _domestic_danger_level_label(payload.get("combined_context_level"))],
        ["米国・グローバル", _domestic_danger_level_label(payload.get("global_risk_level"))],
        ["国内", _domestic_danger_level_label(payload.get("domestic_risk_level"))],
        ["為替", _domestic_danger_level_label(payload.get("fx_risk_level"))],
        ["国内金利", _domestic_danger_level_label(payload.get("rate_risk_level"))],
        ["国内インフレデータ品質", _localize_display_text(payload.get("inflation_data_quality", "-"))],
        ["最終判断への影響", _display_bool(not bool(payload.get("must_not_affect_final_action", True)))],
        ["買い候補度への影響", _display_bool(not bool(payload.get("must_not_affect_buy_readiness_score", True)))],
    ]
    item_rows = [
        [
            esc(row.get("group", "-")),
            esc(_domestic_danger_level_label(row.get("level"))),
            esc(_localize_display_text(row.get("summary", "-"))),
            esc(_localize_display_text(row.get("source", "-"))),
        ]
        for row in payload.get("watch_items", [])
    ]
    reason_items = (
        "".join(f"<li>{esc(_localize_display_text(reason))}</li>" for reason in payload.get("primary_reasons", [])) or "<li>-</li>"
    )
    limitation_items = (
        "".join(f"<li>{esc(_localize_display_text(item))}</li>" for item in payload.get("data_limitations", []))
        or "<li>追加のデータ制約はありません。</li>"
    )
    return (
        '<section class="panel mt"><h3>日本在住者向け統合リスク文脈 {source}</h3>'
        "<p>{summary}</p>"
        '<div class="table-wrap mt">{level_table}</div>'
        '<div class="table-wrap mt">{item_table}</div>'
        '<h3 class="mt">統合理由</h3><ul class="compact-list">{reasons}</ul>'
        '<h3 class="mt">データ制約</h3><ul class="compact-list">{limitations}</ul>'
        "<p>{caveat}</p>"
        "</section>"
    ).format(
        source=source_chip("日本在住者向け統合リスク文脈"),
        summary=esc(SECTION_EXPLANATIONS["japan_resident_integrated_risk_context"]),
        level_table=small_table(["項目", "状態"], [[esc(row[0]), esc(row[1])] for row in level_rows]),
        item_table=small_table(["分類", "補助判定", "要約", "取得元"], item_rows),
        reasons=reason_items,
        limitations=limitation_items,
        caveat=esc(_localize_display_text(payload.get("caveat", "-"))),
    )


def _risk_context_ux_hub_html(report: dict[str, Any]) -> str:
    card = report.get("buy_decision_card") or {}
    experiment = report.get("decision_boundary_experiment") or {}
    experiment_baseline = experiment.get("baseline") or {}
    experiment_payload = experiment.get("experimental") or {}
    experiment_diff = experiment.get("diff") or {}
    risk_lines = report.get("risk_lines") or {}
    integrated = report.get("japan_resident_integrated_risk_context") or {}
    domestic = report.get("domestic_danger_context") or {}
    availability = report.get("data_availability") or []
    limitations = integrated.get("data_limitations") or domestic.get("domestic_data_limitations") or []
    market_monitoring = [
        "株式市場: 米国主要指数、欧州株、日本株、新興国株",
        "債券・金利: 米10年、独10年、日10年、信用スプレッド",
        "為替市場: DXY、USD/JPY、EUR/JPY、主要通貨",
        "その他指標: VIX、クレジット、PMI、景気サプライズ指数",
    ]
    availability_counts: dict[str, int] = {}
    for row in availability:
        status = str(row.get("status") or "-")
        availability_counts[status] = availability_counts.get(status, 0) + 1
    availability_text = (
        ", ".join(f"{STATUS_LABELS.get(key, key)}={value}" for key, value in sorted(availability_counts.items())) or "取得状況データなし"
    )
    limitation_text = (
        " / ".join(_localize_display_text(item) for item in limitations[:3]) if limitations else "追加のデータ制約はありません。"
    )
    rows = [
        (
            "本体判断",
            f"最終判断: {_jp_action(str(card.get('final_action', '-')))} / 買い候補度: {card.get('buy_readiness_score', '-')}",
            "買い判断カードの結論です。補助文脈はここを上書きしません。",
        ),
        (
            "グローバル危険ライン",
            f"{risk_lines.get('stage_label', '-')} / 総合ストレス指数 {_display_number(risk_lines.get('composite_risk_score'))}",
            "米国・グローバル中心の危険監視です。国内文脈とは役割を分けます。",
        ),
    ]
    primary_alert = (report.get("alerts") or [{}])[0] or {}
    if primary_alert:
        rows.append(
            (
                "アラート",
                str(primary_alert.get("title") or "-"),
                str(primary_alert.get("message") or "現時点で高重要度の追加警告はありません。"),
            )
        )
    rows.extend(
        [
            (
                "データ制約・取得状況",
                f"{limitation_text} / {availability_text}",
                "不足系列や取得状態は、観測された危険と分けて読みます。",
            ),
            (
                "市場監視",
                " / ".join(market_monitoring[:4]),
                "主要市場、金利、為替、ストレス指標を横断して補助確認します。",
            ),
        ]
    )
    if experiment:
        rows.append(
            (
                "実験比較",
                (
                    "基準 {base} → 実験値 {exp} / 差分 {delta}".format(
                        base=experiment_baseline.get("buy_readiness_score", "-"),
                        exp=experiment_payload.get("adjusted_buy_readiness_score", "-"),
                        delta=(
                            f"調整前 {experiment_diff.get('raw_score_delta', experiment_diff.get('score_delta', 0))}"
                            f" / 上限適用後 {experiment_diff.get('clamped_score_delta', experiment_diff.get('score_delta', 0))}"
                        ),
                    )
                ),
                "本番既定値は変更せず、統合文脈を使う場合の境界だけ比較します。",
            )
        )
    cards = "".join(
        "<article class='risk-context-card'>"
        f"<div class='risk-context-type'>{html.escape(title)}</div>"
        f"<strong>{html.escape(value)}</strong>"
        f"<p>{html.escape(note)}</p>"
        "</article>"
        for title, value, note in rows
    )
    return (
        "<section class='risk-context-hub'>"
        "<div class='risk-context-head'>"
        "<h2>判断とリスク文脈の読み分け</h2>"
        "<p>本体判断、危険ライン、データ制約、取得状況を分けて確認します。</p>"
        "</div>"
        f"<div class='risk-context-grid'>{cards}</div>"
        "</section>"
    )


def _short_list_html(items: Iterable[Any], fallback: str, *, limit: int = 4) -> str:
    rows = [_localize_display_text(item) for item in list(items)[:limit] if str(item)]
    rows = rows or [fallback]
    return "".join(f"<li>{html.escape(row)}</li>" for row in rows)


def _availability_summary(report: dict[str, Any]) -> tuple[str, str]:
    availability = report.get("data_availability") or []
    counts: dict[str, int] = {}
    for entry in availability:
        status = str(entry.get("status") or "-")
        counts[status] = counts.get(status, 0) + 1
    if not counts:
        return "取得状況データなし", "データ制約"
    ok_count = counts.get("ok", 0)
    missing_count = sum(value for key, value in counts.items() if key != "ok")
    if missing_count:
        return f"一部未取得あり / ok={ok_count} / 未取得・代替={missing_count}", "一部未取得あり"
    return f"取得成功 ok={ok_count}", "取得成功"


def _data_limitation_items(report: dict[str, Any]) -> list[str]:
    integrated = report.get("japan_resident_integrated_risk_context") or {}
    domestic = report.get("domestic_danger_context") or {}
    hindenburg = report.get("hindenburg_omen_context") or {}
    items: list[str] = []
    items.extend(_localize_display_text(item) for item in integrated.get("data_limitations", [])[:3])
    items.extend(_localize_display_text(item) for item in domestic.get("domestic_data_limitations", [])[:3])
    items.extend(str(item) for item in hindenburg.get("limitations", [])[:2])
    unique: list[str] = []
    for item in items:
        if item and item not in unique:
            unique.append(item)
    return unique


def _status_tone_class(value: Any) -> str:
    text = str(value or "").lower()
    if any(token in text for token in ("danger", "extreme", "block", "警戒", "危険", "注意")):
        return "notice"
    if any(token in text for token in ("unavailable", "missing", "manual", "未取得", "データ不足")):
        return "muted"
    if any(token in text for token in ("ok", "normal", "pass", "通常", "中立", "取得成功")):
        return "ok"
    return "watch"


def _supplemental_signal_strip_html(report: dict[str, Any]) -> str:
    risk_lines = report.get("risk_lines") or {}
    domestic = report.get("domestic_danger_context") or {}
    _, availability_chip = _availability_summary(report)
    gold_value, gold_kind = _gold_signal_strip_status(report)
    signal_items = [
        ("VIX", risk_lines.get("stage_label", "-"), "補助確認"),
        ("米10年", "確認中", "補助確認"),
        ("DXY", "確認中", "補助確認"),
        ("HYG", "信用環境", "補助確認"),
        ("金", gold_value, gold_kind),
        ("原油", "確認中", "補助確認"),
        ("TOPIX", _domestic_danger_level_label(domestic.get("domestic_asset_level")), "国内文脈"),
        ("未取得", availability_chip, "データ制約"),
    ]
    signal_strip = "".join(
        "<article class='signal-pill {tone}'>"
        "<div class='signal-icon' aria-hidden='true'>{icon}</div>"
        f"<span>{html.escape(name)}</span>"
        f"<strong>{html.escape(str(value))}</strong>"
        f"<small>{html.escape(kind)}</small>"
        "</article>".format(
            tone=_status_tone_class(value),
            icon=html.escape({"VIX": "⌁", "米10年": "▰", "DXY": "$", "HYG": "▥", "金": "▣", "原油": "◌", "TOPIX": "↗"}.get(name, "☁")),
        )
        for name, value, kind in signal_items
    )
    return (
        '<section class="supplemental-signal-strip" aria-label="補助確認">'
        '<div class="section-title-row"><h2>補助確認</h2><span class="section-chip">リスク文脈 / 単独判断には不使用</span></div>'
        f'<div class="signal-strip-grid">{signal_strip}</div>'
        "</section>"
    )


def _gold_signal_strip_status(report: dict[str, Any]) -> tuple[str, str]:
    row = _find_monitor_row(report.get("inflation_monitor") or [], {"GC=F", "GLD", "IAU"})
    if not row:
        return "未取得", "候補未接続"
    signal = str(row.get("signal_label") or "中立")
    if signal == "安全資産選好":
        return "安全資産選好", "レジーム警戒に使用"
    return signal if signal != "中立" else "中立", "レジーム補助"


def _find_monitor_row(rows: Iterable[dict[str, Any]], tickers: set[str]) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get("ticker") or "") in tickers:
            return row
    return None


def _approved_report_dashboard_html(report: dict[str, Any]) -> str:
    card = report.get("buy_decision_card") or {}
    spot_signal = report.get("spot_signal", {}) or {}
    action_decision = spot_signal.get("action_decision", {}) or {}
    risk_lines = report.get("risk_lines") or {}
    integrated = report.get("japan_resident_integrated_risk_context") or {}
    domestic = report.get("domestic_danger_context") or {}
    hindenburg = report.get("hindenburg_omen_context") or {}
    candidate = report.get("investment_candidates") or {}
    recovery = report.get("recovery_candidates") or {}
    regime_leading = report.get("regime_leading_candidates") or {}

    final_action = _jp_action(str(card.get("final_action", action_decision.get("action", spot_signal.get("action", "-")))))
    readiness_score = _safe_int(card.get("buy_readiness_score", 0))
    buy_timing, buy_timing_note = _beginner_buy_timing_copy(str(card.get("final_action", action_decision.get("action", "-"))), card)
    next_conditions = [
        str(row.get("condition") or row.get("target_state") or "-") for row in (card.get("unlock_conditions") or [])[:3] if row
    ]
    positives: list[str] = []
    recovery_evidence = spot_signal.get("recovery_evidence") or {}
    if recovery_evidence.get("summary"):
        positives.append(str(recovery_evidence.get("summary")))
    positives.extend(str(reason) for reason in candidate.get("rationale", [])[:2])
    positives = positives or ["過度な恐怖は未確認", "一部セクターで底堅さ"]
    negatives = [_beginner_blocker_label(card.get("primary_blocker"))]
    negatives.extend(_beginner_blocker_label(item) for item in card.get("secondary_blockers", [])[:3])
    negatives.extend(str(reason) for reason in risk_lines.get("reasons", [])[:2])
    hindenburg_label = _hindenburg_signal_label(hindenburg.get("current_signal")) if hindenburg else "未取得"
    hindenburg_summary = _hindenburg_summary_text(hindenburg) if hindenburg else "市場幅CSVが未設定のため判定できません。"
    hindenburg_lamp_class = "active" if hindenburg.get("is_currently_active") else "unavailable" if not hindenburg else "normal"
    integrated_summary = (
        "統合: {combined} / 国内: {domestic} / 為替: {fx} / 国内金利: {rate}".format(
            combined=_domestic_danger_level_label(integrated.get("combined_context_level")),
            domestic=_domestic_danger_level_label(integrated.get("domestic_risk_level")),
            fx=_domestic_danger_level_label(integrated.get("fx_risk_level")),
            rate=_domestic_danger_level_label(integrated.get("rate_risk_level")),
        )
        if integrated
        else "統合文脈なし"
    )
    domestic_summary = (
        f"国内資産: {_domestic_danger_level_label(domestic.get('domestic_asset_level'))} / "
        f"為替: {_domestic_danger_level_label(domestic.get('domestic_fx_level'))} / "
        f"国内金利: {_domestic_danger_level_label(domestic.get('domestic_macro_level'))}"
        if domestic
        else "国内文脈なし"
    )

    main_candidate_chips = _candidate_chip_html(candidate.get("candidate_tickers", [])[:4])
    recovery_candidate_chips = _candidate_chip_html(recovery.get("candidate_tickers", [])[:4], tone="gold")
    regime_leading_candidate_chips = _candidate_chip_html(regime_leading.get("candidate_tickers", [])[:4], tone="violet")
    main_domestic_chips = _candidate_chip_html(
        _domestic_candidate_rows_for_top(report, "main"), tone="domestic", compact_metric=True, fallback=False
    )
    recovery_domestic_chips = _candidate_chip_html(
        _domestic_candidate_rows_for_top(report, "recovery"), tone="domestic", compact_metric=True, fallback=False
    )
    regime_domestic_chips = _candidate_chip_html(
        _domestic_candidate_rows_for_top(report, "regime"), tone="domestic", compact_metric=True, fallback=False
    )
    return f"""
      <section class="approved-report-dashboard main-dashboard-shell" aria-label="本体判断と補助確認の要約">
        <div class="main-report-left">
          <section class="glance-summary visual-first-read main-decision-section" aria-label="本体判断">
            <div class="section-title-row">
              <div>
                <span class="section-eyebrow">本体判断</span>
                <h2>まず見る：今日の判断</h2>
              </div>
              <span class="section-chip">上から順に読む</span>
            </div>
            <ol class="reading-guide" aria-label="この画面の読み方">
              <li><b>1</b><span><strong>結論</strong><small>いま動く場面か</small></span></li>
              <li><b>2</b><span><strong>理由</strong><small>良い材料と注意材料</small></span></li>
              <li><b>3</b><span><strong>次の確認</strong><small>何が変われば再検討か</small></span></li>
            </ol>
            <div class="decision-summary-grid">
              <article class="decision-hero-card decision-hero">
                <div class="decision-hero-icon">⌕</div>
                <div>
                  <strong>{html.escape(final_action)}</strong>
                  <div class="decision-hero-label">いまの結論</div>
                  <p>{html.escape(buy_timing_note)}</p>
                </div>
              </article>
              <article class="readiness-summary-card readiness-card">
                <div class="score-row"><span>買い候補度 <em>?</em></span><strong>{readiness_score}<small>/ 100</small></strong></div>
                <div class="readiness-bars" style="--score:{readiness_score}" aria-label="買い候補度 {readiness_score} / 100"></div>
                <div class="readiness-scale"><span>0</span><span>25</span><span>50</span><span>75</span><span>100</span></div>
                <div class="readiness-state">{html.escape(buy_timing)}</div>
                <p>これは成功確率ではありません</p>
              </article>
            </div>
            <div class="main-reason-grid">
              <article class="first-read-card next-check-card">
                <span class="term-note">次の確認条件</span>
                <h3><b>1</b> 次に確認すること</h3>
                <ul>{_short_list_html(next_conditions, "VIX、金利、主要指数の落ち着きを確認します", limit=3)}</ul>
                <small>監視判断であり、売買を指示するものではありません</small>
              </article>
              <article class="first-read-card positive">
                <span class="term-note">主なプラス要因</span>
                <h3><b>2</b> 良い材料</h3>
                <ul>{_short_list_html(positives, "プラス要因は限定的です", limit=4)}</ul>
              </article>
              <article class="first-read-card negative">
                <span class="term-note">主なマイナス要因</span>
                <h3><b>3</b> 注意したい材料</h3>
                <ul>{_short_list_html(negatives, "大きなマイナス要因は限定的です", limit=4)}</ul>
              </article>
            </div>
          </section>
          <div class="lower-summary-row">
            <section class="first-read-card candidate-summary-card">
              <span class="term-note">候補一覧</span>
              <h3>候補は「買う銘柄」ではなく、次に観察する対象</h3>
              <div class="candidate-follow-grid">
                <div class="candidate-mini-block">
                  <strong>主要候補</strong>
                  <span>積極判断よりも待機優先です</span>
                  <div class="candidate-chip-row compact">{main_candidate_chips}</div>
                  <div class="candidate-chip-row compact domestic">{main_domestic_chips}</div>
                </div>
                <div class="candidate-mini-block">
                  <strong>先回り候補</strong>
                  <span>反転初期を拾う候補</span>
                  <div class="candidate-chip-row compact">{recovery_candidate_chips}</div>
                  <div class="candidate-chip-row compact domestic">{recovery_domestic_chips}</div>
                </div>
                <div class="candidate-mini-block">
                  <strong>レジーム先回り</strong>
                  <span>次の地合いで効きやすい候補</span>
                  <div class="candidate-chip-row compact">{regime_leading_candidate_chips}</div>
                  <div class="candidate-chip-row compact domestic">{regime_domestic_chips}</div>
                </div>
              </div>
            </section>
          </div>
        </div>
        <aside class="main-report-context-stack context-stack" aria-label="補助文脈">
          <section class="context-card global">
            <span class="context-eyebrow">補助確認 1</span>
            <h2>グローバルリスク</h2>
            <div class="context-row"><strong>{html.escape(str(risk_lines.get("stage_label", "-")))}</strong><span>{html.escape(str(risk_lines.get("summary") or "米国・グローバル中心の危険監視です。"))}</span></div>
          </section>
          <section class="context-card resident">
            <span class="context-eyebrow">補助確認 2</span>
            <h2>日本在住者向け文脈</h2>
            <div class="context-row"><strong>為替・物価・金利</strong><span>{html.escape(integrated_summary)}</span></div>
            <div class="context-row"><strong>国内補助</strong><span>{html.escape(domestic_summary)}</span></div>
          </section>
          <section class="context-card hindenburg-lamp hindenburg-lamp-card {hindenburg_lamp_class}">
            <div class="lamp-row"><span></span><span></span><span></span><strong>{html.escape(hindenburg_label)}</strong></div>
            <h2>ヒンデンブルグオーメン: {html.escape(hindenburg_label)} <small>（表示専用）</small><span class="manual-link-wrap">{_hindenburg_manual_link_html()}</span></h2>
            <p>{html.escape(hindenburg_summary)} 単独では売買判断に使いません。</p>
          </section>
          <a class="supplement-link-card" href="supplement_dashboard.html">
            <strong>▣ 詳細は補足レポートで確認</strong>
            <span>補助確認・検証用の詳細を開く（別タブ） ↗</span>
          </a>
        </aside>
      </section>
    """


def _first_read_summary_items(report: dict[str, Any]) -> list[tuple[str, str]]:
    spot_signal = report.get("spot_signal", {}) or {}
    action_decision = spot_signal.get("action_decision", {}) or {}
    risk_lines = report.get("risk_lines", {}) or {}
    reliability = report.get("data_reliability", {}) or {}
    threshold_usage = report.get("threshold_usage", {}) or {}
    proposed_mode = "診断のみ"
    if (report.get("threshold_rule_certification") or {}).get("summary"):
        proposed_mode = "診断のみ（ルール単位で検証中）"
    reason = ", ".join(action_decision.get("policy_reasons", [])[:2]) or reliability.get("cap_reason") or spot_signal.get("reason") or "-"
    action_layers = spot_signal.get("action_layers") or {}
    diagnostics = report.get("buy_window_diagnostics") or {}
    fx_policy_diagnostics = report.get("fx_policy_diagnostics") or {}
    hindenburg = report.get("hindenburg_omen_context") or {}
    zero_reasons = diagnostics.get("buy_window_zero_reason_summary") or []
    return [
        ("市場だけ見た判定", _jp_action(str(action_layers.get("market_raw_action", action_decision.get("market_raw_action", "-"))))),
        ("リスク調整後", _jp_action(str(action_layers.get("risk_adjusted_action", action_decision.get("risk_adjusted_action", "-"))))),
        ("最終判断", _jp_action(str(action_decision.get("action", spot_signal.get("action", "-"))))),
        ("調整前/最終の買い検討ゾーン", f"{diagnostics.get('raw_buy_window_count', 0)} / {diagnostics.get('final_buy_window_count', 0)}"),
        ("調整前/最終の買い場候補", f"{diagnostics.get('raw_buy_candidate_count', 0)} / {diagnostics.get('final_buy_candidate_count', 0)}"),
        (
            "調整前の買い検討ゾーンからの降格",
            str(
                int(diagnostics.get("raw_buy_window_to_watch_count", 0) or 0) + int(diagnostics.get("raw_buy_window_to_wait_count", 0) or 0)
            ),
        ),
        (
            "買い場候補",
            (
                "あり"
                if action_layers.get("market_raw_action") == "buy_candidate" or action_layers.get("risk_adjusted_action") == "buy_candidate"
                else "なし"
            ),
        ),
        ("買い検討ゾーンが出ない主因", _localize_display_text(zero_reasons[0]) if zero_reasons else "-"),
        (
            "FX soft-cap診断",
            f"{_jp_action(str(fx_policy_diagnostics.get('current_final_action', '-')))} → {_jp_action(str(fx_policy_diagnostics.get('fx_soft_cap_action', '-')))} / 診断専用",
        ),
        ("判断理由", _localize_display_text(reason)),
        ("市場レジーム", _jp_regime(str((report.get("regime") or {}).get("regime_label", "-")))),
        ("危険ライン", _localize_display_text(risk_lines.get("stage_key", "-"))),
        ("ヒンデンブルグオーメン", _hindenburg_signal_label(hindenburg.get("current_signal")) if hindenburg else "未取得"),
        ("実運用しきい値", _localize_display_text(threshold_usage.get("final_action_threshold_set", "active"))),
        ("提案中しきい値 / 候補版", proposed_mode),
        ("次に見る項目", "データ品質 / 危険ラインの発火経路 / セクター内部構造"),
    ]


def _first_read_summary_markdown_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## まず見る要約"]
    lines.extend(f"- {label}: {value}" for label, value in _first_read_summary_items(report))
    return lines


def _buy_decision_card_markdown_lines(report: dict[str, Any]) -> list[str]:
    card = report.get("buy_decision_card") or {}
    if not card:
        return []
    lines = [
        "## 買い判断カード",
        f"- 最終判断: {_jp_action(str(card.get('final_action', '-')))}",
        f"- 市場だけ見た判定: {_jp_action(str(card.get('market_raw_action', '-')))}",
        f"- リスク調整後: {_jp_action(str(card.get('risk_adjusted_action', '-')))}",
        f"- 買い候補度: {card.get('buy_readiness_score', 0)} / 100 ({_localize_display_text(card.get('readiness_level', '-'))})",
        "- 注記: 買い候補度は成功確率・期待リターン・投資成功率ではありません。条件の揃い具合を示す説明用スコアです。",
        f"- 主な阻害要因: {_localize_display_text(card.get('primary_blocker') or 'なし')}",
    ]
    for index, row in enumerate((card.get("unlock_conditions") or [])[:3], start=1):
        lines.append(
            f"- 次に見る条件 {index}: {_localize_display_text(row.get('condition'))} -> {_localize_display_text(row.get('target_state'))}"
        )
    if card.get("sample_only_note"):
        lines.append(f"- サンプル実行注意: {_localize_display_text(card.get('sample_only_note'))}")
    lines.append("- このカードは説明用であり、最終判断には影響しません。")
    return lines


def _decision_boundary_experiment_markdown_lines(report: dict[str, Any]) -> list[str]:
    payload = report.get("decision_boundary_experiment") or {}
    if not payload:
        return []
    baseline = payload.get("baseline") or {}
    experimental = payload.get("experimental") or {}
    diff = payload.get("diff") or {}
    return [
        "## 判断境界の実験比較",
        f"- 有効化: {_display_bool(payload.get('enabled', False))}",
        f"- 基準の最終判断: {_jp_action(str(baseline.get('final_action', '-')))}",
        f"- 基準の買い候補度: {baseline.get('buy_readiness_score', '-')}",
        f"- 実験後の買い候補度: {experimental.get('adjusted_buy_readiness_score', '-')}",
        f"- 補助警戒水準: {experimental.get('supplemental_warning_level', '-')}",
        f"- スコア差分: {diff.get('score_delta', 0)}",
        f"- 調整前スコア差分: {diff.get('raw_score_delta', diff.get('score_delta', 0))}",
        f"- 上限適用後スコア差分: {diff.get('clamped_score_delta', diff.get('score_delta', 0))}",
        f"- 上限理由: {diff.get('clamp_reason', '-')}",
        f"- 判断変更: {_display_bool(diff.get('action_changed', False))}",
        f"- 本番既定値への影響: {_display_bool(not bool(payload.get('must_not_affect_production_default', True)))}",
        f"- 提案調整: {experimental.get('suggested_adjustment', '-')}",
    ]


def _buy_window_diagnostics_markdown_lines(report: dict[str, Any]) -> list[str]:
    diagnostics = report.get("buy_window_diagnostics") or {}
    if not diagnostics or diagnostics.get("status") in {None, "not_available"}:
        return []
    blockers = diagnostics.get("blocker_counts") or {}
    top_blockers = sorted(blockers.items(), key=lambda item: int(item[1] or 0), reverse=True)[:3]
    lines = [
        "## 買い場判定の診断",
        f"- 調整前の買い検討ゾーン: {diagnostics.get('raw_buy_window_count', 0)}",
        f"- 買い場候補: {diagnostics.get('raw_buy_candidate_count', 0)}",
        f"- 最終判断の買い検討ゾーン: {diagnostics.get('final_buy_window_count', 0)}",
        f"- 最終判断の買い場候補: {diagnostics.get('final_buy_candidate_count', 0)}",
        f"- 調整前の買い検討ゾーンからの降格: {int(diagnostics.get('raw_buy_window_to_watch_count', 0) or 0) + int(diagnostics.get('raw_buy_window_to_wait_count', 0) or 0)}",
        f"- FXによる買い場降格: {(report.get('japan_fx_downgrade_diagnostics') or {}).get('raw_buy_window_downgraded_by_fx_count', 0)}件",
        f"- 買い場候補の惜しい未達: {(report.get('buy_candidate_near_miss') or {}).get('near_miss_count', 0)}件",
        f"- 主な不足条件: {(report.get('buy_candidate_near_miss') or {}).get('top_missing_condition', '-')}",
        "- FX方針診断: 現行方針は変更なし。候補方針は診断専用です。",
        f"- FXソフト上限診断: 現行={_jp_action(str((report.get('fx_policy_diagnostics') or {}).get('current_final_action', '-')))} / ソフト上限={_jp_action(str((report.get('fx_policy_diagnostics') or {}).get('fx_soft_cap_action', '-')))} / 最終判断への影響なし",
        "- FXソフト上限ウォッチリスト: 追跡={tracked} / レビュー可能={ready} / 待機={waiting} / 判断={decision} / 診断専用".format(
            tracked=(report.get("fx_soft_cap_watchlist") or {}).get("tracked_case_count", 0),
            ready=(report.get("fx_soft_cap_watchlist") or {}).get("ready_for_review_count", 0),
            waiting=(report.get("fx_soft_cap_watchlist") or {}).get("waiting_future_data_count", 0),
            decision=(report.get("fx_soft_cap_watchlist") or {}).get("adoption_decision", "hold"),
        ),
        "- FXソフト上限の過去再生: 週数={weeks} / 候補={candidates} / 判断={decision} / 診断専用".format(
            weeks=(report.get("fx_soft_cap_historical_replay") or {}).get("total_replay_weeks", 0),
            candidates=(report.get("fx_soft_cap_historical_replay") or {}).get("fx_soft_cap_buy_candidate_count", 0),
            decision=(report.get("fx_soft_cap_historical_replay") or {}).get("adoption_decision", "hold"),
        ),
        "- 条件付きFXソフト上限診断: 最良候補={best} / 判断={decision} / 最終判断への影響なし".format(
            best=(report.get("fx_conditional_soft_cap_replay") or {}).get("best_candidate", "-"),
            decision=(report.get("fx_conditional_soft_cap_replay") or {}).get("adoption_decision", "hold"),
        ),
        "- FXソフト上限ドローダウンガード診断: 最良候補={best} / 最悪DD={before}→{after} / 判断={decision} / 最終判断への影響なし".format(
            best=(report.get("fx_soft_cap_dd_guard_replay") or {}).get("best_guard", "-"),
            before=_format_percent((report.get("fx_soft_cap_dd_guard_replay") or {}).get("base_worst_dd_13w")),
            after=_format_percent((report.get("fx_soft_cap_dd_guard_replay") or {}).get("best_worst_dd_13w")),
            decision=(report.get("fx_soft_cap_dd_guard_replay") or {}).get("adoption_decision", "hold"),
        ),
        "- FXソフト上限バランスガード: 件数={count} / 良好候補の見逃し={missed} / 判断={decision} / 最終判断への影響なし".format(
            count=(report.get("fx_soft_cap_balanced_guard") or {}).get("buy_candidate_count", 0),
            missed=(report.get("fx_soft_cap_balanced_guard") or {}).get("missed_good_count", 0),
            decision=(report.get("fx_soft_cap_balanced_guard") or {}).get("adoption_decision", "hold"),
        ),
        "- FXソフト上限の長期診断: 最良候補={best} / 週数={weeks} / 判断={decision} / 最終判断への影響なし".format(
            best=(report.get("fx_soft_cap_long_range_guard_replay") or {}).get("best_candidate", "-"),
            weeks=(report.get("fx_soft_cap_long_range_guard_replay") or {}).get("usable_weeks", 0),
            decision=(report.get("fx_soft_cap_long_range_guard_replay") or {}).get("adoption_decision", "hold"),
        ),
        "- レジーム考慮FX診断: 最良候補={best} / 週数={weeks} / 判断={decision} / 最終判断への影響なし".format(
            best=(report.get("regime_aware_fx_policy_replay") or {}).get("best_candidate", "-"),
            weeks=(report.get("regime_aware_fx_policy_replay") or {}).get("usable_weeks", 0),
            decision=(report.get("regime_aware_fx_policy_replay") or {}).get("adoption_decision", "hold"),
        ),
        "- 主な阻害要因:",
    ]
    if top_blockers:
        lines.extend(f"  - {key}: {value}" for key, value in top_blockers)
    else:
        lines.append("  - -")
    return lines


def _format_percent(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return str(value)


def _safe_int(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def _beginner_buy_timing_copy(action: str, card: dict[str, Any]) -> tuple[str, str]:
    normalized = action.lower()
    score = _safe_int(card.get("buy_readiness_score", 0))
    if normalized in {"buy_window", "buy_candidate"}:
        return "材料待ち", "追加確認を優先します"
    if normalized in {"watch", "monitor"}:
        return ("材料待ち", "あと少し条件を確認します") if score >= 65 else ("まだ早い", "決め手が不足しています")
    return "見送り", "今は慎重に確認します"


def _beginner_market_state_copy(report: dict[str, Any]) -> tuple[str, str]:
    risk_lines = report.get("risk_lines", {}) or {}
    regime = report.get("regime", {}) or {}
    stage_key = str(risk_lines.get("stage_key", "normal"))
    if stage_key in {"extreme_danger_line_reached", "danger_line_reached"}:
        return "警戒", "市場ストレスが高い状態です"
    if stage_key in {"credit_spillover_initial", "caution"}:
        return "注意", "不安が残っています"
    regime_label = _jp_regime(str(regime.get("regime_label", "-")))
    if regime_label in {"リスクオン", "初期回復"}:
        return "通常〜回復途中", "徐々に落ち着いています"
    if regime_label == "移行局面":
        return "移行局面", "方向を確認する段階です"
    return regime_label, "落ち着き具合を確認します"


def _beginner_blocker_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "大きな見送り理由は限定的"
    mapping = {
        "inflation_shock": "インフレショックの影響が残る",
        "fx_risk": "為替リスクの影響が残る",
        "rate_shock": "金利ショックの影響が残る",
        "sample_only": "確認用データが含まれる",
        "sample_fallback_present": "確認用データが含まれる",
        "risk_line": "危険ラインを確認中",
        "market_stress": "市場ストレスが残る",
        "insufficient_recovery": "回復の決め手が不足",
        "low_score": "決め手不足",
    }
    return mapping.get(text, _localize_decision_reason(text.replace("_", " ")))


def _beginner_reason_items(report: dict[str, Any], card: dict[str, Any]) -> list[str]:
    items = [_beginner_blocker_label(card.get("primary_blocker"))]
    risk_lines = report.get("risk_lines", {}) or {}
    risk_stage = str(risk_lines.get("stage_label") or "")
    if risk_stage:
        items.append("危険ライン前" if _risk_stage_tone(risk_lines.get("stage_key")) == "normal" else risk_stage)
    action_note = _beginner_buy_timing_copy(str(card.get("final_action", "")), card)[1]
    items.append(action_note)
    unique: list[str] = []
    for item in items:
        if item and item not in unique:
            unique.append(item)
    return unique[:3] or ["決め手不足"]


def _beginner_next_items(candidate: dict[str, Any], risk_lines: dict[str, Any]) -> list[str]:
    items = [str(item.get("ticker", "-")) for item in candidate.get("candidate_tickers", [])[:2] if item.get("ticker")]
    if not items:
        preferred = candidate.get("preferred_asset_class") or {}
        if preferred.get("ticker"):
            items.append(str(preferred.get("ticker")))
    items.append("危険ライン")
    return items[:3]


def _beginner_candidate_items(candidate: dict[str, Any]) -> list[str]:
    items = [str(item.get("ticker", "-")) for item in candidate.get("candidate_tickers", [])[:2] if item.get("ticker")]
    return items or ["候補なし"]


def _candidate_chip_html(
    rows: Iterable[dict[str, Any]],
    *,
    tone: str = "",
    compact_metric: bool = False,
    fallback: bool = True,
) -> str:
    chips = []
    tone_class = f" {tone}" if tone else ""
    for row in rows:
        symbol = str(row.get("ticker") or row.get("symbol") or "-")
        metric = str(row.get("metric_text") or "")
        body = html.escape(symbol)
        if compact_metric and metric:
            body += f"<small>{html.escape(metric)}</small>"
        chips.append(f"<span class='candidate-chip{tone_class}'>{body}</span>")
    if chips:
        return "".join(chips)
    return "<span class='candidate-chip muted'>候補なし</span>" if fallback else ""


def _domestic_candidate_rows_for_top(report: dict[str, Any], bucket: str) -> list[dict[str, Any]]:
    candidates = (report.get("multi_asset_candidates") or {}).get("candidates") or []
    prepared = [_top_domestic_candidate_row(row) for row in candidates]
    rows = [row for row in prepared if row]
    fallback_by_class: dict[str, dict[str, Any]] = {}
    existing_classes = {existing["asset_class"] for existing in rows}
    for row in _domestic_metric_fallback_rows_for_top(report):
        asset_class = str(row["asset_class"])
        if asset_class not in existing_classes and asset_class not in fallback_by_class:
            fallback_by_class[asset_class] = row
    rows.extend(fallback_by_class.values())
    if bucket == "main":
        order = {"jp_equity": 0, "bond_jpy": 1, "reit_jp": 2}
        return sorted(rows, key=lambda row: order.get(str(row.get("asset_class")), 99))[:3]
    if bucket == "recovery":
        return _top_recovery_domestic_rows(rows)
    if bucket == "regime":
        return _top_regime_domestic_rows(rows, str((report.get("regime") or {}).get("regime_label") or ""))
    return []


def _top_domestic_candidate_row(row: dict[str, Any]) -> dict[str, Any] | None:
    asset_class = str(row.get("asset_class") or "")
    if asset_class not in {"jp_equity", "bond_jpy", "reit_jp"}:
        return None
    symbol = str(row.get("symbol") or "")
    if not symbol:
        return None
    metrics = row.get("metrics") or {}
    if not row.get("source_data_available") or _has_suspicious_metric_limitation(metrics.get("limitations")):
        return None
    metric_text = _compact_candidate_metric(metrics)
    if not metric_text:
        return None
    return {
        "asset_class": asset_class,
        "symbol": symbol,
        "metric_text": metric_text,
        "momentum_4w": _metric_percent_value(metrics, "change_4w"),
        "momentum_12w": _metric_percent_value(metrics, "momentum_12w", fallback_key="change_12w"),
        "max_drawdown": _metric_percent_value(metrics, "max_drawdown"),
    }


def _domestic_metric_fallback_rows_for_top(report: dict[str, Any]) -> list[dict[str, Any]]:
    group_to_class = {"jp_equity": "jp_equity", "jpy_bond": "bond_jpy", "jp_reit": "reit_jp"}
    preferred_order = {"jp_equity": 0, "jpy_bond": 1, "jp_reit": 2}
    metrics_by_symbol = (report.get("domestic_market_metrics") or {}).get("by_symbol") or {}
    rows: list[dict[str, Any]] = []
    for metric in metrics_by_symbol.values():
        asset_group = str(metric.get("asset_group") or "")
        asset_class = group_to_class.get(asset_group)
        if not asset_class:
            continue
        symbol = str(metric.get("symbol") or "")
        if not symbol or not metric.get("is_available") or _has_suspicious_metric_limitation(metric.get("limitations")):
            continue
        metric_text = _compact_candidate_metric(metric)
        if not metric_text:
            continue
        rows.append(
            {
                "asset_class": asset_class,
                "symbol": symbol,
                "metric_text": metric_text,
                "momentum_4w": _metric_percent_value(metric, "change_4w"),
                "momentum_12w": _metric_percent_value(metric, "momentum_12w", fallback_key="change_12w"),
                "max_drawdown": _metric_percent_value(metric, "max_drawdown"),
                "source_order": preferred_order.get(asset_group, 99),
            }
        )
    return sorted(rows, key=lambda row: (row.get("source_order", 99), row["symbol"]))


def _top_recovery_domestic_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for row in rows:
        mom_4w = row.get("momentum_4w")
        mom_12w = row.get("momentum_12w")
        drawdown = row.get("max_drawdown")
        if mom_4w is None or mom_12w is None or drawdown is None:
            continue
        is_rate_like = row.get("asset_class") == "bond_jpy"
        deep_drawdown = -8.0 if is_rate_like else -10.0
        collapse_floor = -30.0 if is_rate_like else -35.0
        if not (mom_4w > 0 and mom_12w <= 5.0 and drawdown <= deep_drawdown and drawdown >= collapse_floor):
            continue
        score = 0.0
        score += 1.2 if mom_4w >= 2.0 else 0.8
        score += 1.0 if mom_12w <= -5.0 else 0.6 if mom_12w <= 2.0 else 0.0
        score += 1.1 if drawdown <= (-12.0 if is_rate_like else -14.0) else 0.7
        if mom_4w - mom_12w >= 6.0:
            score += 0.9
        scored.append({**row, "score": score})
    return sorted(scored, key=lambda row: row["score"], reverse=True)[:3]


def _top_regime_domestic_rows(rows: list[dict[str, Any]], regime_label: str) -> list[dict[str, Any]]:
    theme = _domestic_regime_theme(regime_label)
    if not theme:
        return []
    scored: list[dict[str, Any]] = []
    for row in rows:
        asset_class = str(row.get("asset_class") or "")
        if asset_class not in theme:
            continue
        mom_4w = row.get("momentum_4w")
        mom_12w = row.get("momentum_12w")
        if mom_4w is None or mom_12w is None:
            continue
        score = float(theme[asset_class])
        if mom_4w >= 3.0:
            score += 0.95
        elif mom_4w > 0:
            score += 0.65
        elif mom_4w >= -1.0:
            score += 0.25
        else:
            score -= 0.25
        if mom_12w <= -6.0:
            score += 0.75
        elif mom_12w <= 4.0:
            score += 0.55
        elif mom_12w <= 12.0:
            score += 0.2
        else:
            score -= 0.25
        if mom_4w - mom_12w >= 5.0:
            score += 0.7
        elif mom_4w - mom_12w >= 2.0:
            score += 0.4
        if score >= 0.95:
            scored.append({**row, "score": score})
    return sorted(scored, key=lambda row: row["score"], reverse=True)[:3]


def _domestic_regime_theme(regime_label: str) -> dict[str, float]:
    return {
        "risk_off": {"bond_jpy": 1.0, "jp_equity": 0.75, "reit_jp": 0.2},
        "transition": {"jp_equity": 0.9, "reit_jp": 0.75, "bond_jpy": 0.65},
        "early_recovery": {"jp_equity": 0.65, "reit_jp": 0.85, "bond_jpy": 0.35},
        "inflation_shock": {"jp_equity": 0.45, "reit_jp": 0.2, "bond_jpy": 0.25},
    }.get(regime_label, {})


def _metric_percent_value(metrics: dict[str, Any], key: str, *, fallback_key: str | None = None) -> float | None:
    raw_value = metrics.get(key)
    if raw_value is None and fallback_key:
        raw_value = metrics.get(fallback_key)
    if raw_value is None:
        return None
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value):
        return None
    if key in {"momentum_12w", "max_drawdown"} and abs(value) <= 1.0:
        return value * 100.0
    return value


def _compact_candidate_metric(metrics: dict[str, Any]) -> str:
    for key, label in (("change_4w", "4週"), ("momentum_12w", "12週"), ("change_12w", "12週")):
        value = metrics.get(key)
        if value is not None:
            return f"{label} {_display_compact_number(value, 1)}%"
    trend = metrics.get("trend_label")
    if trend:
        return _localize_display_text(trend)
    return ""


def _beginner_risk_level(risk_lines: dict[str, Any]) -> tuple[str, str]:
    tone = _risk_stage_tone(risk_lines.get("stage_key"))
    if tone in {"danger", "extreme"}:
        return "高い", "危険ラインを優先して確認します"
    if tone == "caution":
        return "注意", "現在の危険は限定的ではありません"
    return "低い", "現在の危険は限定的です"


def _beginner_one_line(final_action: str, buy_timing: str) -> str:
    if buy_timing == "まだ早い":
        return "今は急がず、材料がそろうまで様子を見る局面です。"
    if buy_timing == "材料待ち":
        return "候補に近い材料はありますが、次の確認を待つ局面です。"
    if final_action == "待機":
        return "無理に動かず、市場の落ち着きを確認する局面です。"
    return "まず状態を確認し、複数の材料がそろうまで慎重に見ます。"


def _beginner_next_action(buy_timing: str) -> str:
    if buy_timing == "まだ早い":
        return "焦って買わず、次の確認を待つ"
    if buy_timing == "材料待ち":
        return "材料がそろうか確認する"
    return "無理に動かず確認を続ける"


def _first_read_summary_html(report: dict[str, Any]) -> str:
    spot_signal = report.get("spot_signal", {}) or {}
    action_decision = spot_signal.get("action_decision", {}) or {}
    card = report.get("buy_decision_card") or {}
    risk_lines = report.get("risk_lines", {}) or {}
    candidate = report.get("investment_candidates", {}) or {}

    final_action = _jp_action(str(card.get("final_action", action_decision.get("action", spot_signal.get("action", "-")))))
    buy_timing, buy_timing_note = _beginner_buy_timing_copy(str(card.get("final_action", action_decision.get("action", "-"))), card)
    market_state, market_state_note = _beginner_market_state_copy(report)
    reason_items = _beginner_reason_items(report, card)
    next_items = _beginner_next_items(candidate, risk_lines)
    beginner_note = _beginner_one_line(final_action, buy_timing)

    reason_html = "".join(f"<li>{html.escape(item)}</li>" for item in reason_items)
    next_html = "".join(f"<span>{html.escape(item)}</span>" for item in next_items)
    return f"""
      <section class=\"glance-summary\" aria-label=\"まず見るポイント\">
        <div class=\"glance-heading\">
          <h2>まず見るポイント</h2>
          <p>3秒で今の状況を把握できます</p>
        </div>
        <div class=\"glance-grid\">
          <article class=\"glance-tile tone-watch\">
            <div class=\"tile-label\">今の判断</div>
            <div class=\"tile-icon\">▣</div>
            <div class=\"tile-main\">{html.escape(final_action)}</div>
            <div class=\"tile-sub\">今は様子見の局面です</div>
          </article>
          <article class=\"glance-tile tone-wait\">
            <div class=\"tile-label\">買い場か？</div>
            <div class=\"tile-icon\">○</div>
            <div class=\"tile-main\">{html.escape(buy_timing)}</div>
            <div class=\"tile-sub\">{html.escape(buy_timing_note)}</div>
          </article>
          <article class=\"glance-tile tone-normal\">
            <div class=\"tile-label\">市場の状態</div>
            <div class=\"tile-icon\">↗</div>
            <div class=\"tile-main\">{html.escape(market_state)}</div>
            <div class=\"tile-sub\">{html.escape(market_state_note)}</div>
          </article>
          <article class=\"glance-tile tone-reason\">
            <div class=\"tile-label\">主な理由</div>
            <ul>{reason_html}</ul>
          </article>
          <article class=\"glance-tile tone-next\">
            <div class=\"tile-label\">次に見るもの</div>
            <div class=\"chip-row\">{next_html}</div>
          </article>
          <article class=\"glance-tile tone-beginner\">
            <div class=\"tile-label\">初心者向けひとこと</div>
            <div class=\"tile-sub\">{html.escape(beginner_note)}</div>
          </article>
        </div>
      </section>
    """


def _buy_decision_card_html(report: dict[str, Any]) -> str:
    card = report.get("buy_decision_card") or {}
    if not card:
        return ""
    candidate = report.get("investment_candidates", {}) or {}
    risk_lines = report.get("risk_lines", {}) or {}
    final_action = _jp_action(str(card.get("final_action", "-")))
    blocker = _beginner_blocker_label(card.get("primary_blocker"))
    risk_label, risk_note = _beginner_risk_level(risk_lines)
    candidate_items = _beginner_candidate_items(candidate)
    candidate_html = "".join(f"<span>{html.escape(item)}</span>" for item in candidate_items)
    readiness_score = _safe_int(card.get("buy_readiness_score", 0))
    buy_timing, buy_timing_note = _beginner_buy_timing_copy(str(card.get("final_action", "-")), card)
    return f"""
      <section class=\"buy-decision-flow\" aria-label=\"買い判断カード\">
        <div class=\"buy-flow-heading\">
          <div>
            <h2>買い判断カード</h2>
            <p>初心者向け: 今どう見るかを順番に整理します</p>
          </div>
          <span class=\"beginner-badge\">初心者向け</span>
        </div>
        <div class=\"buy-flow-layout\">
          <div class=\"buy-steps\">
            <article class=\"buy-step\">
              <div class=\"step-number\">1</div>
              <h3>現在の判断</h3>
              <div class=\"step-icon\">▣</div>
              <strong>{html.escape(final_action)}</strong>
              <p>今は様子見です</p>
            </article>
            <article class=\"buy-step\">
              <div class=\"step-number\">2</div>
              <h3>理由</h3>
              <div class=\"step-icon\">%</div>
              <strong>{html.escape(blocker)}</strong>
              <p>市場に不安が残っています</p>
            </article>
            <article class=\"buy-step\">
              <div class=\"step-number\">3</div>
              <h3>危険度</h3>
              <div class=\"step-icon\">◒</div>
              <strong>{html.escape(risk_label)}</strong>
              <p>{html.escape(risk_note)}</p>
            </article>
            <article class=\"buy-step\">
              <div class=\"step-number\">4</div>
              <h3>買い候補</h3>
              <div class=\"chip-row\">{candidate_html}</div>
            </article>
            <article class=\"buy-step\">
              <div class=\"step-number\">5</div>
              <h3>今すること</h3>
              <div class=\"step-icon\">✓</div>
              <strong>{html.escape(_beginner_next_action(buy_timing))}</strong>
              <p>{html.escape(buy_timing_note)}</p>
            </article>
          </div>
          <aside class=\"readiness-panel\" aria-label=\"買い候補度\">
            <div class=\"score-label\">買い候補度</div>
            <div class=\"score-gauge readiness-gauge\" style=\"--score:{readiness_score}\" aria-label=\"買い候補度 {readiness_score} / 100\">
              <div class=\"score-number\">{readiness_score}</div>
              <div class=\"score-total\">/ 100</div>
            </div>
            <p class=\"score-note\">これは成功確率ではありません</p>
            <p class=\"score-subnote\">複数の確認がそろうまで慎重に見ます</p>
          </aside>
        </div>
      </section>
    """


def _threshold_usage_markdown_lines(report: dict[str, Any]) -> list[str]:
    usage = report.get("threshold_usage") or {}
    rule_certification = report.get("threshold_rule_certification") or {}
    affects_final_action = usage.get("affects_final_action", usage.get("currently_affects_final_action", "-"))
    rule_impact = rule_certification.get("currently_affects_final_action", False)
    return [
        "## しきい値利用方針",
        f"- 実運用しきい値: {_localize_display_text(usage.get('operational_set', '-'))}",
        f"- 提案中しきい値: {_localize_display_text(usage.get('proposed_status', '-'))}",
        f"- 候補版v2: {_localize_display_text(usage.get('candidate_v2_status', '-'))}",
        f"- ルール認証の影響: {'一部あり' if rule_impact else 'なし'}",
        "- 最終判断の根拠: 実運用しきい値 + データ信頼性方針",
        f"- 提案中しきい値 / 候補版v2 の最終判断への影響: {_localize_display_text(affects_final_action)}",
        "",
        "補足: 提案中しきい値 / 候補版v2 / ルール認証は診断・将来採用候補であり、v0.7.0 の最終判断には直接影響しません。",
    ]


def _threshold_usage_html(report: dict[str, Any]) -> str:
    usage = report.get("threshold_usage") or {}
    rule_certification = report.get("threshold_rule_certification") or {}
    affects_final_action = usage.get("affects_final_action", usage.get("currently_affects_final_action", "-"))
    rule_impact = rule_certification.get("currently_affects_final_action", False)
    rows = [
        ("実運用しきい値", _localize_display_text(usage.get("operational_set", "-"))),
        ("提案中しきい値", _localize_display_text(usage.get("proposed_status", "-"))),
        ("候補版v2", _localize_display_text(usage.get("candidate_v2_status", "-"))),
        ("ルール認証の影響", "一部あり" if rule_impact else "なし"),
        ("最終判断の根拠", "実運用しきい値 + データ信頼性方針"),
        ("提案中しきい値 / 候補版v2 の最終判断への影響", _localize_display_text(affects_final_action)),
    ]
    items = "".join(f"<li><strong>{html.escape(str(label))}:</strong> {html.escape(str(value))}</li>" for label, value in rows)
    return f"""
    <section class="card">
      <h2>しきい値利用方針</h2>
      <ul>{items}</ul>
      <p>提案中しきい値 / 候補版v2 / ルール認証は診断・将来採用候補であり、v0.7.0 の最終判断には直接影響しません。</p>
    </section>
    """


def render_developer_diagnostics_markdown(report: dict[str, Any]) -> str:
    """Render developer-only diagnostics kept out of the regular report."""
    threshold_drift = report.get("risk_threshold_drift") or {}
    drift_summary = threshold_drift.get("summary") or {}
    threshold_review = report.get("risk_threshold_review") or {}
    threshold_maintenance = report.get("risk_threshold_maintenance") or {}
    risk_engine_replay = report.get("risk_engine_v2_replay") or {}
    reconstructed_replay = report.get("risk_engine_v2_reconstructed_replay") or {}
    holdout_validation = report.get("risk_engine_v2_holdout_validation") or {}
    lines = [
        f"# 開発診断: {report.get('title', 'Report')}",
        "",
        f"- 生成時刻: {report.get('generated_at', '-')}",
        "- 用途: 開発者向けのしきい値・診断情報です。通常の report.html / report.md には表示しません。",
        "- 最終判断への影響: なし",
        "",
        "## しきい値レビュー",
        f"- しきい値バージョン: {report.get('risk_thresholds', {}).get('version', '-')}",
        f"- しきい値校正日時: {report.get('risk_thresholds', {}).get('generated_at', '-')}",
        f"- しきい値ドリフト: 安定={drift_summary.get('stable_count', 0)} / 監視={drift_summary.get('watch_count', 0)} / 要確認={drift_summary.get('review_count', 0)} / 未取得={drift_summary.get('unavailable_count', 0)}",
        f"- しきい値ドリフトのレビュー対象: {', '.join(_jp_review_target(item) for item in drift_summary.get('review_targets', [])) or '-'}",
        f"- しきい値レビュー状態: {_jp_threshold_status(threshold_review.get('status', '-'))} / 推奨={_display_bool(threshold_review.get('review_recommended', False))}",
        f"- しきい値レビュー理由: {', '.join(threshold_review.get('reasons', [])) or '-'}",
        f"- しきい値メンテナンス状態: {_localize_display_text(threshold_maintenance.get('status', '-'))}",
        f"- しきい値メンテナンス所要時間: {_display_number(threshold_maintenance.get('elapsed_seconds'))} 秒",
        f"- しきい値提案生成: {_display_bool(threshold_maintenance.get('proposal_generated_this_run', False))}",
        "",
        *_threshold_usage_markdown_lines(report),
        "",
        *_threshold_rule_certification_markdown_lines(report),
        "",
        "## risk_engine_v2 保存履歴リプレイ",
        f"- status: {risk_engine_replay.get('status', '-')}",
        f"- policy_status: {risk_engine_replay.get('policy_status', '-')}",
        f"- total_cases: {risk_engine_replay.get('total_cases', 0)}",
        f"- strict_available_cases: {risk_engine_replay.get('strict_available_cases', 0)}",
        f"- outcome_status: {risk_engine_replay.get('outcome_status', '-')}",
        f"- outcome_usable_cases: {risk_engine_replay.get('outcome_usable_cases', 0)}",
        f"- promotion_allowed: {_display_bool(risk_engine_replay.get('promotion_allowed', False))}",
        f"- decision_reason: {risk_engine_replay.get('decision_reason', '-')}",
        "",
        "## risk_engine_v2 再構築リプレイ",
        f"- status: {reconstructed_replay.get('status', '-')}",
        f"- policy_status: {reconstructed_replay.get('policy_status', '-')}",
        f"- total_cases: {reconstructed_replay.get('total_cases', 0)}",
        f"- strict_available_cases: {reconstructed_replay.get('strict_available_cases', 0)}",
        f"- outcome_status: {reconstructed_replay.get('outcome_status', '-')}",
        f"- outcome_usable_cases: {reconstructed_replay.get('outcome_usable_cases', 0)}",
        f"- promotion_allowed: {_display_bool(reconstructed_replay.get('promotion_allowed', False))}",
        f"- decision_reason: {reconstructed_replay.get('decision_reason', '-')}",
        f"- reconstruction: {(reconstructed_replay.get('reconstruction') or {}).get('source', '-')}",
        f"- history_files_modified: {_display_bool((reconstructed_replay.get('reconstruction') or {}).get('history_files_modified', False))}",
        "",
        "## risk_engine_v2 holdout validation",
        f"- status: {holdout_validation.get('status', '-')}",
        f"- policy_status: {holdout_validation.get('policy_status', '-')}",
        f"- validation_level: {holdout_validation.get('validation_level', '-')}",
        f"- strict_primary_available: {_display_bool(holdout_validation.get('strict_primary_available', False))}",
        f"- holdout_status: {holdout_validation.get('holdout_status', '-')}",
        f"- split_status: {holdout_validation.get('split_status', '-')}",
        f"- evidence_status: {holdout_validation.get('evidence_status', '-')}",
        f"- performance_status: {holdout_validation.get('performance_status', '-')}",
        f"- cadence_status: {holdout_validation.get('cadence_status', '-')}",
        f"- holdout_episode_count: {holdout_validation.get('holdout_episode_count', 0)}",
        f"- holdout_case_count: {holdout_validation.get('holdout_case_count', 0)}",
        f"- holdout_reason: {holdout_validation.get('holdout_reason', '-')}",
        f"- split_policy: {(holdout_validation.get('split_policy') or {}).get('type', '-')}",
        f"- promotion_allowed: {_display_bool(holdout_validation.get('promotion_allowed', False))}",
        f"- decision_reason: {holdout_validation.get('decision_reason', '-')}",
        f"- promotion_gate_status: {holdout_validation.get('promotion_gate_status', '-')}",
        f"- promotion_gate_blockers: {holdout_validation.get('promotion_gate_blockers', [])}",
        "",
    ]
    return "\n".join(lines)


def render_markdown(report: dict[str, Any]) -> str:
    regime_label = _jp_regime(report["regime"]["regime_label"])
    cycle_label = _jp_cycle(report["cycle"]["phase_label"])
    action_label = _jp_action(report["spot_signal"].get("action_decision", {}).get("action", report["spot_signal"]["action"]))
    legacy_action_label = _jp_action(report["spot_signal"].get("legacy_action", report["spot_signal"].get("action", "")))
    risk_label = _jp_risk(report["spot_signal"]["second_leg_risk"])
    risk_lines = report.get("risk_lines", {})
    recovery_evidence = report.get("spot_signal", {}).get("recovery_evidence", {})
    blocker_assessment = report.get("spot_signal", {}).get("blocker_assessment", {})
    action_decision = report.get("spot_signal", {}).get("action_decision", {})
    recovery_grade = str(recovery_evidence.get("grade", "-"))
    blocker_level = str(blocker_assessment.get("level", "-"))
    decision_action = _jp_action(str(action_decision.get("action", report["spot_signal"].get("action", ""))))
    risk_stage_badge = _risk_badge_markdown(risk_lines.get("stage_label", "-"), _risk_stage_tone(risk_lines.get("stage_key")))
    internal_warning_count = len(report.get("warnings", []))
    sector_context = _build_sector_rotation_context(report.get("sector_rotation", {}))
    japan_risk = report.get("japan_risk", {})

    lines = [
        f"# {report['title']}",
        "",
        *_first_read_summary_markdown_lines(report),
        "",
        *_buy_decision_card_markdown_lines(report),
        *_decision_boundary_experiment_markdown_lines(report),
        *_buy_window_diagnostics_markdown_lines(report),
        "",
        "## サマリー",
        f"- 生成時刻: {report['generated_at']}",
        f"- データソース: {report['data_source']}",
        f"- 判定信頼性: {_jp_reliability(report.get('data_reliability', {}).get('level', 'high'))}",
        *_data_quality_markdown_lines(report),
        f"- 市場レジーム: {regime_label}",
        f"- サイクル判定: {cycle_label} ({_display_number(report['cycle'].get('phase_angle_deg'))} 度)",
        f"- 合成スコア: {_display_number(report['score'].get('total_score'))}",
        f"- 旧判定用スコア: {_display_number(report['spot_signal'].get('legacy_adjusted_score', report['spot_signal'].get('adjusted_score', report['score'].get('total_score'))))}",
        f"- 上昇再開の証拠: {recovery_grade} ({_display_compact_number(recovery_evidence.get('score'))})",
        f"- 騙し上昇の警戒: {blocker_level}",
        f"- 新判断: {decision_action}",
        f"- スポット投資判断: {action_label}",
        f"- 旧スポット投資判断: {legacy_action_label}",
        f"- 二段下げリスク: {risk_label}",
        f"- 円建て・為替リスク: {_jp_japan_risk_level(japan_risk.get('level'))} / {japan_risk.get('summary', '-')}",
        f"- 市場ストレス段階: {risk_stage_badge}",
        "## 解説",
        f"- 市場レジーム: {SECTION_EXPLANATIONS['regime']}",
        f"- サイクル判定: {SECTION_EXPLANATIONS['cycle']}",
        f"- 合成スコア: {SECTION_EXPLANATIONS['score']}",
        f"- スポット投資判断: {SECTION_EXPLANATIONS['spot']}",
        "",
    ]
    lines.extend(["## 判定理由", f"- {SECTION_EXPLANATIONS['decision_reasons']}"])
    lines.append(
        f"- 上昇再開の証拠: {_localize_display_text(recovery_grade)} / スコア {_display_compact_number(recovery_evidence.get('score'))}"
    )
    lines.append(
        f"- 騙し上昇の警戒: {_localize_display_text(blocker_level)} / {_localize_display_text(blocker_assessment.get('summary', '-'))}"
    )
    lines.append(f"- 最終判断: {decision_action} / 判定モード {_localize_display_text(action_decision.get('mode', '-'))}")
    for reason in report["spot_signal"].get("rationale", []):
        lines.append(f"- {_localize_display_text(reason)}")

    lines.extend(["", "## セクターローテーション", f"- {SECTION_EXPLANATIONS['sector']}"])
    for row in sector_context["rows"]:
        candidate_suffix = f" / ラベル {row['candidate_label']}" if row.get("candidate_label") else ""
        lines.append(
            f"- {row['ticker']} ({row['sector_name_ja']}): 12週騰落率 {row['return_12w']} / 順位 {row['rank']}位 / 位置 {row['rotation_phase_ja']}{candidate_suffix}"
        )

    sector_payload = report.get("sector_rotation", {})
    structure = sector_payload.get("internal_structure") or report.get("internal_structure", {})
    next_candidates = sector_payload.get("next_candidates") or report.get("next_candidates", [])
    peakout_sectors = sector_payload.get("peakout_sectors") or report.get("peakout_sectors", [])
    market_structure_comment = sector_payload.get("market_structure_comment") or report.get("market_structure_comment", "-")
    lines.extend(["", "## セクターローテーション内部構造"])
    lines.append(f"- 内部構造ラベル: {structure.get('structure_label', 'Noisy / Unclear')}")
    lines.append(f"- 市場内部構造コメント: {market_structure_comment}")
    lines.append(f"- セクター分散指標: {structure.get('dispersion_score', 0.0)}")
    if "watch_share" in structure or "promising_share" in structure:
        lines.append(
            f"- 相対広がり指標: watch_share={structure.get('watch_share', 0.0)} / promising_share={structure.get('promising_share', 0.0)}"
        )
        lines.append(f"- 相対広がり要約: {_share_summary_ja(structure)}")
    structure_dims = structure.get("structure", {})
    if structure_dims:
        lines.append(
            f"- 内部構造3層: breadth={structure_dims.get('breadth', '-')} / leadership={structure_dims.get('leadership', '-')} / stability={structure_dims.get('stability', '-')}"
        )
        lines.append(f"- 内部構造要約: {_structure_summary_ja(structure)}")
    structure_detail = structure.get("structure_detail", {})
    if structure_detail:
        lines.append(f"- stability内訳: {_stability_detail_summary_ja(structure)}")
    if structure.get("dominant_sector"):
        lines.append(f"- 単独主導セクター: {structure.get('dominant_sector')}")
        if structure.get("dominance_strength"):
            lines.append(f"- 単独主導強度: {structure.get('dominance_strength')}")
        if structure.get("dominance_reason_short"):
            lines.append(f"- 単独主導理由: {structure.get('dominance_reason_short')}")
        if structure.get("dominance_components"):
            lines.append(f"- 単独主導内訳: {_dominance_components_ja(structure)}")
    lines.append(
        "- 次候補セクター: "
        + (
            ", ".join(f"{row.get('ticker', '-')}({row.get('sector_name_ja', '-')})" for row in next_candidates)
            if next_candidates
            else "なし"
        )
    )
    lines.append(
        "- 失速警戒セクター: "
        + (
            ", ".join(f"{row.get('ticker', '-')}({row.get('sector_name_ja', '-')})" for row in peakout_sectors)
            if peakout_sectors
            else "なし"
        )
    )
    sector_explain_lines = _sector_adjustment_summary_lines(report)
    lines.extend(sector_explain_lines)

    lines.extend(["", "## 資産クラス比較", f"- {SECTION_EXPLANATIONS['asset']}"])
    for row in report["asset_compare"]:
        lines.append(
            f"- {row['asset_class']} ({row['ticker']} / {row['ticker_name_ja']}): 12週モメンタム {row['momentum_12w']}, 年率ボラ {row['annualized_volatility']}, 最大DD {row['max_drawdown']}"
        )

    lines.extend(["", "## 信用監視", f"- {SECTION_EXPLANATIONS['credit']}"])
    for row in report.get("credit_monitor", []):
        lines.append(
            f"- {row['ticker']} ({row['ticker_name_ja']}): 現在値 {row['current']} / 1週 {row['change_1w']} / 4週 {row['change_4w']} / 12週 {row['change_12w']} / z {row['zscore']} / 判定 {row['signal_label']}"
        )

    lines.extend(["", "## インフレ監視", f"- {SECTION_EXPLANATIONS['inflation']}"])
    for row in report.get("inflation_monitor", []):
        lines.append(
            f"- {row['ticker']} ({row['ticker_name_ja']}): 現在値 {row['current']} / 1週 {row['change_1w']} / 4週 {row['change_4w']} / 12週 {row['change_12w']} / z {row['zscore']} / 判定 {row['signal_label']}"
        )

    lines.extend(["", "## 円建て・為替リスク", f"- {SECTION_EXPLANATIONS['japan_risk']}"])
    lines.append(f"- 判定: {_jp_japan_risk_level(japan_risk.get('level'))}")
    lines.append(f"- 要約: {japan_risk.get('summary', '-')}")
    usd_jpy = japan_risk.get("usd_jpy", {})
    if usd_jpy:
        lines.append(
            f"- {usd_jpy.get('ticker', 'USDJPY=X')} ({usd_jpy.get('ticker_name_ja', '米ドル円')}): 現在値 {_display_number(usd_jpy.get('current'))} / 1週 {_display_number(usd_jpy.get('change_1w'))} / 4週 {_display_number(usd_jpy.get('change_4w'))} / 12週 {_display_number(usd_jpy.get('change_12w'))} / z {_display_number(usd_jpy.get('zscore'))} / 判定 {usd_jpy.get('signal_label', '-')}"
        )
    for row in japan_risk.get("foreign_assets", []):
        lines.append(
            f"- {row.get('asset_class', '-')} ({row.get('ticker', '-')} / {row.get('ticker_name_ja', '-')}): USD建て4週 {row.get('usd_return_4w', '-')} / 円建て4週 {row.get('jpy_return_4w', '-')} / 為替寄与 {row.get('fx_contribution_4w', '-')} / 円建て最大DD {row.get('jpy_max_drawdown', '-')} / 判定 {row.get('signal_label', '-')}"
        )

    candidate = report.get("investment_candidates", {})
    lines.extend(["", "## 危険ライン監視", f"- {SECTION_EXPLANATIONS['risk_lines']}"])
    lines.append(f"- 段階: {risk_stage_badge}")
    lines.append(f"- 要約: {risk_lines.get('summary', '-')}")
    lines.append(f"- 厳密性: {risk_lines.get('precision_label', '-')}")
    lines.append(
        f"- 不足指標: {', '.join(risk_lines.get('strict_missing_indicators', []) or risk_lines.get('missing_indicators', [])) or 'なし'}"
    )
    lines.append(f"- 総合ストレス指数: {_display_number(risk_lines.get('composite_risk_score'))}")
    lines.append(f"- 合成スコア側の内部警告件数: {internal_warning_count}")
    lines.append("- 注記: 内部警告件数は alerts/warnings の件数で、危険ライン段階とは別の判定です。")
    audit = report.get("risk_line_confidence_audit") or {}
    if audit:
        lines.extend(_risk_line_confidence_audit_markdown_lines(audit))
    lines.append(f"- 危険ライン本数: {risk_lines.get('danger_count', 0)} / 非常に危険ライン本数: {risk_lines.get('extreme_count', 0)}")
    for reason in risk_lines.get("reasons", []):
        lines.append(f"- {reason}")
    for row in risk_lines.get("indicators", []):
        line_badge = _risk_badge_markdown(row.get("line_level_label", "-"), _risk_label_tone(row.get("line_level_label")))
        lines.append(
            f"- {row.get('ticker_name_ja', row.get('ticker', '-'))} ({row.get('ticker', '-')}): 現在値 {_display_number(row.get('current'))} / 1週 {_display_number(row.get('change_1w'))} / 4週 {_display_number(row.get('change_4w'))} / z {_display_number(row.get('zscore'))} / 判定 {line_badge} / warning {_format_risk_threshold_markdown(row.get('warning_line', '-'))} / danger {_format_risk_threshold_markdown(row.get('danger_line', '-'))} / extreme {_format_risk_threshold_markdown(row.get('extreme_line', '-'))}"
        )
        lines.append(f"  - 本判定根拠: {_risk_accepted_rule_summary(row)}")
        lines.append(f"  - 参考・除外根拠: {_risk_diagnostic_rule_summary(row)}")
    lines.extend(_hindenburg_omen_markdown_lines(report))
    lines.extend(_domestic_danger_markdown_lines(report))
    lines.extend(_japan_resident_integrated_context_markdown_lines(report))

    lines.extend(["", "## 投資候補", f"- {SECTION_EXPLANATIONS['candidates']}"])
    lines.append(f"- 判定: {candidate.get('label', '候補なし')}")
    lines.append(f"- 要約: {candidate.get('summary', '-')}")
    asset_candidate = candidate.get("preferred_asset_class")
    sector_candidate = candidate.get("preferred_sector")
    if asset_candidate:
        lines.append(
            f"- 優先資産: {asset_candidate.get('asset_class', '-')} ({asset_candidate.get('ticker', '-')} / {asset_candidate.get('ticker_name_ja', '-')})"
        )
    if sector_candidate:
        lines.append(f"- 優先セクター: {sector_candidate.get('sector_name_ja', '-')} ({sector_candidate.get('ticker', '-')})")
    tickers = candidate.get("candidate_tickers", [])
    if tickers:
        lines.append("- 候補ティッカー: " + ", ".join(f"{item.get('ticker', '-')}({item.get('label', '-')})" for item in tickers))
    for reason in candidate.get("rationale", []):
        lines.append(f"- {_localize_display_text(reason)}")

    lines.extend(_multi_asset_candidate_markdown_lines(report))

    recovery = report.get("recovery_candidates", {})
    lines.extend(["", "## 先回り候補", f"- {SECTION_EXPLANATIONS['recovery_candidates']}"])
    lines.append(f"- 判定: {recovery.get('label', '候補なし')}")
    lines.append(f"- 要約: {recovery.get('summary', '-')}")
    recovery_asset = recovery.get("preferred_asset_class")
    recovery_sector = recovery.get("preferred_sector")
    if recovery_asset:
        lines.append(
            f"- 優先資産: {recovery_asset.get('label', '-')} ({recovery_asset.get('ticker', '-')} / {recovery_asset.get('ticker_name_ja', '-')})"
        )
    if recovery_sector:
        lines.append(f"- 優先セクター: {recovery_sector.get('ticker_name_ja', '-')} ({recovery_sector.get('ticker', '-')})")
    recovery_tickers = recovery.get("candidate_tickers", [])
    if recovery_tickers:
        lines.append("- 候補ティッカー: " + ", ".join(f"{item.get('ticker', '-')}({item.get('label', '-')})" for item in recovery_tickers))
    for reason in recovery.get("rationale", []):
        lines.append(f"- {_localize_display_text(reason)}")

    regime_leading = report.get("regime_leading_candidates", {})
    lines.extend(["", "## レジーム先回り候補", f"- {SECTION_EXPLANATIONS['regime_leading_candidates']}"])
    lines.append(f"- 判定: {regime_leading.get('label', '候補なし')}")
    lines.append(f"- 要約: {regime_leading.get('summary', '-')}")
    leading_sector = regime_leading.get("preferred_sector")
    if leading_sector:
        lines.append(f"- 優先セクター: {leading_sector.get('ticker_name_ja', '-')} ({leading_sector.get('ticker', '-')})")
    leading_region = regime_leading.get("preferred_region")
    if leading_region:
        lines.append(f"- 優先地域: {leading_region.get('ticker_name_ja', '-')} ({leading_region.get('ticker', '-')})")
    leading_asset = regime_leading.get("preferred_asset_class")
    if leading_asset:
        lines.append(f"- 優先資産: {leading_asset.get('ticker_name_ja', '-')} ({leading_asset.get('ticker', '-')})")
    leading_tickers = regime_leading.get("candidate_tickers", [])
    if leading_tickers:
        lines.append(
            "- 候補ティッカー: "
            + ", ".join(
                f"{item.get('ticker', '-')}({item.get('label', '-')}: {_localize_display_text(item.get('reason', '-'))})"
                for item in leading_tickers
            )
        )
    for reason in regime_leading.get("rationale", []):
        lines.append(f"- {_localize_display_text(reason)}")

    lines.extend(["", "## 警告レイヤー", f"- {SECTION_EXPLANATIONS['alerts']}"])
    alerts = report.get("alerts", [])
    if alerts:
        for alert in alerts:
            lines.append(
                f"- [{_alert_category_label(alert.get('category', 'memo'))} / {_alert_severity_label(alert.get('severity', 'low'))}] {alert.get('title', '-')}: {alert.get('message', '-')}"
            )
    else:
        lines.append("- 現時点で追加の警告はありません。")

    lines.extend(["", "## 類似局面", f"- {SECTION_EXPLANATIONS['analogues']}"])
    if report["analogues"]:
        for row in report["analogues"]:
            lines.append(f"- {row['end_date']}: 類似度 {row['similarity']}, その後12週リターン {row['forward_12w_return']}")
    else:
        lines.append("- 十分に近い類似局面は抽出されませんでした。")

    lines.extend(["", "## データ取得状況", f"- {SECTION_EXPLANATIONS['availability']}"])
    for entry in report.get("data_availability", []):
        requested_name = entry.get("requested_ticker_name_ja") or entry["requested_ticker"]
        used = entry.get("used_ticker") or "-"
        used_name = entry.get("used_ticker_name_ja") or "-"
        alt = (
            ", ".join(
                f"{ticker}({name})"
                for ticker, name in zip(entry.get("alternatives", []), entry.get("alternatives_name_ja", []), strict=False)
            )
            if entry.get("alternatives")
            else "なし"
        )
        lines.append(
            f"- {entry['requested_ticker']} ({requested_name}): {STATUS_LABELS.get(entry['status'], entry['status'])} / 使用系列 {used} ({used_name}) / 代替候補 {alt} / {entry['message']}"
        )

    diagnostics = report.get("fetch_diagnostics", {})
    runtime_context = report.get("runtime_context", {})
    summary = diagnostics.get("summary", {})
    lines.extend(["", "## 接続診断", f"- {SECTION_EXPLANATIONS['diagnostics']}"])
    lines.append(f"- 実行形態: {'配布 exe' if runtime_context.get('is_frozen') else 'Python 実行'}")
    lines.append(f"- 実行ファイル: {runtime_context.get('python_executable', '-')}")
    lines.append(f"- 作業フォルダ: {runtime_context.get('working_directory', '-')}")
    lines.append(f"- 取得ソース: {summary.get('source', report.get('data_source', '-'))}")
    lines.append(f"- 判定信頼性: {_jp_reliability(report.get('data_reliability', {}).get('level', 'high'))}")
    lines.append(f"- 判定継続可否: {'可' if report.get('data_reliability', {}).get('decision_allowed', True) else '保留'}")
    lines.extend(_data_quality_markdown_lines(report))
    lines.append(f"- 失敗試行数: {summary.get('failed_attempt_count', 0)}")
    lines.append(f"- 接続不良疑い: {'あり' if summary.get('suspected_network_issue') else 'なし'}")
    hosts = diagnostics.get("suspected_hosts", [])
    lines.append(f"- 接続先候補ホスト: {', '.join(hosts) if hosts else '記録なし'}")
    samples = diagnostics.get("failure_samples", [])
    if samples:
        lines.append("- 代表エラー:")
        lines.extend([f"  - {sample}" for sample in samples])

    lines.extend(_action_validation_markdown_lines(report))

    lines.extend(["", "## 警告"])
    if report["warnings"]:
        lines.extend([f"- {warning}" for warning in report["warnings"]])
    else:
        lines.append("- 重要な警告はありません。")
    return "\n".join(lines) + "\n"


EXPLAIN_SIGNAL_LABELS = {
    "single_sector_dominance_warning": "単独主導警戒",
    "energy_dominance_warning": "エネルギー単独主導警戒",
    "peakout_warning": "失速警戒",
    "broad_improvement": "広がり改善",
    "cyclical_improving": "景気敏感改善",
    "defensive_leadership": "ディフェンシブ優位",
    "narrow_leadership": "物色集中",
    "cap": "上限制御",
}

EXPLAIN_STRENGTH_LABELS = {
    "weak": "弱",
    "medium": "中",
    "strong": "強",
}

STRUCTURE_BREADTH_LABELS = {
    "broad": "裾野は広い",
    "mixed": "裾野は中立",
    "narrow": "裾野は狭い",
}

STRUCTURE_LEADERSHIP_LABELS = {
    "cyclical": "景気敏感が主導",
    "defensive": "ディフェンシブが主導",
    "balanced": "主導は分散",
    "energy-led": "エネルギーが主導",
}

STRUCTURE_STABILITY_LABELS = {
    "accelerating": "動きは加速",
    "stable": "動きは継続",
    "decelerating": "動きは減速",
    "unclear": "動きは不明瞭",
}

DOMINANCE_COMPONENT_LABELS = {
    "concentration": "集中",
    "breadth_deficit": "裾野不足",
    "top_gap": "先頭優位",
}

DOMINANCE_LEVEL_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
}


def _format_explain_entry(entry: dict[str, Any]) -> str:
    raw_signal = str(entry.get("signal", "-")).strip().lower()
    signal = EXPLAIN_SIGNAL_LABELS.get(raw_signal, raw_signal.replace("_", " "))
    delta = entry.get("delta")
    strength = str(entry.get("strength") or "").strip().lower()
    parts = [signal]
    if strength:
        parts.append(f"強度={EXPLAIN_STRENGTH_LABELS.get(strength, strength)}")
    if delta is not None:
        try:
            delta_value = float(delta)
            label = "加点" if delta_value > 0 else "減点" if delta_value < 0 else "変化"
            parts.append(f"{label}={delta_value:+.2f}")
        except (TypeError, ValueError):
            parts.append(f"変化={delta}")
    return " / ".join(parts)


def _explain_priority(entry: dict[str, Any]) -> tuple[int, float]:
    signal = str(entry.get("signal", "")).strip().lower()
    delta = abs(float(entry.get("delta", 0.0) or 0.0))
    if signal == "cap":
        return (99, -delta)
    if signal in {"single_sector_dominance_warning", "energy_dominance_warning", "peakout_warning"}:
        return (0, -delta)
    if signal in {"broad_improvement", "cyclical_improving", "defensive_leadership", "narrow_leadership"}:
        return (1, -delta)
    return (2, -delta)


def _select_primary_explain_entry(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not entries:
        return None
    return sorted(entries, key=_explain_priority)[0]


def _sector_adjustment_summary_lines(report: dict[str, Any]) -> list[str]:
    regime_explain = report.get("regime", {}).get("sector_adjustment_explain", [])
    score_explain = report.get("score", {}).get("sector_integration_explain", [])
    spot_explain = report.get("spot_signal", {}).get("sector_adjustment_explain", [])
    lines: list[str] = []
    if regime_explain or score_explain or spot_explain:
        lines.append("- 補助反映要約:")
    regime_primary = _select_primary_explain_entry(regime_explain)
    score_primary = _select_primary_explain_entry(score_explain)
    spot_primary = _select_primary_explain_entry(spot_explain)
    if regime_primary:
        lines.append(f"- レジーム: {_format_explain_entry(regime_primary)}")
    if score_primary:
        lines.append(f"- 総合評価: {_format_explain_entry(score_primary)}")
    if spot_primary:
        lines.append(f"- スポット判定: {_format_explain_entry(spot_primary)}")
    return lines


def _structure_summary_ja(structure: dict[str, Any]) -> str:
    dims = structure.get("structure", {}) if isinstance(structure, dict) else {}
    if not dims:
        return "-"
    breadth = STRUCTURE_BREADTH_LABELS.get(str(dims.get("breadth", "")), str(dims.get("breadth", "-")))
    leadership_raw = str(dims.get("leadership", "-"))
    leadership = STRUCTURE_LEADERSHIP_LABELS.get(leadership_raw, f"主導={leadership_raw}")
    stability = STRUCTURE_STABILITY_LABELS.get(str(dims.get("stability", "")), str(dims.get("stability", "-")))
    return f"{breadth} / {leadership} / {stability}"


def _dominance_components_ja(structure: dict[str, Any]) -> str:
    components = structure.get("dominance_components", {}) if isinstance(structure, dict) else {}
    if not components:
        return "-"
    parts: list[str] = []
    for key in ("concentration", "breadth_deficit", "top_gap"):
        value = str(components.get(key, "")).strip().lower()
        if not value:
            continue
        parts.append(f"{DOMINANCE_COMPONENT_LABELS.get(key, key)}={DOMINANCE_LEVEL_LABELS.get(value, value)}")
    return " / ".join(parts) if parts else "-"


def _share_summary_ja(structure: dict[str, Any]) -> str:
    watch_share = float(structure.get("watch_share", 0.0) or 0.0)
    promising_share = float(structure.get("promising_share", 0.0) or 0.0)
    if watch_share >= 0.65:
        breadth = "裾野は十分"
    elif watch_share >= 0.4:
        breadth = "裾野は中程度"
    else:
        breadth = "裾野は限定的"

    if promising_share >= 0.35:
        promising = "有望比率は高い"
    elif promising_share >= 0.18:
        promising = "有望比率は中程度"
    else:
        promising = "有望比率は控えめ"
    return f"{breadth} / {promising}"


def _stability_detail_summary_ja(structure: dict[str, Any]) -> str:
    detail = structure.get("structure_detail", {}) if isinstance(structure, dict) else {}
    if not detail:
        return "-"
    consistency = str(detail.get("consistency", "-"))
    momentum_quality = str(detail.get("momentum_quality", "-"))

    consistency_label = {
        "aligned": "方向は揃っています",
        "mixed": "方向は混在しています",
        "fragile": "方向は崩れ気味です",
        "unclear": "方向は不明瞭です",
    }.get(consistency, f"方向={consistency}")

    momentum_label = {
        "accelerating": "勢いは加速しています",
        "stable": "勢いは安定しています",
        "decelerating": "勢いは減速しています",
        "unclear": "勢いは不明瞭です",
    }.get(momentum_quality, f"勢い={momentum_quality}")

    return f"{consistency_label} / {momentum_label}"


def _build_hero_summary_copy(report: dict[str, Any], risk_lines: dict[str, Any], decision_action: str) -> str:
    reliability = report.get("data_reliability", {})
    if not reliability.get("decision_allowed", True):
        return html.escape(str(reliability.get("reason", "重要系列の取得不足により判定を保留しています。")))

    stage_label = str(risk_lines.get("stage_label", "通常"))
    stage_summary = str(risk_lines.get("summary", "")).strip()
    prefix = f"市場ストレスが強く、{stage_label}です。"
    if "非常に危険" in stage_label:
        prefix = "市場ストレスが強く、非常に危険ラインに到達しています。"
    elif "危険" in stage_label:
        prefix = "市場ストレスが強く、危険ラインに達しています。"

    if decision_action == "待機":
        suffix = "トレンドの方向感は明瞭でなく、リスク管理を優先し、今は待機を推奨します。"
    elif decision_action == "監視継続":
        suffix = "回復の兆しはあるものの、まだ判断材料が揃い切らず、監視継続が妥当です。"
    else:
        suffix = "条件は改善しており、押し目検討の余地があります。"

    if stage_summary and "前提" in stage_summary:
        return html.escape(f"{prefix} {suffix}")
    return html.escape(f"{prefix} {suffix}")


def _localize_signal_value(value: Any) -> str:
    text = str(value)
    mapping = {
        "building": "形成中",
        "confirmed": "確認済み",
        "weak": "弱い",
        "caution": "注意",
        "neutral": "中立",
        "normal": "通常",
        "watch": "監視",
        "review": "要確認",
        "stable": "安定",
        "unavailable": "未取得",
        "transition": "移行局面",
        "late_cycle": "終盤局面",
        "upswing": "上昇局面",
        "risk_on": "リスクオン",
        "risk_off": "リスクオフ",
    }
    return mapping.get(text, text)


def _localize_decision_reason(reason: Any) -> str:
    text = str(reason)
    exact = {
        "市場レジームは transition です。": "市場レジームは移行局面です。",
        "サイクル位相は upswing です。": "サイクル位相は上昇局面です。",
        "サイクル位相は late_cycle です。": "サイクル位相は終盤局面です。",
    }
    if text in exact:
        return exact[text]
    replacements = [
        ("transition と", "移行局面と"),
        ("late_cycle と", "終盤局面と"),
        ("upswing と", "上昇局面と"),
        ("inflation_shock と", "インフレショックと"),
        ("downswing と", "下落局面と"),
        ("risk_on と", "リスクオンと"),
        ("risk_off と", "リスクオフと"),
        (" transition ", " 移行局面 "),
        (" late_cycle ", " 終盤局面 "),
        (" upswing ", " 上昇局面 "),
        (" inflation_shock ", " インフレショック "),
        (" downswing ", " 下落局面 "),
        (" risk_on ", " リスクオン "),
        (" risk_off ", " リスクオフ "),
        ("transition", "移行局面"),
        ("late_cycle", "終盤局面"),
        ("upswing", "上昇局面"),
        ("inflation_shock", "インフレショック"),
        ("downswing", "下落局面"),
        ("building", "形成中"),
        ("caution", "注意"),
        ("neutral", "中立"),
        ("block", "強い警戒"),
        ("high", "高い"),
        ("moderate", "中程度"),
        ("low", "低い"),
    ]
    for src, dst in replacements:
        text = text.replace(src, dst)
    return text


def _jp_threshold_status(value: Any) -> str:
    return _localize_signal_value(value)


def _jp_review_target(value: Any) -> str:
    text = str(value)
    for src, dst in [(":warning", ":警戒"), (":danger", ":危険"), (":review", ":要確認"), (":watch", ":監視")]:
        text = text.replace(src, dst)
    return text


def _build_primary_reason_lines(report: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    risk_lines = report.get("risk_lines", {})
    for reason in risk_lines.get("reasons", []):
        localized = _localize_decision_reason(reason)
        if localized not in reasons:
            reasons.append(localized)
    for reason in report.get("spot_signal", {}).get("rationale", []):
        normalized = str(reason).strip()
        if not normalized:
            continue
        if any(token in normalized for token in ("市場レジーム", "サイクル位相", "合成スコア")):
            continue
        localized = _localize_decision_reason(normalized)
        if localized not in reasons:
            reasons.append(localized)
    blocker_summary = str(report.get("spot_signal", {}).get("blocker_assessment", {}).get("summary", "")).strip()
    if blocker_summary and blocker_summary not in reasons:
        reasons.insert(0, blocker_summary)
    return reasons[:3]


def _score_ratio(score_value: Any, maximum: float = 1.0) -> float:
    try:
        value = float(score_value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(value):
        return 0.0
    return min(max(value / maximum, 0.0), 1.0)


def _build_risk_highlight_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    indicators = report.get("risk_lines", {}).get("indicators", [])
    priority = ["^VIX", "CL=F", "DX-Y.NYB", "^TNX"]
    selected: list[dict[str, Any]] = []
    for ticker in priority:
        row = next((item for item in indicators if str(item.get("ticker")) == ticker), None)
        if row:
            selected.append(row)
    return selected[:4]


def _risk_meter_ratio(row: dict[str, Any]) -> float:
    current = row.get("current")
    warning = row.get("warning_line")
    danger = row.get("danger_line")
    extreme = row.get("extreme_line")
    numeric_values: list[float] = []
    for value in (warning, danger, extreme):
        try:
            numeric_values.append(abs(float(str(value).split(":", 1)[-1])))
        except (TypeError, ValueError):
            continue
    try:
        current_value = abs(float(current))
    except (TypeError, ValueError):
        current_value = 0.0
    upper = max(numeric_values + [current_value, 1.0])
    return min(max(current_value / upper, 0.0), 1.0)


def _risk_pressure_ratio(row: dict[str, Any]) -> float:
    try:
        score = float(row.get("pressure_score"))
    except (TypeError, ValueError):
        score = _risk_meter_ratio(row)
    return min(max(score, 0.0), 1.0)


def _risk_threshold_short_text(value: Any) -> str:
    text = str(value or "-")
    labels = {
        "level_zscore": "水準Z",
        "level_percentile": "水準位置",
        "level_and_roc_4w": "水準+4週",
        "level_and_roc_8w": "水準+8週",
        "roc_1w": "1週変化",
        "roc_2w": "2週変化",
        "roc_4w": "4週変化",
        "roc_8w": "8週変化",
        "roc_z_1w": "1週変化Z",
        "roc_z_2w": "2週変化Z",
        "roc_z_4w": "4週変化Z",
        "roc_z_8w": "8週変化Z",
        "drawdown_13w": "13週下落",
        "drawdown_zscore": "下落Z",
    }
    for source, label in labels.items():
        text = text.replace(source, label)
    return _localize_display_text(text)


def _risk_track_row_html(row: dict[str, Any]) -> str:
    oil_context = row.get("oil_context") if row.get("ticker") in {"CL=F", "BZ=F"} else None
    if isinstance(oil_context, dict):
        return _oil_risk_track_row_html(row, oil_context)
    pressure = _risk_pressure_ratio(row)
    pressure_pct = pressure * 100.0
    tone = _risk_label_tone(row.get("line_level_label"))
    label = str(row.get("ticker_name_ja", row.get("ticker", "-"))).replace("先物", "")
    current = _display_compact_number(row.get("current"))
    warning = _risk_threshold_short_text(row.get("warning_line"))
    danger = _risk_threshold_short_text(row.get("danger_line"))
    extreme = _risk_threshold_short_text(row.get("extreme_line"))
    accepted = _risk_accepted_rule_summary(row)
    diagnostic = _risk_diagnostic_rule_summary(row)
    return (
        "<div class='risk-track-row'>"
        "<div class='risk-track-head'>"
        f"<div class='risk-track-label'>{html.escape(label)}</div>"
        f"<div class='risk-track-value'>現在 {html.escape(current)}</div>"
        f"<div class='risk-track-state'>{_risk_badge_html(row.get('line_level_label', '-'), tone)}</div>"
        "</div>"
        "<div class='risk-track-bar' aria-label='危険度 {score:.0f} / 100'>"
        f"<span class='risk-track-fill {html.escape(tone)}' style='width:{pressure_pct:.1f}%'></span>"
        "<span class='risk-track-marker warning' title='注意ライン'></span>"
        "<span class='risk-track-marker danger' title='危険ライン'></span>"
        "<span class='risk-track-marker extreme' title='非常に危険ライン'></span>"
        "</div>"
        "<div class='risk-track-scale'><span>通常</span><span>注意</span><span>危険</span><span>非常に危険</span></div>"
        "<div class='risk-track-thresholds'>"
        f"<span>危険度 {pressure_pct:.0f}/100</span>"
        f"<span>注意: {html.escape(warning)}</span>"
        f"<span>危険: {html.escape(danger)}</span>"
        f"<span>非常に危険: {html.escape(extreme)}</span>"
        "</div>"
        "<div class='risk-track-proof'>"
        f"<span>本判定根拠: {html.escape(accepted)}</span>"
        f"<span>参考・除外: {html.escape(diagnostic)}</span>"
        "</div>"
        "</div>"
    ).format(score=pressure_pct)


def _oil_risk_track_row_html(row: dict[str, Any], oil_context: dict[str, Any]) -> str:
    inflation_score = _optional_score_pct(oil_context.get("inflation_pressure_score"))
    demand_score = _optional_score_pct(oil_context.get("demand_collapse_score"))
    pressure_pct = max(inflation_score or 0.0, demand_score or 0.0)
    status = str(oil_context.get("overall_status", "normal"))
    tone = _oil_status_tone(status)
    label = str(row.get("ticker_name_ja", row.get("ticker", "-"))).replace("先物", "")
    current = _display_compact_number(row.get("current"))
    inflation_label = _score_or_unavailable(oil_context.get("inflation_pressure_score"))
    demand_label = _score_or_unavailable(oil_context.get("demand_collapse_score"))
    wti_20d = _percent_or_dash(oil_context.get("wti_return_20d"))
    data_quality = _oil_data_quality_label(oil_context)
    reason = str(oil_context.get("reason", "-"))
    status_label = _oil_status_label(status)
    if not oil_context.get("risk_signal_allowed", False):
        pressure_pct = 0.0
    return (
        "<div class='risk-track-row oil-context-row'>"
        "<div class='risk-track-head'>"
        f"<div class='risk-track-label'>{html.escape(label)}</div>"
        f"<div class='risk-track-value'>現在 {html.escape(current)}</div>"
        f"<div class='risk-track-state'>{_risk_badge_html(status_label, tone)}</div>"
        "</div>"
        f"<div class='risk-track-bar' aria-label='原油方向別圧力 {pressure_pct:.0f} / 100'>"
        f"<span class='risk-track-fill {html.escape(tone)}' style='width:{pressure_pct:.1f}%'></span>"
        "<span class='risk-track-marker warning' title='確認ライン'></span>"
        "<span class='risk-track-marker danger' title='ストレスライン'></span>"
        "<span class='risk-track-marker extreme' title='強いストレスライン'></span>"
        "</div>"
        "<div class='risk-track-scale'><span>通常</span><span>確認</span><span>ストレス</span><span>強いストレス</span></div>"
        "<div class='risk-track-thresholds'>"
        f"<span>インフレ方向圧力 {html.escape(inflation_label)}</span>"
        f"<span>需要減速方向 {html.escape(demand_label)}</span>"
        f"<span>4週変化 {html.escape(wti_20d)}</span>"
        f"<span>データ品質 {html.escape(data_quality)}</span>"
        "</div>"
        "<div class='risk-track-proof'>"
        f"<span>判定理由: {html.escape(reason)}</span>"
        f"<span>参考・除外: {html.escape(_oil_limitations_text(oil_context))}</span>"
        "</div>"
        "</div>"
    )


def _optional_score_pct(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return min(max(numeric, 0.0), 100.0)


def _score_or_unavailable(value: Any) -> str:
    numeric = _optional_score_pct(value)
    if numeric is None:
        return "未評価"
    return f"{numeric:.0f}/100"


def _percent_or_dash(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    if math.isnan(numeric):
        return "-"
    return f"{numeric * 100:.1f}%"


def _oil_status_label(status: str) -> str:
    return {
        "normal": "通常",
        "inflation_watch": "インフレ確認",
        "demand_watch": "需要減速確認",
        "inflation_stress": "インフレ圧力",
        "demand_stress": "需要減速",
        "unavailable": "参考外",
    }.get(status, status)


def _oil_status_tone(status: str) -> str:
    if status in {"inflation_stress", "demand_stress"}:
        return "danger"
    if status in {"inflation_watch", "demand_watch"}:
        return "caution"
    if status == "unavailable":
        return "weak"
    return "normal"


def _oil_data_quality_label(oil_context: dict[str, Any]) -> str:
    if oil_context.get("risk_signal_allowed", False):
        return "有効"
    flags = oil_context.get("quality_flags", [])
    if "suspicious_discontinuity" in flags:
        return "先物ロール/不連続疑い"
    if "same_observation_comparison" in flags:
        return "比較値なし"
    if "comparison_unavailable" in flags:
        return "算出不可"
    if "stale" in flags:
        return "データ遅延"
    return "参考外"


def _oil_limitations_text(oil_context: dict[str, Any]) -> str:
    limitations = [str(item) for item in oil_context.get("limitations", []) if str(item).strip()]
    return " / ".join(limitations[:2]) if limitations else "なし"


def _build_sector_overview_rows(sector_context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(sector_context.get("rows", []))
    if not rows:
        return []
    return sorted(rows, key=lambda item: float(item.get("return_12w", 0.0) or 0.0), reverse=True)


def _sector_bar_width(value: Any, max_abs: float) -> float:
    try:
        numeric = abs(float(value))
    except (TypeError, ValueError):
        return 0.0
    if max_abs <= 0:
        return 0.0
    return min(max((numeric / max_abs) * 100.0, 0.0), 100.0)


def _build_history_embed_payload(entries: list[dict[str, Any]]) -> dict[str, Any]:
    latest_by_day: dict[str, dict[str, Any]] = {}
    compact_entries: list[dict[str, Any]] = []
    for entry in entries:
        generated_at = str(entry.get("generated_at", ""))
        compact_entries.append(
            {
                "generated_at": generated_at,
                "score": entry.get("score"),
                "regime": {
                    "key": entry.get("regime", {}).get("key", "data_unavailable"),
                    "label": entry.get("regime", {}).get("label", "-"),
                },
            }
        )
        day_key = generated_at[:10]
        existing = latest_by_day.get(day_key)
        if existing is None or generated_at > str(existing.get("generated_at", "")):
            latest_by_day[day_key] = entry
    return {
        "history": compact_entries,
        "meta": {
            "history_count": len(entries),
            "daily_latest_count": len(latest_by_day),
            "primary_basis": "daily_latest",
        },
    }


def _render_supplement_dashboard_html_legacy(report: dict[str, Any], history_entries: list[dict[str, Any]] | None = None) -> str:
    """Render the earlier tabbed supplemental dashboard layout."""
    sector_payload = report.get("sector_rotation", {})
    sector_context = _build_sector_rotation_context(sector_payload)
    sector_svg = _render_sector_rotation_svg(sector_payload, sector_context)
    sector_structure = sector_payload.get("internal_structure") or report.get("internal_structure", {})
    sector_next_candidates = sector_payload.get("next_candidates") or report.get("next_candidates", [])
    sector_peakout_sectors = sector_payload.get("peakout_sectors") or report.get("peakout_sectors", [])
    sector_market_structure_comment = sector_payload.get("market_structure_comment") or report.get("market_structure_comment", "-")
    risk_lines = report.get("risk_lines", {})
    spot_signal = report.get("spot_signal", {})
    recovery_evidence = spot_signal.get("recovery_evidence", {})
    blocker_assessment = spot_signal.get("blocker_assessment", {})
    action_decision = spot_signal.get("action_decision", {})
    threshold_drift = report.get("risk_threshold_drift") or {}
    drift_summary = threshold_drift.get("summary") or {}
    threshold_review = report.get("risk_threshold_review") or {}
    threshold_maintenance = report.get("risk_threshold_maintenance") or {}
    candidate = report.get("investment_candidates", {})
    recovery = report.get("recovery_candidates", {})
    regime_leading = report.get("regime_leading_candidates", {})
    domestic_danger = report.get("domestic_danger_context") or {}
    integrated_context = report.get("japan_resident_integrated_risk_context") or {}
    hindenburg_omen = report.get("hindenburg_omen_context") or {}
    japan_risk = report.get("japan_risk", {})
    diagnostics = report.get("fetch_diagnostics", {})
    runtime_context = report.get("runtime_context", {})
    diagnostic_summary = diagnostics.get("summary", {})
    history_payload = _build_history_embed_payload(history_entries or [])
    history_payload_json = json.dumps(history_payload, ensure_ascii=False).replace("</", "<\\/")

    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else "-"))

    def compact(value: Any) -> str:
        return html.escape(_display_compact_number(value))

    def number(value: Any) -> str:
        return html.escape(_display_number(value))

    def source_chip(name: str) -> str:
        return f'<span class="source-chip">元: {esc(name)}</span>'

    def kv_card(label: str, value: Any, note: str = "", tone: str = "", raw_value: bool = False) -> str:
        tone_class = f" {tone}" if tone else ""
        note_html = f'<div class="metric-note">{esc(note)}</div>' if note else ""
        value_html = str(value) if raw_value else esc(value)
        return f'<div class="metric-card{tone_class}"><div class="metric-label">{esc(label)}</div><div class="metric-value">{value_html}</div>{note_html}</div>'

    def small_table(headers: list[str], rows: list[list[Any]], empty_colspan: int | None = None) -> str:
        head_html = "".join(f"<th>{esc(header)}</th>" for header in headers)
        if rows:
            body_html = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
        else:
            colspan = empty_colspan or len(headers)
            body_html = f'<tr><td colspan="{colspan}">有効データなし</td></tr>'
        return f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"

    def ticker_label(ticker: Any, name: Any) -> str:
        return f'{esc(ticker)}<br><span class="subtext">{esc(name)}</span>'

    history_entries_list = history_payload.get("history", [])
    latest_history = history_entries_list[-1] if history_entries_list else {}
    latest_regime = latest_history.get("regime", {}) if isinstance(latest_history, dict) else {}
    history_metrics = "".join(
        [
            kv_card("選択中の履歴時点", str(latest_history.get("generated_at", "履歴なし")).replace("T", " ")[:16]),
            kv_card("主基準 daily_latest", f"{history_payload.get('meta', {}).get('daily_latest_count', 0)}件"),
            kv_card("参考 all_history", f"{history_payload.get('meta', {}).get('history_count', 0)}件"),
            kv_card("最新レジーム", latest_regime.get("label", "-")),
            kv_card("最新スコア", latest_history.get("score", "-")),
        ]
    )

    risk_line_rows = [
        [
            ticker_label(row.get("ticker"), row.get("ticker_name_ja", row.get("ticker"))),
            _risk_badge_html(row.get("line_level_label", "-"), _risk_label_tone(row.get("line_level_label"))),
            number(row.get("current")),
            _format_risk_threshold_html(row.get("warning_line")),
            _format_risk_threshold_html(row.get("danger_line")),
            _format_risk_threshold_html(row.get("extreme_line")),
            esc(_risk_accepted_rule_summary(row)),
            esc(_risk_diagnostic_rule_summary(row)),
        ]
        for row in risk_lines.get("indicators", [])
    ]
    risk_line_table = small_table(["指標", "判定", "現在値", "warning", "danger", "extreme", "本判定根拠", "参考・除外"], risk_line_rows)
    risk_line_confidence_audit_html = _risk_line_confidence_audit_html(report.get("risk_line_confidence_audit") or {})
    hindenburg_omen_panel = _hindenburg_omen_panel_html(hindenburg_omen, esc)
    domestic_danger_panel = _domestic_danger_panel_html(domestic_danger, small_table, esc, source_chip)
    integrated_context_panel = _japan_resident_integrated_context_panel_html(integrated_context, small_table, esc, source_chip)
    sector_rows = [
        [
            esc(row.get("rank")),
            esc(row.get("ticker")),
            esc(row.get("sector_name_ja")),
            esc(row.get("return_12w")),
            esc(row.get("rotation_phase_ja")),
            f'<span class="status-pill neutral">{esc(row.get("candidate_label") or "様子見")}</span>',
        ]
        for row in sector_context.get("rows", [])
    ]
    sector_table = small_table(["順位", "ETF", "日本語", "12週騰落率", "位置", "判定"], sector_rows)

    asset_rows = [
        [
            esc(row.get("asset_class")),
            ticker_label(row.get("ticker"), row.get("ticker_name_ja")),
            esc(row.get("momentum_12w")),
            esc(row.get("annualized_volatility")),
            esc(row.get("max_drawdown")),
        ]
        for row in report.get("asset_compare", [])
    ]
    asset_table = small_table(["資産クラス", "ティッカー", "12週モメンタム", "年率ボラ", "最大DD"], asset_rows)

    credit_rows = [
        [
            ticker_label(row.get("ticker"), row.get("ticker_name_ja")),
            esc(row.get("current")),
            esc(row.get("change_1w")),
            esc(row.get("change_4w")),
            esc(row.get("change_12w")),
            esc(row.get("zscore")),
            esc(row.get("signal_label")),
        ]
        for row in report.get("credit_monitor", [])
    ]
    credit_table = small_table(["系列", "現在値", "1週", "4週", "12週", "zスコア", "判定"], credit_rows)

    inflation_rows = [
        [
            ticker_label(row.get("ticker"), row.get("ticker_name_ja")),
            esc(row.get("current")),
            esc(row.get("change_1w")),
            esc(row.get("change_4w")),
            esc(row.get("change_12w")),
            esc(row.get("zscore")),
            esc(row.get("signal_label")),
        ]
        for row in report.get("inflation_monitor", [])
    ]
    inflation_table = small_table(["系列", "現在値", "1週", "4週", "12週", "zスコア", "判定"], inflation_rows)

    usd_jpy = japan_risk.get("usd_jpy", {})
    fx_rows = []
    if usd_jpy:
        fx_rows.append(
            [
                ticker_label(usd_jpy.get("ticker", "USDJPY=X"), usd_jpy.get("ticker_name_ja", "米ドル円")),
                number(usd_jpy.get("current")),
                number(usd_jpy.get("change_1w")),
                number(usd_jpy.get("change_4w")),
                number(usd_jpy.get("change_12w")),
                number(usd_jpy.get("zscore")),
                esc(usd_jpy.get("signal_label", "-")),
            ]
        )
    fx_table = small_table(["為替", "現在値", "1週", "4週", "12週", "zスコア", "判定"], fx_rows)
    yen_asset_rows = [
        [
            esc(row.get("asset_class")),
            ticker_label(row.get("ticker"), row.get("ticker_name_ja")),
            esc(row.get("usd_return_4w")),
            esc(row.get("jpy_return_4w")),
            esc(row.get("fx_contribution_4w")),
            esc(row.get("jpy_max_drawdown")),
            esc(row.get("signal_label")),
        ]
        for row in japan_risk.get("foreign_assets", [])
    ]
    yen_asset_table = small_table(["資産", "ティッカー", "USD建て4週", "円建て4週", "為替寄与", "円建て最大DD", "判定"], yen_asset_rows)

    alert_cards = (
        "".join(
            '<div class="warning-card">'
            f'<div class="warning-title">{esc(alert.get("title", "-"))}</div>'
            f'<div class="warning-meta">{esc(_alert_category_label(alert.get("category", "memo")))} / {esc(_alert_severity_label(alert.get("severity", "low")))}</div>'
            f'<p>{esc(alert.get("message", "-"))}</p>'
            "</div>"
            for alert in report.get("alerts", [])
        )
        or '<div class="empty-box">現時点で追加の警告はありません。</div>'
    )

    analogue_rows = [
        [esc(row.get("end_date")), esc(row.get("similarity")), esc(row.get("forward_12w_return"))] for row in report.get("analogues", [])
    ]
    analogue_table = small_table(
        ["基準日", "類似度", "その後12週リターン"], analogue_rows or [["十分に近い類似局面は抽出されませんでした。", "", ""]]
    )

    availability_rows = [
        [
            ticker_label(entry.get("requested_ticker"), entry.get("requested_ticker_name_ja", entry.get("requested_ticker"))),
            f'<span class="status-pill ok">{esc(STATUS_LABELS.get(entry.get("status"), entry.get("status")))}</span>',
            ticker_label(entry.get("used_ticker") or "-", entry.get("used_ticker_name_ja") or "-"),
            esc(
                ", ".join(
                    f"{ticker}({name})"
                    for ticker, name in zip(entry.get("alternatives", []), entry.get("alternatives_name_ja", []), strict=False)
                )
                if entry.get("alternatives")
                else "なし"
            ),
            esc(entry.get("message", "-")),
        ]
        for entry in report.get("data_availability", [])
    ]
    availability_table = small_table(["要求系列", "状態", "実使用系列", "代替候補", "説明"], availability_rows)

    diagnostic_rows = [
        ["実行形態", "配布 exe" if runtime_context.get("is_frozen") else "Python 実行"],
        ["実行ファイル", runtime_context.get("python_executable", "-")],
        ["作業フォルダ", runtime_context.get("working_directory", "-")],
        ["取得ソース", diagnostic_summary.get("source", report.get("data_source", "-"))],
        *_execution_mode_html_rows(report),
        *_data_quality_html_rows(report),
        ["失敗試行数", diagnostic_summary.get("failed_attempt_count", 0)],
        ["接続不良疑い", "あり" if diagnostic_summary.get("suspected_network_issue") else "なし"],
        ["接続先候補ホスト", ", ".join(diagnostics.get("suspected_hosts", [])) or "記録なし"],
    ]
    diagnostic_table = small_table(["項目", "内容"], [[esc(k), esc(v)] for k, v in diagnostic_rows])
    diagnostic_errors = (
        "".join(f"<li>{esc(item)}</li>" for item in diagnostics.get("failure_samples", [])) or "<li>代表エラーは記録されていません。</li>"
    )

    candidate_tickers = (
        ", ".join(f"{item.get('ticker', '-')}({item.get('label', '-')})" for item in candidate.get("candidate_tickers", [])) or "なし"
    )
    recovery_tickers = (
        ", ".join(f"{item.get('ticker', '-')}({item.get('label', '-')})" for item in recovery.get("candidate_tickers", [])) or "なし"
    )
    regime_leading_tickers = (
        ", ".join(
            f"{item.get('ticker', '-')}({item.get('label', '-')}: {item.get('reason', '-')})"
            for item in regime_leading.get("candidate_tickers", [])
        )
        or "なし"
    )
    candidate_rationale = (
        "".join(f"<li>{esc(_localize_display_text(reason))}</li>" for reason in candidate.get("rationale", []))
        or "<li>候補提示の条件がまだ揃っていません。</li>"
    )
    multi_asset = report.get("multi_asset_candidates") or {}
    multi_asset_rows = [
        [
            esc(row.get("asset_class_label", "-")),
            ticker_label(row.get("symbol", "-"), row.get("display_name", "-")),
            esc(row.get("role_label", "-")),
            esc(_multi_asset_status_label(row.get("status"))),
            "あり" if row.get("source_data_available") else "なし",
            '{reason}<br><span class="subtext">分類: {category} / 注意: {caution}</span>'.format(
                reason=esc(row.get("reason", "-")),
                category=esc(_multi_asset_reason_category_label(row.get("reason_category"))),
                caution=esc(row.get("caution", "-")),
            ),
        ]
        for row in multi_asset.get("candidates", [])
    ]
    multi_asset_table = small_table(
        ["資産クラス", "候補", "役割", "状態", "データ", "理由"],
        multi_asset_rows or [["候補データなし", "", "", "", "", ""]],
    )
    multi_asset_panel = (
        '<section class="panel mt"><h3>資産クラス別の確認候補 {source}</h3>'
        "<p>{summary}</p><p><strong>注意:</strong> {disclaimer}</p>"
        '<ul class="compact-list"><li>最終判断への影響: {final_action}</li>'
        "<li>買い候補度への影響: {readiness}</li></ul>"
        '<div class="table-wrap">{table}</div></section>'
    ).format(
        source=source_chip("資産クラス別の確認候補"),
        summary=esc(multi_asset.get("summary", "-")),
        disclaimer=esc(multi_asset.get("disclaimer", "-")),
        final_action=esc(_display_bool(multi_asset.get("affects_final_action", False))),
        readiness=esc(_display_bool(multi_asset.get("affects_buy_readiness_score", False))),
        table=multi_asset_table,
    )
    recovery_rationale = (
        "".join(f"<li>{esc(_localize_display_text(reason))}</li>" for reason in recovery.get("rationale", []))
        or "<li>先回り候補の条件はまだ揃っていません。</li>"
    )
    regime_leading_rationale = (
        "".join(f"<li>{esc(_localize_display_text(reason))}</li>" for reason in regime_leading.get("rationale", []))
        or "<li>レジーム先回り候補の条件はまだ揃っていません。</li>"
    )
    decision_rationale = "".join(f"<li>{esc(_localize_display_text(reason))}</li>" for reason in spot_signal.get("rationale", []))
    risk_reason_items = (
        "".join(f"<li>{esc(_localize_decision_reason(reason))}</li>" for reason in risk_lines.get("reasons", []))
        or "<li>追加理由はありません。</li>"
    )
    sector_adjustment_items = "".join(f"<li>{esc(line.lstrip('- ').strip())}</li>" for line in _sector_adjustment_summary_lines(report))
    warning_items = "".join(f"<li>{esc(warning)}</li>" for warning in report.get("warnings", [])) or "<li>重要な警告はありません。</li>"

    structure_metrics = "".join(
        [
            kv_card("内部構造ラベル", sector_structure.get("structure_label", "-")),
            kv_card("セクター分散指標", sector_structure.get("dispersion_score", "-")),
            kv_card(
                "相対広がり",
                f"watch_share={sector_structure.get('watch_share', 0)} / promising_share={sector_structure.get('promising_share', 0)}",
            ),
            kv_card("内部構造3層", _structure_summary_ja(sector_structure)),
            kv_card(
                "失速警戒セクター",
                ", ".join(
                    f"{row.get('ticker', '-')}({row.get('sector_name_ja', row.get('ticker_name_ja', '-'))})"
                    for row in sector_peakout_sectors
                )
                or "なし",
            ),
            kv_card(
                "次候補セクター",
                ", ".join(
                    f"{row.get('ticker', '-')}({row.get('sector_name_ja', row.get('ticker_name_ja', '-'))})"
                    for row in sector_next_candidates
                )
                or "なし",
            ),
        ]
    )

    style = """
    :root { --bg:#f6f8fb; --surface:#ffffff; --surface-2:#f9fbfd; --ink:#172033; --muted:#667085; --line:#d9e2ec; --accent:#0f766e; --accent-soft:#e6f4f1; --warn:#d97706; --warn-soft:#fff4df; --bad:#dc2626; --bad-soft:#ffe8e8; --shadow:0 12px 32px rgba(15,23,42,.07); }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font-family:'Yu Gothic UI','Hiragino Sans',Meiryo,sans-serif; letter-spacing:0; }
    a { color:inherit; }
    .app { display:grid; grid-template-columns:216px minmax(0,1fr); min-height:100vh; }
    .side { position:sticky; top:0; height:100vh; padding:22px 16px; border-right:1px solid var(--line); background:#fff; }
    .brand { display:grid; gap:4px; padding:0 8px 18px; border-bottom:1px solid var(--line); }
    .brand strong { font-size:18px; line-height:1.2; }
    .brand span { color:var(--muted); font-size:12px; }
    .tabs { display:grid; gap:8px; margin-top:18px; }
    .tab-label { display:flex; align-items:center; justify-content:space-between; min-height:42px; padding:0 12px; border-radius:8px; color:#475467; font-weight:700; cursor:pointer; }
    .tab-label small { color:#98a2b3; font-size:11px; }
    .tab-label:hover { background:#f2f6f8; }
    input[name=tab] { position:absolute; opacity:0; pointer-events:none; }
    #tab-history:checked ~ .app .side label[for=tab-history],
    #tab-decision:checked ~ .app .side label[for=tab-decision],
    #tab-sector:checked ~ .app .side label[for=tab-sector],
    #tab-market:checked ~ .app .side label[for=tab-market],
    #tab-audit:checked ~ .app .side label[for=tab-audit] { background:var(--accent-soft); color:var(--accent); }
    .main { min-width:0; padding:22px 26px 46px; }
    .topbar { position:sticky; top:0; z-index:5; display:flex; justify-content:space-between; gap:16px; align-items:center; margin:-22px -26px 22px; padding:16px 26px; border-bottom:1px solid var(--line); background:rgba(246,248,251,.92); backdrop-filter:blur(10px); }
    .top-title h1 { margin:0; font-size:22px; }
    .top-title p { margin:4px 0 0; color:var(--muted); font-size:13px; }
    .actions { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
    .button { display:inline-flex; align-items:center; min-height:34px; padding:0 12px; border:1px solid var(--line); border-radius:8px; background:#fff; color:#344054; font-size:13px; font-weight:700; text-decoration:none; }
    .view { display:none; }
    #tab-history:checked ~ .app .view-history,
    #tab-decision:checked ~ .app .view-decision,
    #tab-sector:checked ~ .app .view-sector,
    #tab-market:checked ~ .app .view-market,
    #tab-audit:checked ~ .app .view-audit { display:block; }
    .view-head { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:18px; align-items:end; margin-bottom:16px; }
    .view-head h2 { margin:0; font-size:26px; }
    .view-head p { margin:8px 0 0; max-width:78ch; color:var(--muted); line-height:1.65; }
    .source-chip { display:inline-flex; align-items:center; min-height:24px; padding:0 8px; border:1px solid var(--line); border-radius:999px; background:#fff; color:var(--muted); font-size:11px; font-weight:700; white-space:nowrap; }
    .metrics { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; margin-bottom:14px; }
    .metric-card { min-width:0; padding:13px 14px; border:1px solid var(--line); border-radius:8px; background:var(--surface); box-shadow:0 1px 0 rgba(15,23,42,.02); }
    .metric-card.warn { border-color:#f3cf91; background:var(--warn-soft); }
    .metric-card.danger { border-color:#f7aaaa; background:var(--bad-soft); }
    .metric-label { color:var(--muted); font-size:12px; font-weight:700; }
    .metric-value { margin-top:6px; font-size:21px; line-height:1.18; font-weight:800; color:var(--ink); overflow-wrap:anywhere; }
    .metric-note { margin-top:6px; color:var(--muted); font-size:12px; line-height:1.45; }
    .grid-2 { display:grid; grid-template-columns:minmax(0,1.28fr) minmax(320px,.72fr); gap:14px; align-items:start; }
    .grid-even { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; align-items:start; }
    .grid-3 { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; align-items:stretch; }
    .panel { min-width:0; padding:16px; border:1px solid var(--line); border-radius:8px; background:var(--surface); box-shadow:var(--shadow); }
    .panel.tight { padding:13px; }
    .panel h3 { display:flex; justify-content:space-between; gap:10px; align-items:center; margin:0 0 10px; font-size:17px; }
    .panel p { margin:0 0 10px; color:var(--muted); line-height:1.6; font-size:13px; }
    .chart-shell { min-height:320px; border:1px solid var(--line); border-radius:8px; background:linear-gradient(180deg,#fff,#fbfdff); padding:10px; }
    .chart-shell svg { width:100%; height:auto; display:block; }
    .history-toolbar { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; align-items:center; margin-top:10px; padding:10px 12px; border:1px solid var(--line); border-radius:8px; background:var(--surface-2); }
    input[type=range] { width:100%; accent-color:var(--accent); }
    .detail-strip { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:10px; }
    .note-list, .compact-list { margin:0; padding-left:18px; color:#344054; line-height:1.65; font-size:13px; }
    .compact-list li + li { margin-top:4px; }
    .table-wrap { overflow:auto; border:1px solid var(--line); border-radius:8px; background:#fff; }
    table { width:100%; min-width:680px; border-collapse:separate; border-spacing:0; table-layout:auto; }
    th, td { padding:9px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; font-size:12.5px; line-height:1.45; overflow-wrap:normal; }
    td:not(:first-child), th:not(:first-child) { white-space:nowrap; }
    td:first-child, th:first-child { min-width:128px; }
    th { position:sticky; top:0; z-index:1; background:#f8fafc; color:#667085; font-size:12px; font-weight:800; }
    tr:last-child td { border-bottom:0; }
    .subtext { color:var(--muted); font-size:11px; }
    .status-pill, .risk-badge { display:inline-flex; align-items:center; min-height:24px; padding:0 8px; border-radius:999px; font-size:11px; font-weight:800; white-space:nowrap; }
    .status-pill.ok { background:var(--accent-soft); color:var(--accent); }
    .status-pill.neutral { background:#eef2f6; color:#475467; }
    .risk-badge.caution { background:var(--warn-soft); color:var(--warn); }
    .risk-badge.danger, .risk-badge.extreme { background:var(--bad-soft); color:var(--bad); }
    .decision-flow { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; margin:10px 0 14px; }
    .flow-step { padding:10px; border:1px solid var(--line); border-radius:8px; background:var(--surface-2); }
    .flow-step b { display:block; font-size:13px; }
    .flow-step span { display:block; margin-top:4px; color:var(--muted); font-size:12px; }
    .sector-layout { display:grid; grid-template-columns:minmax(0,1.08fr) minmax(420px,.92fr); gap:14px; align-items:start; }
    .sector-chart svg { width:100%; max-height:600px; }
    .warning-card { padding:12px; border:1px solid #f3cf91; border-radius:8px; background:var(--warn-soft); }
    .warning-card + .warning-card { margin-top:8px; }
    .warning-title { font-weight:800; }
    .warning-meta { margin-top:3px; color:var(--warn); font-size:12px; font-weight:800; }
    .empty-box { padding:12px; border:1px dashed var(--line); border-radius:8px; color:var(--muted); background:#fff; }
    .audit-targets { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
    .audit-targets span { padding:5px 8px; border-radius:999px; background:var(--warn-soft); color:var(--warn); font-size:12px; font-weight:800; }
    .stack { display:grid; gap:14px; }
    .mt { margin-top:14px; }
    @media (max-width: 980px) { .app { grid-template-columns:1fr; } .side { position:static; height:auto; border-right:0; border-bottom:1px solid var(--line); } .tabs { grid-template-columns:repeat(5,minmax(0,1fr)); overflow:auto; } .tab-label { justify-content:center; white-space:nowrap; } .tab-label small { display:none; } .main { padding:18px; } .topbar { position:static; margin:-18px -18px 18px; padding:14px 18px; flex-direction:column; align-items:flex-start; } .metrics, .grid-3 { grid-template-columns:1fr 1fr; } .grid-2, .grid-even, .sector-layout { grid-template-columns:1fr; } }
    @media (max-width: 620px) { .metrics, .grid-3, .detail-strip, .decision-flow { grid-template-columns:1fr; } .view-head { grid-template-columns:1fr; } .tabs { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    """

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>補足レポート ダッシュボード - {esc(report.get('title', 'グローバル市場モニター'))}</title>
  <style>{style}</style>
</head>
<body>
  <input id="tab-history" name="tab" type="radio" checked>
  <input id="tab-decision" name="tab" type="radio">
  <input id="tab-sector" name="tab" type="radio">
  <input id="tab-market" name="tab" type="radio">
  <input id="tab-audit" name="tab" type="radio">
  <div class="app">
    <aside class="side">
      <div class="brand"><strong>補足レポート</strong><span>現行17セクション / 10テーブルを5画面へ再配置</span></div>
      <nav class="tabs" aria-label="補足レポート画面">
        <label class="tab-label" for="tab-history">履歴 <small>History</small></label>
        <label class="tab-label" for="tab-decision">判定 <small>Decision</small></label>
        <label class="tab-label" for="tab-sector">セクター <small>Sector</small></label>
        <label class="tab-label" for="tab-market">市場監視 <small>Market</small></label>
        <label class="tab-label" for="tab-audit">監査 <small>Audit</small></label>
      </nav>
    </aside>
    <main class="main">
      <header class="topbar">
        <div class="top-title">
          <h1>補足レポート ダッシュボード</h1>
          <p>{esc(report.get('generated_at'))} JST / {esc(report.get('data_source'))} / 判定信頼性 {esc(_jp_reliability(report.get('data_reliability', {}).get('level', 'high')))}</p>
        </div>
        <div class="actions">
          <a class="button" href="report.html">最新レポートへ戻る</a>
          <a class="button" href="dashboard.html">履歴ダッシュボード</a>
        </div>
      </header>

      <section class="view view-history">
        <div class="view-head"><div><h2>履歴</h2><p>過去に保存された履歴だけを使うビューです。最新判断とは別枠なので、上段と値が違う場合は過去時点との差として読みます。</p></div>{source_chip('過去履歴ブラウズ')}</div>
        <div class="metrics">{history_metrics}</div>
        <div class="grid-2">
          <section class="panel">
            <h3>過去履歴ブラウズ {source_chip('過去履歴ブラウズ')}</h3>
            <div class="chart-shell"><svg id="supplementHistoryChart" viewBox="0 0 980 360" role="img" aria-label="履歴の合成スコア推移チャート"></svg></div>
            <div class="history-toolbar"><input id="supplementHistoryRange" type="range" min="0" max="0" value="0"><output id="supplementHistoryCount">0件</output></div>
            <div class="detail-strip">
              {kv_card('generated_at', '<span id="supplementHistoryTimestamp">履歴なし</span>', raw_value=True)}
              {kv_card('score', '<span id="supplementHistoryScore">-</span>', raw_value=True)}
              {kv_card('regime', '<span id="supplementHistoryRegime">-</span>', raw_value=True)}
            </div>
          </section>
          <aside class="panel">
            <h3>履歴の読み方</h3>
            <ul class="note-list">
              <li>主基準は <strong>daily_latest</strong> です。同日の再生成は最新1件へ圧縮します。</li>
              <li><strong>all_history</strong> は重複を含む全履歴の母数として残します。</li>
              <li>この画面は監査と時系列確認が目的です。最新判断は `report.html` の上段を優先します。</li>
            </ul>
          </aside>
        </div>
      </section>

      <section class="view view-decision">
        <div class="view-head"><div><h2>判定</h2><p>判定理由、危険ライン、候補抽出を同じ画面で確認し、最終判断に至った材料を追えるようにします。</p></div>{source_chip('判定の読み方 / 判定理由 / 危険ライン監視')}</div>
        <div class="metrics">
          {kv_card('市場レジーム', _jp_regime(report.get('regime', {}).get('regime_label')))}
          {kv_card('サイクル', _jp_cycle(report.get('cycle', {}).get('phase_label')))}
          {kv_card('合成スコア', compact(report.get('score', {}).get('total_score')))}
          {kv_card('判定用スコア', compact(spot_signal.get('legacy_adjusted_score', spot_signal.get('adjusted_score', report.get('score', {}).get('total_score')))))}
          {kv_card('最終判断', _jp_action(str(action_decision.get('action', spot_signal.get('action', '-')))))}
        </div>
        <div class="decision-flow">
          <div class="flow-step"><b>地合い</b><span>{esc(report.get('regime', {}).get('regime_label'))}</span></div>
          <div class="flow-step"><b>回復証拠</b><span>{esc(recovery_evidence.get('grade', '-'))} / score {compact(recovery_evidence.get('score'))}</span></div>
          <div class="flow-step"><b>警戒材料</b><span>{esc(blocker_assessment.get('level', '-'))}</span></div>
          <div class="flow-step"><b>行動</b><span>{esc(_jp_action(str(action_decision.get('action', spot_signal.get('action', '-')))))}</span></div>
        </div>
        <div class="grid-2">
          <section class="panel">
            <h3>判定理由 {source_chip('判定理由')}</h3>
            <ul class="compact-list">
              <li>上昇再開の証拠: {esc(recovery_evidence.get('grade', '-'))} / スコア {compact(recovery_evidence.get('score'))}</li>
              <li>騙し上昇の警戒: {esc(blocker_assessment.get('level', '-'))} / {esc(blocker_assessment.get('summary', '-'))}</li>
              <li>最終判断: {esc(_jp_action(str(action_decision.get('action', spot_signal.get('action', '-')))))} / mode {esc(action_decision.get('mode', '-'))}</li>
              {decision_rationale}
            </ul>
          </section>
          <section class="panel">
            <h3>危険ライン監視 {source_chip('危険ライン監視')}</h3>
            <div class="metrics" style="grid-template-columns:repeat(2,minmax(0,1fr));">
              {kv_card('段階', risk_lines.get('stage_label', '-'))}
              {kv_card('総合ストレス指数', compact(risk_lines.get('composite_risk_score')))}
              {kv_card('不足指標', ', '.join(risk_lines.get('missing_indicators', [])) or 'なし')}
              {kv_card('危険 / 非常に危険', f"{risk_lines.get('danger_count', 0)} / {risk_lines.get('extreme_count', 0)}")}
            </div>
            {risk_line_confidence_audit_html}
            {hindenburg_omen_panel}
            <ul class="compact-list">{risk_reason_items}</ul>
          </section>
        </div>
        <section class="panel mt">
          <h3>危険ライン詳細表</h3>
          <div class="table-wrap">{risk_line_table}</div>
        </section>
        {integrated_context_panel}
        {domestic_danger_panel}
        <div class="grid-3 mt">
          <section class="panel"><h3>投資候補 {source_chip('投資候補')}</h3><p>{esc(candidate.get('summary', '-'))}</p><ul class="compact-list"><li>判定: {esc(candidate.get('label', '候補なし'))}</li><li>候補ティッカー: {esc(candidate_tickers)}</li>{candidate_rationale}</ul></section>
          <section class="panel"><h3>先回り候補 {source_chip('先回り候補')}</h3><p>{esc(recovery.get('summary', '-'))}</p><ul class="compact-list"><li>判定: {esc(recovery.get('label', '候補なし'))}</li><li>候補ティッカー: {esc(recovery_tickers)}</li>{recovery_rationale}</ul></section>
          <section class="panel"><h3>レジーム先回り候補 {source_chip('レジーム先回り候補')}</h3><p>{esc(regime_leading.get('summary', '-'))}</p><ul class="compact-list"><li>判定: {esc(regime_leading.get('label', '候補なし'))}</li><li>候補ティッカー: {esc(regime_leading_tickers)}</li>{regime_leading_rationale}</ul></section>
        </div>
        {multi_asset_panel}
      </section>

      <section class="view view-sector">
        <div class="view-head"><div><h2>セクター</h2><p>12週騰落率の順位、ローテーション図、内部構造をまとめ、資金移動と裾野の広がりを確認します。</p></div>{source_chip('セクターローテーション / 内部構造')}</div>
        <div class="metrics">
          {kv_card('先導', sum(1 for row in sector_context.get('rows', []) if row.get('rotation_phase_ja') == '先導'))}
          {kv_card('改善', sum(1 for row in sector_context.get('rows', []) if row.get('rotation_phase_ja') == '改善'))}
          {kv_card('鈍化', sum(1 for row in sector_context.get('rows', []) if row.get('rotation_phase_ja') == '鈍化'))}
          {kv_card('出遅れ', sum(1 for row in sector_context.get('rows', []) if row.get('rotation_phase_ja') == '出遅れ'))}
          {kv_card('内部構造', sector_structure.get('structure_label', '-'))}
        </div>
        <div class="sector-layout">
          <section class="panel sector-chart"><h3>簡易ローテーション図 {source_chip('セクターローテーション')}</h3>{sector_svg}</section>
          <section class="panel"><h3>順位表</h3><div class="table-wrap">{sector_table}</div></section>
        </div>
        <section class="panel mt">
          <h3>セクターローテーション内部構造 {source_chip('セクターローテーション内部構造')}</h3>
          <p>{esc(sector_market_structure_comment)}</p>
          <div class="metrics" style="grid-template-columns:repeat(3,minmax(0,1fr));">{structure_metrics}</div>
          <ul class="compact-list">{sector_adjustment_items}</ul>
        </section>
      </section>

      <section class="view view-market">
        <div class="view-head"><div><h2>市場監視</h2><p>資産クラス、信用、インフレ、円建て影響、警告、類似局面を横断して確認します。</p></div>{source_chip('資産クラス比較 / 信用監視 / インフレ監視 / 円建て・為替リスク')}</div>
        <div class="metrics">
          {kv_card('資産比較', f"{len(report.get('asset_compare', []))}件")}
          {kv_card('信用監視', f"{len(report.get('credit_monitor', []))}系列")}
          {kv_card('インフレ監視', f"{len(report.get('inflation_monitor', []))}系列")}
          {kv_card('為替リスク', _jp_japan_risk_level(japan_risk.get('level')))}
          {kv_card('警告', f"{len(report.get('alerts', []))}件", tone='warn' if report.get('alerts') else '')}
        </div>
        <div class="grid-even">
          <section class="panel"><h3>資産クラス比較 {source_chip('資産クラス比較')}</h3><div class="table-wrap">{asset_table}</div></section>
          <section class="panel"><h3>信用監視 {source_chip('信用監視')}</h3><div class="table-wrap">{credit_table}</div></section>
          <section class="panel"><h3>インフレ監視 {source_chip('インフレ監視')}</h3><div class="table-wrap">{inflation_table}</div></section>
          <section class="panel"><h3>警告レイヤー {source_chip('警告レイヤー')}</h3>{alert_cards}</section>
        </div>
        <section class="panel mt"><h3>円建て・為替リスク {source_chip('円建て・為替リスク')}</h3><p>{esc(japan_risk.get('summary', '-'))}</p><div class="table-wrap">{fx_table}</div><div class="table-wrap mt">{yen_asset_table}</div></section>
        {integrated_context_panel}
        {domestic_danger_panel}
        <section class="panel mt"><h3>類似局面 {source_chip('類似局面')}</h3><div class="table-wrap">{analogue_table}</div></section>
      </section>

      <section class="view view-audit">
        <div class="view-head"><div><h2>監査</h2><p>しきい値、データ取得状況、接続診断、最終警告を後から追えるようにまとめます。</p></div>{source_chip('データ取得状況 / 接続診断 / 警告')}</div>
        <div class="metrics">
          {kv_card('しきい値バージョン', report.get('risk_thresholds', {}).get('version', '-'))}
          {kv_card('校正日時', report.get('risk_thresholds', {}).get('generated_at', '-'))}
          {kv_card('レビュー状態', f"{_jp_threshold_status(threshold_review.get('status', '-'))} / 推奨={_display_bool(threshold_review.get('review_recommended', False))}", tone='warn' if threshold_review.get('review_recommended') else '')}
          {kv_card('メンテナンス', f"{_localize_display_text(threshold_maintenance.get('status', '-'))} / {number(threshold_maintenance.get('elapsed_seconds'))}秒")}
          {kv_card('提案生成', _display_bool(threshold_maintenance.get('proposal_generated_this_run', False)))}
        </div>
        <div class="grid-2">
          <section class="panel"><h3>しきい値ドリフト {source_chip('判定の読み方')}</h3><div class="metrics" style="grid-template-columns:repeat(4,minmax(0,1fr));">{kv_card('安定', drift_summary.get('stable_count', 0))}{kv_card('監視', drift_summary.get('watch_count', 0), tone='warn')}{kv_card('要確認', drift_summary.get('review_count', 0), tone='danger')}{kv_card('未取得', drift_summary.get('unavailable_count', 0))}</div><div class="audit-targets">{"".join(f"<span>{esc(item)}</span>" for item in drift_summary.get('review_targets', [])) or "<span>レビュー対象なし</span>"}</div><ul class="compact-list mt"><li>レビュー理由: {esc(', '.join(threshold_review.get('reasons', [])) or '-')}</li></ul></section>
          <section class="panel"><h3>接続診断 {source_chip('接続診断')}</h3><div class="table-wrap">{diagnostic_table}</div><h3 class="mt">代表エラー</h3><ul class="compact-list">{diagnostic_errors}</ul></section>
        </div>
        <section class="panel mt"><h3>データ取得状況 {source_chip('データ取得状況')}</h3><div class="table-wrap">{availability_table}</div></section>
        <section class="panel mt"><h3>警告 {source_chip('警告')}</h3><ul class="compact-list">{warning_items}</ul></section>
      </section>
    </main>
  </div>
  <script id="supplementHistoryPayload" type="application/json">{history_payload_json}</script>
  <script>
  (() => {{
    const tabMap = {{ '#history': 'tab-history', '#decision': 'tab-decision', '#sector': 'tab-sector', '#market': 'tab-market', '#audit': 'tab-audit' }};
    const activateFromHash = () => {{
      const id = tabMap[window.location.hash] || 'tab-history';
      const input = document.getElementById(id);
      if (input) input.checked = true;
    }};
    activateFromHash();
    window.addEventListener('hashchange', activateFromHash);
    Object.entries(tabMap).forEach(([hash, id]) => {{
      const label = document.querySelector(`label[for="${{id}}"]`);
      if (label) label.addEventListener('click', () => {{
        if (window.location.hash !== hash) history.replaceState(null, '', hash);
      }});
    }});
  }})();
  (() => {{
    const payload = JSON.parse(document.getElementById('supplementHistoryPayload').textContent || '{{}}');
    const entries = payload.history || [];
    const meta = payload.meta || {{ history_count: entries.length, daily_latest_count: entries.length }};
    const svg = document.getElementById('supplementHistoryChart');
    const range = document.getElementById('supplementHistoryRange');
    const count = document.getElementById('supplementHistoryCount');
    const ts = document.getElementById('supplementHistoryTimestamp');
    const score = document.getElementById('supplementHistoryScore');
    const regime = document.getElementById('supplementHistoryRegime');
    const colors = {{ risk_on:'#0f766e', transition:'#d97706', risk_off:'#dc2626', credit_stress:'#7c2d12', inflation_shock:'#b45309', early_recovery:'#2563eb', data_unavailable:'#98a2b3' }};
    const fmt = value => String(value || '履歴なし').replace('T', ' ').slice(0, 16);
    if (!entries.length) {{
      svg.innerHTML = '<text x="490" y="180" text-anchor="middle" fill="#667085" font-size="18">履歴データなし</text>';
      count.value = '0件';
      return;
    }}
    range.max = String(entries.length - 1);
    function redraw(index) {{
      const width = 980, height = 360, left = 54, right = 24, top = 24, bottom = 46;
      const plotW = width - left - right, plotH = height - top - bottom;
      const scores = entries.map(item => Number(item.score)).filter(Number.isFinite);
      const min = Math.min(...scores, 0.45), max = Math.max(...scores, 0.70);
      const span = Math.max(max - min, 0.001);
      const x = i => left + (entries.length === 1 ? 0 : (i / (entries.length - 1)) * plotW);
      const y = v => top + (1 - ((Number(v) - min) / span)) * plotH;
      const bg = entries.map((item, i) => `<rect x="${{x(i).toFixed(1)}}" y="${{top}}" width="${{Math.max(plotW / entries.length, 2).toFixed(1)}}" height="${{plotH}}" fill="${{colors[item.regime?.key] || '#98a2b3'}}" opacity=".08"></rect>`).join('');
      const grid = [0, .25, .5, .75, 1].map(t => `<line x1="${{left}}" x2="${{width-right}}" y1="${{(top+t*plotH).toFixed(1)}}" y2="${{(top+t*plotH).toFixed(1)}}" stroke="#e5eaf0"></line>`).join('');
      const points = entries.map((item, i) => `${{x(i).toFixed(1)}},${{y(item.score).toFixed(1)}}`).join(' ');
      const dots = entries.map((item, i) => `<circle cx="${{x(i).toFixed(1)}}" cy="${{y(item.score).toFixed(1)}}" r="${{i === index ? 5 : 2.8}}" fill="${{colors[item.regime?.key] || '#0f766e'}}" stroke="#fff"></circle>`).join('');
      const selected = entries[index] || entries[entries.length - 1];
      ts.innerHTML = fmt(selected.generated_at);
      score.innerHTML = selected.score ?? '-';
      regime.innerHTML = selected.regime?.label || '-';
      count.value = `${{entries.length}}件の履歴 / daily_latest ${{meta.daily_latest_count || entries.length}}件`;
      svg.innerHTML = `${{bg}}${{grid}}<polyline points="${{points}}" fill="none" stroke="#0f766e" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>${{dots}}<text x="${{left}}" y="${{height-12}}" fill="#667085" font-size="12">${{fmt(entries[0].generated_at)}}</text><text x="${{width-right}}" y="${{height-12}}" text-anchor="end" fill="#667085" font-size="12">${{fmt(entries[entries.length-1].generated_at)}}</text>`;
    }}
    range.addEventListener('input', () => redraw(Number(range.value)));
    range.value = String(entries.length - 1);
    redraw(entries.length - 1);
  }})();
  </script>
</body>
</html>"""


def render_html(report: dict[str, Any], history_entries: list[dict[str, Any]] | None = None) -> str:
    regime_label = _jp_regime(report["regime"]["regime_label"])
    cycle_label = _jp_cycle(report["cycle"]["phase_label"])
    action_label = _jp_action(report["spot_signal"].get("action_decision", {}).get("action", report["spot_signal"]["action"]))
    legacy_action_label = _jp_action(report["spot_signal"].get("legacy_action", report["spot_signal"].get("action", "")))
    risk_label = _jp_risk(report["spot_signal"]["second_leg_risk"])
    recovery_evidence = report.get("spot_signal", {}).get("recovery_evidence", {})
    blocker_assessment = report.get("spot_signal", {}).get("blocker_assessment", {})
    action_decision = report.get("spot_signal", {}).get("action_decision", {})
    recovery_grade = str(recovery_evidence.get("grade", "-"))
    recovery_score = _display_compact_number(recovery_evidence.get("score"))
    blocker_level = str(blocker_assessment.get("level", "-"))
    decision_action = _jp_action(str(action_decision.get("action", report["spot_signal"].get("action", ""))))
    internal_warning_count = len(report.get("warnings", []))
    sector_context = _build_sector_rotation_context(report.get("sector_rotation", {}))
    risk_lines = report.get("risk_lines", {})
    threshold_drift = report.get("risk_threshold_drift") or {}
    drift_summary = threshold_drift.get("summary") or {}
    threshold_review = report.get("risk_threshold_review") or {}
    threshold_maintenance = report.get("risk_threshold_maintenance") or {}
    candidate = report.get("investment_candidates", {})
    recovery = report.get("recovery_candidates", {})
    regime_leading = report.get("regime_leading_candidates", {})
    japan_risk = report.get("japan_risk", {})
    hero_summary_copy = _build_hero_summary_copy(report, risk_lines, decision_action)
    primary_reason_lines = _build_primary_reason_lines(report)
    recovery_grade_label = _localize_signal_value(recovery_grade)
    blocker_level_label = _localize_signal_value(blocker_level)
    threshold_status_label = _jp_threshold_status(threshold_review.get("status", "-"))
    drift_labels = {
        "stable": "安定",
        "watch": "監視",
        "review": "要確認",
        "unavailable": "未取得",
    }
    drift_review_targets = ", ".join(_jp_review_target(item) for item in drift_summary.get("review_targets", [])) or "-"
    score_ratio = _score_ratio(report["score"].get("total_score"))
    score_degrees = 180 * score_ratio
    risk_highlights = _build_risk_highlight_rows(report)
    risk_highlight_rows = (
        "".join(_risk_track_row_html(row) for row in risk_highlights) or "<div class='risk-track-empty'>主要指標データなし</div>"
    )
    sector_overview_rows = _build_sector_overview_rows(sector_context)
    sector_max_abs = max([abs(float(row.get("return_12w", 0.0) or 0.0)) for row in sector_overview_rows] + [1.0])
    sector_overview_html = (
        "".join(
            "<div class='sector-overview-row'>"
            f"<div class='sector-overview-tone {'positive' if float(row.get('return_12w', 0.0) or 0.0) >= 0 else 'negative'}'>{'強い' if float(row.get('return_12w', 0.0) or 0.0) >= 0 else '弱い'}</div>"
            f"<div class='sector-overview-name'>{html.escape(str(row.get('sector_name_ja', '-')))}</div>"
            f"<div class='sector-overview-bar'><span class='sector-overview-fill {'positive' if float(row.get('return_12w', 0.0) or 0.0) >= 0 else 'negative'}' style='width:{_sector_bar_width(row.get('return_12w'), sector_max_abs) * 0.5:.1f}%'></span></div>"
            f"<div class='sector-overview-value {'positive' if float(row.get('return_12w', 0.0) or 0.0) >= 0 else 'negative'}'>{float(row.get('return_12w', 0.0) or 0.0):+.2f}</div>"
            "</div>"
            for row in sector_overview_rows
        )
        or "<div class='sector-overview-empty'>セクター概要データなし</div>"
    )
    history_payload = _build_history_embed_payload(history_entries or [])
    history_payload_json = json.dumps(history_payload, ensure_ascii=False).replace("</", "<\\/")
    approved_report_dashboard_html = _approved_report_dashboard_html(report)
    supplemental_signal_strip_html = _supplemental_signal_strip_html(report)
    risk_context_ux_hub_html = _risk_context_ux_hub_html(report)
    provenance_strip_html = _top_provenance_strip_html(report)

    warning_items = "".join(f"<li>{html.escape(warning)}</li>" for warning in report["warnings"]) or "<li>重要な警告はありません。</li>"
    sector_rows = (
        "".join(
            "<tr>"
            f"<td>{html.escape(row['ticker'])}</td>"
            f"<td>{html.escape(row['sector_name_ja'])}{_sector_label_badge_html(row.get('candidate_label'))}</td>"
            f"<td>{row['return_12w']}</td>"
            f"<td>{row['rank']}</td>"
            f"<td>{html.escape(row['rotation_phase_ja'])}</td>"
            "</tr>"
            for row in sector_context["rows"]
        )
        or "<tr><td colspan='5'>有効データなし</td></tr>"
    )
    asset_rows = (
        "".join(
            "<tr>"
            f"<td>{html.escape(row['asset_class'])}</td>"
            f"<td>{html.escape(row['ticker'])}<br><span style='color:#52606d;font-size:12px'>{html.escape(row['ticker_name_ja'])}</span></td>"
            f"<td>{row['momentum_12w']}</td>"
            f"<td>{row['annualized_volatility']}</td>"
            f"<td>{row['max_drawdown']}</td>"
            "</tr>"
            for row in report["asset_compare"]
        )
        or "<tr><td colspan='5'>有効データなし</td></tr>"
    )
    credit_rows = (
        "".join(
            "<tr>"
            f"<td>{html.escape(row['ticker'])}<br><span style='color:#52606d;font-size:12px'>{html.escape(row['ticker_name_ja'])}</span></td>"
            f"<td>{row['current']}</td>"
            f"<td>{row['change_1w']}</td>"
            f"<td>{row['change_4w']}</td>"
            f"<td>{row['change_12w']}</td>"
            f"<td>{row['zscore']}</td>"
            f"<td>{html.escape(row['signal_label'])}</td>"
            "</tr>"
            for row in report.get("credit_monitor", [])
        )
        or "<tr><td colspan='7'>有効データなし</td></tr>"
    )
    risk_stage_badge_html = _risk_badge_html(risk_lines.get("stage_label", "-"), _risk_stage_tone(risk_lines.get("stage_key")))
    risk_line_confidence_audit_html = _risk_line_confidence_audit_html(report.get("risk_line_confidence_audit") or {})

    inflation_rows = (
        "".join(
            "<tr>"
            f"<td>{html.escape(row['ticker'])}<br><span style='color:#52606d;font-size:12px'>{html.escape(row['ticker_name_ja'])}</span></td>"
            f"<td>{row['current']}</td>"
            f"<td>{row['change_1w']}</td>"
            f"<td>{row['change_4w']}</td>"
            f"<td>{row['change_12w']}</td>"
            f"<td>{row['zscore']}</td>"
            f"<td>{html.escape(row['signal_label'])}</td>"
            "</tr>"
            for row in report.get("inflation_monitor", [])
        )
        or "<tr><td colspan='7'>有効データなし</td></tr>"
    )
    usd_jpy = japan_risk.get("usd_jpy", {})
    japan_fx_rows = ""
    if usd_jpy:
        japan_fx_rows = (
            "<tr>"
            f"<td>{html.escape(str(usd_jpy.get('ticker', 'USDJPY=X')))}<br><span style='color:#52606d;font-size:12px'>{html.escape(str(usd_jpy.get('ticker_name_ja', '米ドル円')))}</span></td>"
            f"<td>{html.escape(_display_number(usd_jpy.get('current')))}</td>"
            f"<td>{html.escape(_display_number(usd_jpy.get('change_1w')))}</td>"
            f"<td>{html.escape(_display_number(usd_jpy.get('change_4w')))}</td>"
            f"<td>{html.escape(_display_number(usd_jpy.get('change_12w')))}</td>"
            f"<td>{html.escape(_display_number(usd_jpy.get('zscore')))}</td>"
            f"<td>{html.escape(str(usd_jpy.get('signal_label', '-')))}</td>"
            "</tr>"
        )
    japan_fx_rows = japan_fx_rows or "<tr><td colspan='7'>有効データなし</td></tr>"
    japan_asset_rows = (
        "".join(
            "<tr>"
            f"<td>{html.escape(str(row.get('asset_class', '-')))}</td>"
            f"<td>{html.escape(str(row.get('ticker', '-')))}<br><span style='color:#52606d;font-size:12px'>{html.escape(str(row.get('ticker_name_ja', '-')))}</span></td>"
            f"<td>{html.escape(str(row.get('usd_return_4w', '-')))}</td>"
            f"<td>{html.escape(str(row.get('jpy_return_4w', '-')))}</td>"
            f"<td>{html.escape(str(row.get('fx_contribution_4w', '-')))}</td>"
            f"<td>{html.escape(str(row.get('jpy_max_drawdown', '-')))}</td>"
            f"<td>{html.escape(str(row.get('signal_label', '-')))}</td>"
            "</tr>"
            for row in japan_risk.get("foreign_assets", [])
        )
        or "<tr><td colspan='7'>有効データなし</td></tr>"
    )
    risk_line_rows = (
        "".join(
            "<tr>"
            f"<td>{html.escape(str(row.get('ticker_name_ja', row.get('ticker', '-'))))}<br><span style='color:#52606d;font-size:12px'>{html.escape(str(row.get('ticker', '-')))}</span></td>"
            f"<td>{_risk_badge_html(row.get('line_level_label', '-'), _risk_label_tone(row.get('line_level_label')))}</td>"
            f"<td>{_display_number(row.get('current'))}</td>"
            f"<td>{_format_risk_threshold_html(row.get('warning_line'))}</td>"
            f"<td>{_format_risk_threshold_html(row.get('danger_line'))}</td>"
            f"<td>{_format_risk_threshold_html(row.get('extreme_line'))}</td>"
            f"<td>{html.escape(_risk_accepted_rule_summary(row))}</td>"
            f"<td>{html.escape(_risk_diagnostic_rule_summary(row))}</td>"
            "</tr>"
            for row in risk_lines.get("indicators", [])
        )
        or "<tr><td colspan='8'>有効データなし</td></tr>"
    )
    risk_line_reason_items = (
        "".join(f"<li>{html.escape(str(reason))}</li>" for reason in risk_lines.get("reasons", [])) or "<li>追加理由はありません。</li>"
    )
    alert_items = (
        "".join(
            "<li>"
            f"<strong>{html.escape(alert.get('title', '-'))}</strong>"
            f" <span class='pill'>{html.escape(_alert_category_label(alert.get('category', 'memo')))} / {html.escape(_alert_severity_label(alert.get('severity', 'low')))}</span>"
            f"<br><span style='color:#52606d'>{html.escape(alert.get('message', '-'))}</span>"
            "</li>"
            for alert in report.get("alerts", [])
        )
        or "<li>現時点で追加の警告はありません。</li>"
    )
    candidate_items = (
        "".join(f"<li>{html.escape(_localize_display_text(reason))}</li>" for reason in candidate.get("rationale", []))
        or "<li>候補提示の条件がまだ揃っていません。</li>"
    )
    candidate_asset = candidate.get("preferred_asset_class")
    candidate_sector = candidate.get("preferred_sector")
    candidate_tickers = (
        ", ".join(f"{item.get('ticker', '-')}({item.get('label', '-')})" for item in candidate.get("candidate_tickers", [])) or "なし"
    )
    recovery_items = (
        "".join(f"<li>{html.escape(_localize_display_text(reason))}</li>" for reason in recovery.get("rationale", []))
        or "<li>先回り候補の条件はまだ揃っていません。</li>"
    )
    recovery_asset = recovery.get("preferred_asset_class")
    recovery_sector = recovery.get("preferred_sector")
    recovery_tickers = (
        ", ".join(f"{item.get('ticker', '-')}({item.get('label', '-')})" for item in recovery.get("candidate_tickers", [])) or "なし"
    )
    regime_leading_items = (
        "".join(f"<li>{html.escape(_localize_display_text(reason))}</li>" for reason in regime_leading.get("rationale", []))
        or "<li>レジーム先回り候補の条件はまだ揃っていません。</li>"
    )
    regime_leading_sector = regime_leading.get("preferred_sector")
    regime_leading_region = regime_leading.get("preferred_region")
    regime_leading_asset = regime_leading.get("preferred_asset_class")
    regime_leading_tickers = (
        ", ".join(
            f"{item.get('ticker', '-')}({item.get('label', '-')}: {item.get('reason', '-')})"
            for item in regime_leading.get("candidate_tickers", [])
        )
        or "なし"
    )
    analogue_rows = (
        "".join(
            "<tr>" f"<td>{row['end_date']}</td><td>{row['similarity']}</td><td>{row['forward_12w_return']}</td>" "</tr>"
            for row in report["analogues"]
        )
        or "<tr><td colspan='3'>十分に近い類似局面は抽出されませんでした。</td></tr>"
    )
    availability_rows = (
        "".join(
            "<tr>"
            f"<td>{html.escape(entry['requested_ticker'])}<br><span style='color:#52606d;font-size:12px'>{html.escape(entry.get('requested_ticker_name_ja', entry['requested_ticker']))}</span></td>"
            f"<td>{html.escape(STATUS_LABELS.get(entry['status'], entry['status']))}</td>"
            f"<td>{html.escape(entry.get('used_ticker') or '-')}<br><span style='color:#52606d;font-size:12px'>{html.escape(entry.get('used_ticker_name_ja') or '-')}</span></td>"
            f"<td>{html.escape(', '.join(f'{ticker}({name})' for ticker, name in zip(entry.get('alternatives', []), entry.get('alternatives_name_ja', []), strict=False)) if entry.get('alternatives') else 'なし')}</td>"
            f"<td>{html.escape(entry['message'])}</td>"
            "</tr>"
            for entry in report.get("data_availability", [])
        )
        or "<tr><td colspan='5'>取得状況データなし</td></tr>"
    )
    diagnostics = report.get("fetch_diagnostics", {})
    runtime_context = report.get("runtime_context", {})
    summary = diagnostics.get("summary", {})
    diagnostic_rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{html.escape(value)}</td></tr>"
        for label, value in [
            ("実行形態", "配布 exe" if runtime_context.get("is_frozen") else "Python 実行"),
            ("実行ファイル", runtime_context.get("python_executable", "-")),
            ("作業フォルダ", runtime_context.get("working_directory", "-")),
            ("取得ソース", str(summary.get("source", report.get("data_source", "-")))),
            *_execution_mode_html_rows(report),
            *_data_quality_html_rows(report),
            ("失敗試行数", str(summary.get("failed_attempt_count", 0))),
            ("接続不良疑い", "あり" if summary.get("suspected_network_issue") else "なし"),
            ("接続先候補ホスト", ", ".join(diagnostics.get("suspected_hosts", [])) or "記録なし"),
        ]
    )
    diagnostic_error_items = (
        "".join(f"<li>{html.escape(item)}</li>" for item in diagnostics.get("failure_samples", []))
        or "<li>代表エラーは記録されていません。</li>"
    )
    sector_payload = report.get("sector_rotation", {})
    sector_structure = sector_payload.get("internal_structure") or report.get("internal_structure", {})
    sector_next_candidates = sector_payload.get("next_candidates") or report.get("next_candidates", [])
    sector_peakout_sectors = sector_payload.get("peakout_sectors") or report.get("peakout_sectors", [])
    sector_market_structure_comment = sector_payload.get("market_structure_comment") or report.get("market_structure_comment", "-")
    sector_svg = _render_sector_rotation_svg(sector_payload, sector_context)
    sector_adjustment_items = "".join(
        f"<li>{html.escape(line.lstrip('- ').strip())}</li>" for line in _sector_adjustment_summary_lines(report)
    )

    html_output = f"""<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\">
  <title>{html.escape(report['title'])}</title>
  <style>
    :root {{
      --bg: #eef3f8;
      --panel: rgba(255,255,255,0.94);
      --ink: #102033;
      --muted: #5d6b7c;
      --line: #d9e2ec;
      --accent: #2563eb;
      --accent-soft: rgba(37,99,235,0.10);
      --ok: #2f855a;
      --warn: #b7791f;
      --bad: #c53030;
      --danger: #c05621;
      --caution: #b7791f;
    }}
    body {{ font-family: 'Yu Gothic UI', 'Hiragino Sans', sans-serif; margin: 0; background: linear-gradient(180deg, #fbfdff 0%, #eef4fb 100%); color: var(--ink); }}
    .wrap {{ max-width: 1640px; margin: 0 auto; padding: 16px 16px 30px; }}
    .hero {{ background: var(--panel); border: 1px solid var(--line); border-radius: 24px; padding: 22px 24px; box-shadow: none; }}
    .hero-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; }}
    .hero-title {{ min-width: 0; flex: 1; }}
    .hero-link-card {{ width: min(220px, 100%); padding: 12px 14px; border-radius: 16px; border: 1px solid var(--line); background: rgba(255,255,255,0.72); }}
    .hero-link-card .k {{ font-size: 11px; color: var(--muted); font-weight: 700; letter-spacing: .03em; }}
    .hero-link-card .v {{ margin-top: 4px; font-size: 15px; font-weight: 800; line-height: 1.35; color: var(--ink); }}
    .hero h1 {{ margin: 0; font-size: 34px; line-height: 1.12; }}
    .hero-copy {{ margin: 10px 0 0; max-width: 76ch; color: var(--muted); line-height: 1.7; }}
    .meta {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; color: var(--muted); font-size: 14px; margin-top: 14px; }}
    .meta > span {{ display: inline-flex; align-items: center; gap: 6px; line-height: 1.2; }}
    .grid {{ display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(260px, 1fr); gap: 14px; margin-top: 18px; }}
    .summary-panel {{ background: rgba(255,255,255,0.78); border: 1px solid var(--line); border-radius: 18px; padding: 18px; }}
    .summary-head {{ display: grid; gap: 6px; }}
    .summary-head h2 {{ margin: 0; font-size: 14px; color: var(--muted); }}
    .summary-main {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(220px, 0.8fr); gap: 14px; align-items: start; margin-top: 10px; }}
    .summary-value {{ font-size: clamp(30px, 4vw, 42px); font-weight: 800; line-height: 1.08; color: #102a43; }}
    .summary-copy {{ margin-top: 8px; font-size: 14px; color: var(--muted); line-height: 1.65; max-width: 30ch; }}
    .summary-side {{ padding: 12px 14px; border-radius: 16px; border: 1px solid rgba(125,145,166,0.16); background: rgba(255,255,255,0.68); }}
    .summary-side .k {{ font-size: 12px; color: var(--muted); font-weight: 700; }}
    .summary-side .v {{ margin-top: 4px; font-size: 34px; font-weight: 800; line-height: 1.08; color: #102a43; }}
    .summary-metrics {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }}
    .mini-metric {{ padding-top: 10px; border-top: 1px solid rgba(125,145,166,0.18); }}
    .mini-metric .k {{ font-size: 12px; color: var(--muted); font-weight: 700; }}
    .mini-metric .v {{ margin-top: 4px; font-size: 24px; font-weight: 800; line-height: 1.12; color: #243b53; }}
    .side-grid {{ display: grid; gap: 10px; }}
    .card {{ background: rgba(255,255,255,0.78); border: 1px solid var(--line); border-radius: 16px; padding: 16px; }}
    .card h2 {{ margin: 0 0 8px; font-size: 13px; color: var(--muted); }}
    .value {{ font-size: 26px; font-weight: 700; color: #102a43; }}
    .explain {{ margin-top: 8px; font-size: 14px; color: var(--muted); }}
    .section {{ margin-top: 18px; background: rgba(255,255,255,0.82); border: 1px solid var(--line); border-radius: 18px; padding: 20px 22px; }}
    .section h2 {{ margin: 0 0 8px; font-size: 22px; }}
    .section p {{ margin: 0 0 16px; color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 13px; }}
    .pill {{ display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; background: var(--accent-soft); color: #1d4ed8; font-size: 13px; line-height: 1; }}
    .risk-badge {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 13px; font-weight: 800; }}
    .risk-badge.caution {{ background: rgba(183,121,31,0.12); color: var(--caution); }}
    .risk-badge.danger {{ background: rgba(192,86,33,0.14); color: var(--danger); }}
    .risk-badge.extreme {{ background: rgba(197,48,48,0.14); color: var(--bad); }}
    .inline-note {{ margin-top: 8px; max-width: 44ch; font-size: 12px; color: var(--muted); line-height: 1.55; }}
    .sector-visual {{ display: grid; grid-template-columns: 1fr; gap: 0; align-items: start; }}
    .sector-top {{ display: grid; grid-template-columns: minmax(0, 720px) minmax(420px, 1fr); gap: 10px; align-items: start; }}
    .sector-visual > h3 {{ margin: 0 0 4px; }}
    .sector-chart {{ min-width: 0; }}
    .sector-chart svg {{ width: min(100%, 640px); height: auto; display: block; }}
    .sector-guide {{ margin-top: 68px; padding: 14px 16px; border: 1px solid var(--line); border-radius: 16px; background: rgba(255,255,255,0.72); }}
    .sector-guide h4 {{ margin: 0 0 8px; font-size: 14px; color: #243b53; }}
    .guide-key {{ font-weight: 700; color: #243b53; }}
    .sector-table {{ width: 100%; }}
    .sector-caption {{ font-size: 13px; color: var(--muted); }}
    .sector-label-badge {{ display: inline-block; margin-top: 4px; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; background: rgba(16,32,51,0.08); color: #1f2933; }}
    .topbar {{ display:grid; grid-template-columns:minmax(420px,.85fr) minmax(0,1.4fr); grid-template-rows:auto auto; align-items:center; gap:12px 24px; padding:12px 16px 14px; margin-bottom:14px; background:rgba(255,255,255,.82); border-bottom:1px solid #d9e2ec; border-radius:0; }}
    .brand {{ grid-column:1; grid-row:1; display:flex; align-items:center; justify-content:flex-start; gap:16px; min-width:0; align-self:center; }}
    .brand-mark {{ width:48px; height:48px; border-radius:999px; background:#fff; color:#17366d; display:grid; place-items:center; font-size:35px; font-weight:900; border:0; }}
    .brand-title {{ display:flex; align-items:center; gap:0; min-width:0; }}
    .brand-title h1 {{ margin:0; font-size:clamp(28px,2.6vw,38px); line-height:1.08; color:#0a1530; white-space:nowrap; letter-spacing:-.02em; }}
    .status-strip {{ grid-column:1; grid-row:2; display:grid; grid-template-columns:minmax(190px,1.45fr) minmax(110px,.8fr) minmax(80px,.6fr); gap:0; justify-content:start; }}
    .status-box {{ min-width:150px; padding-left:18px; border-left:1px solid var(--line); }}
    .status-box:first-child {{ border-left:0; padding-left:0; }}
    .status-box .k {{ font-size:12px; color:var(--muted); font-weight:700; }}
    .status-box .v {{ margin-top:4px; font-size:13px; font-weight:800; color:#1f3b67; white-space:nowrap; }}
    .monitor-note {{ grid-column:2; grid-row:1; justify-self:end; align-self:center; color:#1f2933; font-size:13px; line-height:1.55; text-align:right; max-width:460px; font-weight:800; line-break:strict; }}
    .monitor-note-segment {{ display:inline-block; white-space:nowrap; }}
    .dashboard-grid {{ display:flex; gap:16px; align-items:stretch; margin-bottom:32px; flex-wrap:wrap; }}
    .approved-report-dashboard {{ display:grid; grid-template-columns:minmax(0,1.9fr) minmax(330px,.72fr); gap:18px; margin-bottom:18px; align-items:start; }}
    .main-dashboard-shell {{ min-height:0; }}
    .main-report-left {{ display:grid; grid-template-rows:auto auto 1fr; gap:10px; min-width:0; }}
    .main-report-context-stack {{ display:grid; gap:8px; min-width:0; }}
    .visual-first-read, .supplemental-signal-strip, .first-read-card, .context-card, .supplement-link-card {{ border:1px solid #d7e0ea; border-radius:14px; background:rgba(255,255,255,.97); box-shadow:none; }}
    .visual-first-read {{ padding:20px 22px 22px; }}
    .section-title-row {{ display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:12px; }}
    .section-title-row h2 {{ margin:4px 0 0; color:#102a55; font-size:clamp(25px,2vw,32px); line-height:1.15; font-weight:900; letter-spacing:-.02em; }}
    .section-eyebrow, .term-note, .context-eyebrow {{ display:block; color:#66788e; font-size:12px; line-height:1.2; font-weight:900; letter-spacing:.06em; }}
    .reading-guide {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:0; margin:0 0 18px; padding:0; list-style:none; border-block:1px solid #dbe4ee; }}
    .reading-guide li {{ position:relative; display:flex; align-items:center; gap:10px; min-height:64px; padding:10px 16px; }}
    .reading-guide li + li {{ border-left:1px solid #dbe4ee; }}
    .reading-guide b {{ display:grid; place-items:center; width:28px; height:28px; flex:0 0 auto; border-radius:999px; background:#e8f0fb; color:#173f7a; font-size:14px; }}
    .reading-guide strong, .reading-guide small {{ display:block; }}
    .reading-guide strong {{ color:#17366d; font-size:15px; }}
    .reading-guide small {{ margin-top:2px; color:#66737f; font-size:12px; }}
    .section-chip {{ display:inline-flex; align-items:center; min-height:26px; padding:0 10px; border-radius:999px; border:1px solid #c7d7eb; background:#f6f9fd; color:#23406f; font-size:12px; font-weight:900; white-space:nowrap; }}
    .decision-summary-grid {{ display:grid; grid-template-columns:minmax(340px,1.05fr) minmax(340px,.95fr); gap:18px; align-items:stretch; }}
    .decision-hero-card {{ display:grid; grid-template-columns:118px minmax(0,1fr); gap:22px; align-items:center; min-height:142px; padding:20px 26px; border-radius:10px; background:linear-gradient(135deg,#102a55,#173f7a); color:#fff; box-shadow:inset 0 0 0 1px rgba(255,255,255,.12); }}
    .decision-hero-icon {{ width:92px; height:92px; border-radius:999px; display:grid; place-items:center; border:4px solid rgba(130,181,240,.72); color:#d6e7ff; font-size:54px; font-weight:900; }}
    .decision-hero-label {{ margin-top:10px; padding-top:10px; border-top:1px dashed rgba(255,255,255,.7); color:#d8e6fa; font-size:15px; font-weight:900; }}
    .decision-hero-card strong {{ display:block; margin-top:0; font-size:clamp(38px,3.4vw,52px); line-height:1; letter-spacing:-.02em; }}
    .decision-hero-card p {{ margin:8px 0 0; color:#edf5ff; font-size:15px; line-height:1.5; }}
    .readiness-summary-card {{ min-height:142px; padding:18px 20px 14px; border:1px solid #b7c6d8; border-radius:10px; background:#fff; }}
    .score-row {{ display:flex; align-items:baseline; justify-content:space-between; gap:12px; color:#17366d; font-weight:900; }}
    .score-row span {{ font-size:17px; }}
    .score-row span em {{ display:inline-grid; place-items:center; width:18px; height:18px; margin-left:4px; border:1px solid #9aa8b6; border-radius:999px; color:#6b7785; font-style:normal; font-size:12px; }}
    .score-row strong {{ color:#17366d; font-size:46px; line-height:1; }}
    .score-row small {{ margin-left:4px; color:#111922; font-size:28px; font-weight:800; }}
    .readiness-state {{ margin-top:6px; color:#17366d; font-size:15px; font-weight:900; }}
    .readiness-bars {{ position:relative; height:18px; margin:22px 0 4px; border-radius:7px; background:repeating-linear-gradient(90deg,#e6ebf1 0 42px,#fff 42px 44px); overflow:hidden; }}
    .readiness-bars::before {{ content:''; position:absolute; inset:0 auto 0 0; width:calc(var(--score) * 1%); border-radius:999px; background:repeating-linear-gradient(90deg,#173f7a 0 39px,#2f5f9f 39px 41px); }}
    .readiness-scale {{ display:grid; grid-template-columns:repeat(5,1fr); color:#0f1c2e; font-size:13px; font-weight:800; }}
    .readiness-scale span:nth-child(2), .readiness-scale span:nth-child(3), .readiness-scale span:nth-child(4) {{ text-align:center; }}
    .readiness-scale span:last-child {{ text-align:right; }}
    .readiness-summary-card p {{ margin:6px 0 0; color:#52606d; font-size:12px; line-height:1.35; }}
    .main-reason-grid {{ display:grid; grid-template-columns:minmax(0,1.15fr) minmax(0,.9fr) minmax(0,.95fr); gap:12px; margin-top:18px; }}
    .reason-heading {{ margin:13px 0 0; color:#17366d; font-size:17px; }}
    .first-read-card {{ padding:16px 18px; min-width:0; }}
    .first-read-card h3 {{ display:flex; align-items:center; gap:9px; margin:5px 0 12px; color:#17366d; font-size:20px; line-height:1.35; }}
    .first-read-card h3 b {{ display:grid; place-items:center; width:26px; height:26px; flex:0 0 auto; border-radius:999px; background:#edf3fb; color:#173f7a; font-size:13px; }}
    .first-read-card ul {{ margin:0; padding-left:19px; color:#1f2933; line-height:1.72; font-size:15px; }}
    .first-read-card li + li {{ margin-top:4px; }}
    .first-read-card small {{ display:block; margin-top:10px; color:#66737f; line-height:1.45; }}
    .first-read-card.positive h3 {{ color:#16724f; }}
    .first-read-card.positive li::marker {{ color:#16724f; }}
    .first-read-card.negative h3 {{ color:#a7342e; }}
    .first-read-card.negative li::marker {{ color:#b43d35; }}
    .supplemental-signal-strip {{ padding:12px 16px; }}
    .signal-strip-grid {{ display:grid; grid-template-columns:repeat(8,minmax(0,1fr)); gap:8px; }}
    .signal-pill {{ min-height:78px; padding:8px; border:1px solid #d8e2ef; border-radius:10px; background:#fff; display:flex; flex-direction:column; justify-content:center; gap:4px; text-align:center; min-width:0; }}
    .signal-icon {{ font-size:21px; line-height:1; color:#4b5563; }}
    .signal-pill span {{ color:#52606d; font-size:12px; font-weight:800; }}
    .signal-pill strong {{ color:#17366d; font-size:14px; line-height:1.25; overflow-wrap:anywhere; }}
    .signal-pill small {{ color:#66737f; font-size:10px; font-weight:800; }}
    .signal-pill.notice {{ border-color:#f1c982; background:#fffaf0; }}
    .signal-pill.muted {{ border-style:dashed; background:#f8fafc; }}
    .signal-pill.ok {{ border-color:#b9ddd3; background:#f4fcf9; }}
    .lower-summary-row {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:12px; }}
    .summary-choice-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; }}
    .summary-choice {{ min-height:38px; padding:8px 10px; border:1px solid #d9e5f5; border-radius:9px; background:#fbfdff; display:flex; align-items:center; justify-content:space-between; gap:8px; }}
    .summary-choice span {{ color:#111922; font-weight:800; }}
    .summary-choice b {{ color:#1d4ed8; font-size:12px; padding:3px 8px; border-radius:999px; background:#ecf4ff; }}
    .context-card {{ padding:16px 18px; }}
    .context-card h2 {{ margin:5px 0 10px; color:#17366d; font-size:20px; line-height:1.3; }}
    .context-card strong {{ display:block; color:#111922; font-size:15px; line-height:1.35; }}
    .context-card p, .context-card li {{ color:#425466; font-size:13px; line-height:1.45; }}
    .context-card ul {{ margin:8px 0 0; padding-left:18px; }}
    .context-row {{ display:grid; grid-template-columns:1fr; gap:5px; align-items:start; min-height:30px; border-top:1px solid #dfe7ef; padding:10px 0 0; background:transparent; }}
    .context-row + .context-row {{ margin-top:6px; }}
    .context-row span {{ color:#1f2933; font-size:13px; line-height:1.35; }}
    .context-card.global {{ border-left:4px solid #f59e0b; }}
    .context-card.resident {{ border-left:4px solid #285b99; }}
    .context-card.data-limit {{ border-left:4px solid #7d8792; }}
    .hindenburg-lamp {{ border-left:4px solid #8aa0b5; }}
    .hindenburg-lamp.active {{ border-left-color:#f59e0b; background:#fffaf0; }}
    .lamp-row {{ display:flex; align-items:center; gap:8px; margin:0 0 8px; }}
    .lamp-row span {{ width:22px; height:22px; border-radius:999px; background:#d1d9e4; box-shadow:inset 0 1px 4px rgba(16,32,51,.22); }}
    .hindenburg-lamp.normal .lamp-row span:first-child {{ background:#7fc35a; }}
    .hindenburg-lamp.active .lamp-row span:nth-child(2) {{ background:#f59e0b; }}
    .hindenburg-lamp.unavailable .lamp-row span:nth-child(3) {{ background:#9aa8b6; }}
    .lamp-row strong {{ margin-left:auto; color:#17366d; font-size:14px; }}
    .supplement-link-card {{ display:flex; flex-direction:column; justify-content:center; gap:8px; min-height:112px; padding:18px 20px; text-decoration:none; color:#fff; background:#173f7a; border-color:#173f7a; transition:transform .16s ease, background-color .16s ease; }}
    .supplement-link-card strong {{ font-size:18px; }}
    .supplement-link-card span {{ color:#dce9f9; }}
    .supplement-link-card:hover {{ transform:translateY(-2px); background:#102f62; }}
    .supplement-link-card:focus-visible {{ outline:3px solid #86b7f2; outline-offset:3px; }}
    .detail-summary-grid {{ margin-top:18px; }}
    .glance-summary, .buy-decision-flow {{ flex: 0 0 100%; max-width:100%; box-sizing:border-box; background: rgba(255,255,255,0.94); border:1px solid var(--line); border-radius:18px; padding:18px 20px; }}
    .visual-first-read.glance-summary {{ flex:initial; max-width:none; }}
    .glance-heading, .buy-flow-heading {{ display:flex; align-items:center; justify-content:space-between; gap:14px; margin-bottom:14px; }}
    .glance-heading h2::before {{ content:'●'; display:inline-grid; place-items:center; width:24px; height:24px; margin-right:8px; border-radius:999px; background:#1d4ed8; color:#fff; font-size:10px; vertical-align:2px; }}
    .glance-heading h2, .buy-flow-heading h2 {{ margin:0; font-size:21px; line-height:1.2; color:#17366d; }}
    .glance-heading p, .buy-flow-heading p {{ margin:4px 0 0; color:#52606d; font-size:13px; line-height:1.35; }}
    .glance-grid {{ display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; }}
    .glance-tile {{ min-height:132px; padding:14px; border:1px solid var(--line); border-radius:14px; background:#fff; display:flex; flex-direction:column; justify-content:center; gap:8px; min-width:0; }}
    .glance-tile.tone-watch {{ border-color:#f0c882; background:#fffaf0; }}
    .glance-tile.tone-wait {{ border-color:#c9dcfb; background:#f7fbff; }}
    .glance-tile.tone-normal {{ border-color:#b9ddd3; background:#f4fcf9; }}
    .glance-tile.tone-reason {{ border-color:#d8c9f2; background:#fbf7ff; }}
    .glance-tile.tone-next {{ border-color:#c9dcfb; background:#f8fbff; }}
    .glance-tile.tone-beginner {{ border-color:#f0d49a; background:#fffaf0; }}
    .tile-label {{ color:#17366d; font-size:13px; font-weight:800; text-align:center; }}
    .tile-icon {{ color:#5b7fc8; font-size:32px; line-height:1; text-align:center; font-weight:900; }}
    .tone-watch .tile-icon {{ color:#f59e0b; }}
    .tone-normal .tile-icon {{ color:#138a6b; }}
    .tile-main {{ color:#0f4fb8; font-size:20px; font-weight:900; line-height:1.2; text-align:center; overflow-wrap:anywhere; }}
    .tone-watch .tile-main {{ color:#d97706; }}
    .tone-normal .tile-main {{ color:#138a6b; }}
    .tile-sub {{ color:#425466; font-size:13px; line-height:1.55; text-align:center; }}
    .glance-tile ul {{ margin:0; padding-left:18px; color:#425466; font-size:13px; line-height:1.55; }}
    .glance-tile li + li {{ margin-top:3px; }}
    .chip-row {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:center; }}
    .chip-row span {{ display:inline-flex; align-items:center; justify-content:center; min-height:30px; padding:4px 12px; border:1px solid #bfd6f6; border-radius:999px; background:#edf5ff; color:#0f4fb8; font-weight:900; font-size:14px; line-height:1; }}
    .beginner-badge {{ display:inline-flex; align-items:center; min-height:26px; padding:0 10px; border:1px solid #b8d0f5; border-radius:999px; background:#f4f8ff; color:#1d4ed8; font-size:12px; font-weight:900; white-space:nowrap; }}
    .buy-flow-layout {{ display:grid; grid-template-columns:minmax(0,1fr) 210px; gap:18px; align-items:stretch; }}
    .buy-steps {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; }}
    .buy-step {{ position:relative; min-height:168px; padding:15px 13px 13px; border:1px solid #cbdcf3; border-radius:12px; background:#fff; text-align:center; display:flex; flex-direction:column; align-items:center; justify-content:flex-start; gap:8px; min-width:0; }}
    .buy-step:not(:last-child)::after {{ content:'›'; position:absolute; right:2px; top:50%; transform:translateY(-50%); color:#bfd0e8; font-size:34px; font-weight:900; z-index:2; }}
    .step-number {{ width:26px; height:26px; border-radius:999px; background:#1d4ed8; color:#fff; display:grid; place-items:center; font-size:14px; font-weight:900; }}
    .step-icon {{ color:#5b7fc8; font-size:30px; font-weight:900; line-height:1; min-height:30px; }}
    .buy-step h3 {{ margin:0; color:#17366d; font-size:14px; line-height:1.2; }}
    .buy-step strong {{ color:#17366d; font-size:17px; line-height:1.32; overflow-wrap:anywhere; }}
    .buy-step p {{ margin:0; color:#52606d; font-size:12px; line-height:1.45; }}
    .readiness-panel {{ border-left:1px solid var(--line); padding-left:18px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; }}
    .readiness-panel .score-label {{ color:#17366d; font-size:13px; font-weight:800; }}
    .readiness-panel .score-gauge {{ width:150px; height:92px; margin-top:8px; display:grid; place-items:center; overflow:hidden; position:relative; }}
    .readiness-panel .score-gauge::before {{ content:''; position:absolute; top:0; left:0; width:150px; height:150px; border-radius:999px; background:conic-gradient(from 270deg, #1d4ed8 0deg calc(var(--score) * 1.8deg), #e7edf5 calc(var(--score) * 1.8deg) 180deg, transparent 180deg 360deg); }}
    .readiness-panel .score-gauge::after {{ content:''; position:absolute; top:16px; left:16px; width:118px; height:118px; border-radius:999px; background:#fff; }}
    .score-number, .score-total {{ position:relative; z-index:1; }}
    .score-number {{ margin-top:14px; color:#102a43; font-size:38px; font-weight:900; line-height:1; }}
    .score-total {{ color:#52606d; font-size:14px; font-weight:800; }}
    .score-note {{ margin:8px 0 0; padding:8px 10px; border:1px solid #f3caca; border-radius:10px; background:#fff5f5; color:#c53030; font-size:12px; font-weight:900; }}
    .score-subnote {{ margin:6px 0 0; color:#52606d; font-size:11px; line-height:1.4; }}
    .hero-card, .decision-card, .mini-panel, .overview-panel, .support-panel {{ background: rgba(255,255,255,0.9); border:1px solid var(--line); border-radius:20px; }}
    .hero-card, .decision-card {{ padding: 17px 22px; }}
    .hero-card {{ flex:1.22 1 0; }}
    .decision-card {{ flex:0.96 1 0; }}
    .hero-label, .decision-label, .mini-panel h3, .overview-panel h3, .support-panel h3 {{ margin:0; font-size:14px; font-weight:700; color:#23406f; }}
    .manual-link-wrap {{ float:right; margin-left:8px; }}
    .manual-link {{ display:inline-flex; align-items:center; min-height:24px; padding:0 8px; border:1px solid #9eb7d6; border-radius:6px; background:#fff; color:#17366d; font-size:12px; font-weight:800; text-decoration:none; white-space:nowrap; }}
    .hero-main {{ display:grid; grid-template-columns:minmax(0,1.14fr) minmax(230px,0.86fr); gap:20px; align-items:center; margin-top:10px; }}
    .regime-display {{ display:inline-block; max-width:none; font-size: 48px; font-weight:800; line-height:1; color:#17366d; letter-spacing:0; word-break:keep-all; overflow-wrap:normal; white-space:nowrap; }}
    .hero-copy-strong {{ margin-top:10px; max-width: 30ch; font-size:14px; line-height:1.48; color:#243b53; }}
    .hero-side {{ display:grid; gap:14px; justify-items:center; align-self:stretch; }}
    .score-gauge {{ position:relative; width:206px; height:118px; overflow:hidden; }}
    .score-svg {{ position:absolute; inset:0; width:100%; height:100%; }}
    .score-track {{ fill:none; stroke:#e4ebf5; stroke-width:16; stroke-linecap:round; }}
    .score-progress {{ fill:none; stroke:url(#scoreGradient); stroke-width:16; stroke-linecap:round; }}
    .score-needle {{ position:absolute; left:50%; bottom:18px; width:6px; height:82px; background:transparent; transform-origin:bottom center; }}
    .score-needle::before {{ content:''; position:absolute; top:-2px; left:50%; transform:translateX(-50%); width:16px; height:16px; border-radius:999px; background:#fff; border:2px solid #d9e2ec; box-shadow:0 4px 10px rgba(16,32,51,0.12); }}
    .score-core {{ position:absolute; inset:auto 0 8px; display:grid; justify-items:center; gap:3px; }}
    .score-core .k {{ font-size:12px; color:#425466; font-weight:700; }}
    .score-core .v {{ font-size:42px; line-height:1; font-weight:800; color:#17366d; }}
    .score-core .sub {{ font-size:13px; color:#425466; }}
    .hero-metrics {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:0; margin-top:10px; border-top:1px solid var(--line); }}
    .hero-metric {{ padding:10px 14px 0; min-height:50px; }}
    .hero-metric + .hero-metric {{ border-left:1px solid var(--line); }}
    .hero-metric .k {{ font-size:13px; color:#425466; }}
    .hero-metric .v {{ margin-top:4px; font-size:17px; font-weight:800; color:#17366d; }}
    .hero-metric .v.green {{ color:#22824a; }}
    .hero-metric .v.orange {{ color:#d97706; }}
    .hero-metric .v.blue {{ color:#1d4ed8; }}
    .decision-headline {{ display:flex; align-items:center; gap:14px; margin-top:10px; }}
    .decision-icon {{ width:50px; height:50px; border-radius:999px; background: rgba(197,48,48,0.10); color:#c53030; display:grid; place-items:center; font-size:26px; font-weight:800; }}
    .decision-title {{ font-size: 42px; font-weight:800; line-height:1.04; color:#b91c1c; letter-spacing:0; }}
    .decision-banner {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(0,0.9fr); gap:14px; align-items:center; margin-top:10px; padding:10px 14px; border:1px solid rgba(220,38,38,0.28); border-radius:14px; background:rgba(255,250,250,0.82); }}
    .decision-banner .lead {{ font-size:15px; font-weight:800; color:#b91c1c; }}
    .decision-banner .minor {{ font-size:12px; color:#7b8794; font-weight:700; }}
    .decision-banner .value {{ font-size:15px; font-weight:800; color:#c53030; }}
    .decision-reasons {{ margin:10px 0 0; padding:0; list-style:none; display:grid; gap:6px; }}
    .decision-reasons li {{ display:flex; gap:8px; align-items:flex-start; color:#243b53; font-size:14px; line-height:1.36; }}
    .decision-reasons li::before {{ content:'●'; color:#c53030; font-size:13px; line-height:1.3; }}
    .candidate-inline {{ margin-top:8px; color:#52606d; font-size:13px; }}
    .candidate-inline strong {{ color:#7c4a00; }}
    .pre-supplement-grid {{ display:grid; grid-template-columns:minmax(0,.86fr) minmax(0,1fr) minmax(0,1.32fr); gap:16px; margin-top:18px; margin-bottom:18px; align-items:stretch; }}
    .pre-supplement-grid .mini-panel, .pre-supplement-grid .overview-panel {{ box-sizing:border-box; height:auto; min-height:420px; }}
    .pre-supplement-grid .sector-overview-row {{ grid-template-columns:44px 112px minmax(0,1fr) 54px; }}
    .mini-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; margin-top:18px; align-items:stretch; }}
    .mini-panel {{ box-sizing:border-box; padding:16px 18px; min-height:188px; height:100%; display:flex; flex-direction:column; }}
    .mini-content {{ margin-top:12px; }}
    .cycle-layout {{ display:grid; grid-template-columns:96px 1fr; gap:14px; align-items:center; }}
    .cycle-wheel {{ width:96px; height:96px; border-radius:999px; background: conic-gradient(#173f7a 0deg 48deg, #5e8fd8 48deg 120deg, #7ea8e5 120deg 192deg, #c7d8f4 192deg 264deg, #edf3fb 264deg 360deg); position:relative; }}
    .cycle-wheel::before {{ content:'⚑'; position:absolute; inset:20px; border-radius:999px; background:#fff; display:grid; place-items:center; font-size:30px; color:#385f9e; }}
    .cycle-big {{ font-size:22px; font-weight:800; color:#17366d; }}
    .cycle-copy {{ margin-top:6px; color:#52606d; font-size:14px; line-height:1.55; }}
    .cycle-foot {{ margin-top:10px; display:inline-block; padding:8px 12px; border:1px solid var(--line); border-radius:999px; color:#52606d; font-size:13px; background:#fff; }}
    .risk-track-note {{ margin:8px 0 10px; color:#52606d; font-size:12px; line-height:1.45; }}
    .risk-track-list {{ display:grid; gap:8px; }}
    .risk-track-row {{ display:grid; gap:5px; padding:7px 0; border-bottom:1px solid #edf2f7; }}
    .risk-track-row:last-child {{ border-bottom:0; }}
    .risk-track-head {{ display:grid; grid-template-columns:minmax(0,1fr) 58px 58px; gap:7px; align-items:center; }}
    .risk-track-label {{ font-size:13px; color:#243b53; font-weight:700; min-width:0; overflow-wrap:anywhere; }}
    .risk-track-bar {{ position:relative; height:12px; border-radius:999px; background:linear-gradient(90deg,#eaf2ed 0 40%,#fff3d7 40% 68%,#ffe4e0 68% 88%,#ffd1d1 88% 100%); overflow:hidden; box-shadow:inset 0 0 0 1px rgba(16,32,51,.07); }}
    .risk-track-fill {{ display:block; height:100%; border-radius:999px; }}
    .risk-track-fill.normal {{ background:#3fa168; }}
    .risk-track-fill.caution {{ background:#f59e0b; }}
    .risk-track-fill.danger, .risk-track-fill.extreme {{ background:#ef4444; }}
    .risk-track-marker {{ position:absolute; top:0; bottom:0; width:2px; background:#334e68; opacity:.8; }}
    .risk-track-marker.warning {{ left:40%; }}
    .risk-track-marker.danger {{ left:68%; }}
    .risk-track-marker.extreme {{ left:88%; background:#9b1c1c; }}
    .risk-track-value {{ font-size:12px; color:#243b53; text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
    .risk-track-state .risk-badge {{ display:block; text-align:center; font-size:10px; line-height:1.25; padding:4px 7px; }}
    .risk-track-scale {{ display:grid; grid-template-columns:40% 28% 20% 12%; color:#66737f; font-size:10px; line-height:1.15; }}
    .risk-track-scale span:nth-child(n+2) {{ text-align:center; }}
    .risk-track-thresholds {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:3px 8px; color:#52606d; font-size:10px; line-height:1.25; }}
    .risk-track-thresholds span {{ min-width:0; overflow-wrap:anywhere; }}
    .risk-track-proof {{ display:grid; gap:2px; color:#334e68; font-size:10px; line-height:1.28; }}
    .risk-track-proof span {{ min-width:0; overflow-wrap:anywhere; }}
    .provenance-strip {{ grid-column:2; grid-row:2; display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:8px; margin:0; }}
    .provenance-chip {{ border:1px solid #d7e4ef; background:#f8fbff; border-radius:8px; padding:7px 9px; min-width:0; }}
    .provenance-chip strong {{ display:block; color:#17366d; font-size:12px; line-height:1.2; overflow-wrap:anywhere; }}
    .provenance-chip span {{ display:block; margin-top:3px; color:#52606d; font-size:11px; line-height:1.25; overflow-wrap:anywhere; }}
    .provenance-chip.warn {{ border-color:#f4c779; background:#fff8e8; }}
    .provenance-chip.danger {{ border-color:#f4a3a3; background:#fff1f1; }}
    .candidate-boxes {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:14px; }}
    .candidate-box {{ padding:10px 10px; border:1px solid #cfe0f7; border-radius:14px; background:#fbfdff; text-align:center; }}
    .candidate-box strong {{ display:block; font-size:24px; color:#17366d; line-height:1.1; }}
    .candidate-box span {{ display:block; margin-top:4px; color:#52606d; font-size:13px; }}
    .threshold-status {{ margin-top:12px; font-size:18px; color:#52606d; }}
    .threshold-status strong {{ display:block; margin-top:4px; font-size:28px; color:#b7791f; }}
    .threshold-strip {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:18px; padding-top:14px; border-top:1px solid var(--line); }}
    .threshold-item {{ text-align:center; }}
    .threshold-item .n {{ font-size:30px; font-weight:800; line-height:1; }}
    .threshold-item .l {{ margin-top:4px; color:#52606d; font-size:13px; }}
    .overview-grid {{ display:grid; grid-template-columns:minmax(0,1.12fr) minmax(0,0.88fr); gap:16px; margin-top:46px; align-items:start; }}
    .overview-panel {{ padding:16px 18px; }}
    .overview-panel-head {{ display:flex; align-items:center; justify-content:space-between; gap:14px; }}
    .overview-panel-head h3 {{ margin:0; }}
    .sector-overview-layout {{ margin-top:12px; display:block; }}
    .sector-overview-wrap {{ min-width:0; }}
    .sector-overview-row {{ display:grid; grid-template-columns:44px 124px minmax(0,1fr) 54px; gap:10px; align-items:center; margin-top:10px; }}
    .sector-overview-tone {{ font-size:13px; font-weight:700; }}
    .sector-overview-tone.positive {{ color:#22824a; }}
    .sector-overview-tone.negative {{ color:#dc2626; }}
    .sector-overview-name {{ color:#243b53; font-weight:700; }}
    .sector-overview-bar {{ position:relative; height:8px; border-radius:999px; background:#edf2f7; overflow:hidden; }}
    .sector-overview-bar::after {{ content:""; position:absolute; left:50%; top:0; bottom:0; width:1px; background:#d6dee8; transform:translateX(-0.5px); }}
    .sector-overview-fill {{ position:absolute; top:0; height:100%; display:block; }}
    .sector-overview-fill.positive {{ left:50%; background:#219669; border-radius:0 999px 999px 0; }}
    .sector-overview-fill.negative {{ right:50%; background:#ef5350; border-radius:999px 0 0 999px; }}
    .sector-overview-value {{ font-weight:700; text-align:right; }}
    .sector-overview-value.positive {{ color:#219669; }}
    .sector-overview-value.negative {{ color:#ef5350; }}
    .momentum-side {{ display:flex; justify-content:flex-end; flex:0 0 94px; }}
    .momentum-card {{ width:94px; padding:9px 8px 8px; border:1px solid var(--line); border-radius:12px; color:#52606d; font-size:12px; background:#fff; }}
    .momentum-title {{ font-size:12px; font-weight:700; color:#243b53; white-space:nowrap; }}
    .momentum-scale {{ width:100%; height:7px; margin:9px 0 7px; border-radius:999px; background: linear-gradient(90deg,#f7b4b4 0%,#e5edf6 50%,#3fa168 100%); }}
    .momentum-labels {{ display:flex; justify-content:space-between; gap:6px; font-size:11px; }}
    .momentum-labels span:nth-child(1) {{ color:#dc2626; font-weight:700; }}
    .momentum-labels span:nth-child(2) {{ color:#52606d; font-weight:700; }}
    .momentum-labels span:nth-child(3) {{ color:#22824a; font-weight:700; }}
    .alert-stack {{ margin-top:12px; display:grid; gap:12px; }}
    .alert-stack-card {{ display:grid; grid-template-columns:54px minmax(0,1fr) 18px; gap:14px; align-items:center; padding:14px 16px; border-radius:14px; border:1px solid var(--line); background:#fff; min-height:96px; }}
    .alert-stack-card.high {{ border-color: rgba(220,38,38,0.28); }}
    .alert-stack-card.moderate {{ border-color: rgba(245,158,11,0.28); }}
    .alert-stack-card.low {{ border-color: rgba(125,145,166,0.22); }}
    .alert-stack-icon {{ width:42px; height:42px; border-radius:12px; display:grid; place-items:center; font-size:24px; font-weight:800; }}
    .alert-stack-card.high .alert-stack-icon {{ background:rgba(220,38,38,0.10); color:#dc2626; }}
    .alert-stack-card.moderate .alert-stack-icon {{ background:rgba(245,158,11,0.12); color:#d97706; }}
    .alert-stack-card.low .alert-stack-icon {{ background:rgba(59,130,246,0.10); color:#385f9e; }}
    .alert-stack-title {{ font-size:16px; font-weight:800; color:#17366d; }}
    .alert-stack-copy {{ margin-top:4px; color:#52606d; font-size:14px; line-height:1.55; }}
    .alert-stack-arrow {{ color:#52606d; font-size:28px; }}
    .support-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; margin-top:16px; margin-bottom:18px; align-items:stretch; }}
    .risk-context-hub {{ margin-top:18px; padding:18px 20px; border:1px solid var(--line); border-radius:22px; background:rgba(255,255,255,0.72); }}
    .risk-context-head {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }}
    .risk-context-head h2 {{ margin:0; font-size:20px; color:#17366d; }}
    .risk-context-head p {{ margin:2px 0 0; color:#52606d; line-height:1.55; }}
    .risk-context-grid {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:12px; margin-top:14px; }}
    .risk-context-card {{ padding:14px 14px; border:1px solid var(--line); border-radius:16px; background:#fff; min-width:0; }}
    .risk-context-type {{ color:#52606d; font-size:13px; font-weight:800; }}
    .risk-context-card strong {{ display:block; margin-top:7px; color:#17366d; line-height:1.45; word-break:break-word; }}
    .risk-context-card p {{ margin:8px 0 0; color:#52606d; font-size:13px; line-height:1.55; }}
    .support-panel {{ box-sizing:border-box; padding:16px 18px; min-height:188px; height:100%; display:flex; flex-direction:column; }}
    .support-body {{ margin-top:12px; }}
    .support-head {{ display:flex; align-items:center; gap:12px; }}
    .support-icon {{ width:44px; height:44px; border-radius:999px; display:grid; place-items:center; font-size:24px; color:#3d5f97; background:rgba(59,130,246,0.08); }}
    .support-title {{ font-size:16px; font-weight:800; color:#17366d; }}
    .candidate-chip-row {{ margin-top:14px; display:flex; gap:10px; flex-wrap:wrap; }}
    .candidate-chip-row.compact {{ margin-top:8px; gap:8px; }}
    .candidate-chip-row.domestic {{ margin-top:6px; gap:6px; }}
    .candidate-chip {{ padding:10px 16px; border:1px solid #e1d5bb; border-radius:14px; background:#fff8ee; color:#a16207; font-size:18px; font-weight:800; }}
    .candidate-chip-row.compact .candidate-chip {{ padding:7px 12px; font-size:15px; border-radius:10px; }}
    .candidate-chip-row.domestic .candidate-chip {{ padding:5px 8px; font-size:13px; border-radius:8px; }}
    .candidate-chip.muted {{ background:#f8fafc; border-color:#d9e2ec; color:#52606d; }}
    .candidate-chip.gold {{ background:#fff8ee; border-color:#ecd7aa; color:#b7791f; }}
    .candidate-chip.violet {{ background:#f7f2ff; border-color:#d8c7ff; color:#6d4cc7; }}
    .candidate-chip.domestic {{ background:#eef8f4; border-color:#badbcc; color:#246b4f; }}
    .candidate-chip small {{ display:block; margin-top:2px; color:inherit; font-size:11px; line-height:1.1; opacity:.78; }}
    .support-meta {{ margin-top:12px; color:#52606d; font-size:13px; line-height:1.55; }}
    .support-meta strong {{ color:#17366d; font-weight:800; word-break:break-word; }}
    .candidate-summary-card {{ grid-column:1 / -1; }}
    .candidate-cluster-grid {{ display:grid; grid-template-columns:minmax(0,1.1fr) minmax(220px,.9fr); gap:14px; align-items:stretch; }}
    .candidate-follow-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:0; margin-top:12px; border-top:1px solid #dbe4ee; }}
    .candidate-mini-block {{ padding:16px 18px; border:0; border-radius:0; background:#fff; min-width:0; min-height:150px; display:flex; flex-direction:column; }}
    .candidate-mini-block + .candidate-mini-block {{ border-left:1px solid #dbe4ee; }}
    .candidate-mini-block strong {{ display:block; color:#17366d; font-size:18px; line-height:1.35; }}
    .candidate-mini-block span {{ display:block; margin-top:6px; color:#52606d; font-size:14px; line-height:1.55; }}
    .history-embed {{ margin-top:18px; }}
    .history-embed-head {{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:16px; align-items:start; }}
    .history-embed-lead h2 {{ margin:0; font-size:20px; line-height:1.2; color:#17366d; }}
    .history-embed-copy {{ margin:8px 0 0; color:#52606d; line-height:1.6; }}
    .history-embed-side {{ width:min(620px, 100%); }}
    .history-embed-side .k {{ font-size:14px; font-weight:700; color:#5c6976; }}
    .history-embed-side .v {{ margin-top:6px; color:#52606d; line-height:1.55; }}
    .history-embed-strip {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:10px; }}
    .history-embed-card {{ padding:12px 14px; border:1px solid var(--line); border-radius:16px; background:rgba(255,255,255,0.72); }}
    .history-embed-card .label {{ font-size:12px; color:#52606d; font-weight:700; }}
    .history-embed-card .value {{ margin-top:6px; font-size:18px; line-height:1.25; font-weight:800; color:#17366d; }}
    .history-embed-card small {{ display:block; margin-top:6px; color:#52606d; line-height:1.45; }}
    .history-chart-card {{ margin-top:16px; padding:18px 20px; border:1px solid var(--line); border-radius:22px; background:rgba(255,255,255,0.58); }}
    .history-legend {{ display:flex; gap:14px; flex-wrap:wrap; color:#425466; font-size:14px; }}
    .history-legend span::before {{ content:''; display:inline-block; width:10px; height:10px; border-radius:999px; margin-right:6px; vertical-align:middle; }}
    .history-legend .on::before {{ background:#3f7d5e; }}
    .history-legend .transition::before {{ background:#b38a3a; }}
    .history-legend .off::before {{ background:#a24f4b; }}
    .history-legend .credit::before {{ background:#7d5d49; }}
    .history-legend .inflation::before {{ background:#c56d3d; }}
    .history-legend .recovery::before {{ background:#5f8792; }}
    .history-chart-shell {{ margin-top:12px; }}
    .history-chart-shell svg {{ width:100%; height:auto; display:block; }}
    .history-toolbar {{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; align-items:center; margin-top:14px; padding:12px 14px; border:1px solid var(--line); border-radius:16px; background:#fff; }}
    .history-toolbar input[type="range"] {{ width:100%; accent-color:#173f7a; }}
    .history-toolbar output {{ color:#52606d; font-size:13px; font-weight:700; }}
    ul {{ margin: 0; padding-left: 20px; }}
    @media (max-width: 860px) {{
      .topbar {{ grid-template-columns:1fr; grid-template-rows:auto; gap:12px; padding:12px 4px 16px; }}
      .brand, .status-strip, .monitor-note, .provenance-strip {{ grid-column:1; grid-row:auto; justify-self:stretch; }}
      .brand {{ gap:10px; }}
      .brand-mark {{ width:38px; height:38px; font-size:28px; }}
      .brand-title h1 {{ font-size:28px; white-space:normal; }}
      .status-strip {{ width:100%; }}
      .status-box {{ border-left:0; padding-left:0; }}
      .approved-report-dashboard {{ grid-template-columns:1fr; }}
      .decision-summary-grid, .main-reason-grid, .lower-summary-row, .candidate-cluster-grid, .candidate-follow-grid, .pre-supplement-grid {{ grid-template-columns:1fr; }}
      .signal-strip-grid {{ grid-template-columns:1fr 1fr; }}
      .dashboard-grid {{ flex-direction:column; }}
      .hero-main {{ grid-template-columns:1fr; }}
      .regime-display {{ white-space:normal; }}
      .hero-metrics {{ grid-template-columns:1fr 1fr; }}
      .mini-grid {{ grid-template-columns:1fr 1fr; }}
      .overview-grid {{ grid-template-columns:1fr; }}
      .support-grid {{ grid-template-columns:1fr 1fr; }}
      .risk-context-grid {{ grid-template-columns:1fr 1fr; }}
      .grid {{ grid-template-columns: 1fr; }}
      .summary-main {{ grid-template-columns: 1fr; }}
      .summary-metrics {{ grid-template-columns: 1fr; }}
      .glance-grid {{ grid-template-columns:1fr 1fr; }}
      .buy-flow-layout {{ grid-template-columns:1fr; }}
      .buy-steps {{ grid-template-columns:1fr; }}
      .readiness-panel {{ border-left:0; border-top:1px solid var(--line); padding-left:0; padding-top:14px; }}
      .sector-overview-layout {{ grid-template-columns:1fr; gap:12px; }}
      .overview-panel-head {{ align-items:flex-start; }}
      .momentum-side {{ justify-content:flex-start; }}
      .history-embed-head {{ grid-template-columns:1fr; }}
      .history-embed-side {{ width:100%; }}
      .history-embed-strip {{ grid-template-columns:1fr; }}
      .history-toolbar {{ grid-template-columns:1fr; }}
      .provenance-strip {{ grid-template-columns:1fr 1fr; }}
      .monitor-note {{ max-width:none; text-align:left; font-size:12px; }}
      .hero-top {{ flex-direction: column; }}
      .hero-link-card {{ width: 100%; }}
      .sector-top {{ grid-template-columns: 1fr; }}
      .sector-guide {{ margin-top: 0; }}
    }}
    @media (max-width: 1180px) {{
      .approved-report-dashboard {{ grid-template-columns:1fr; }}
      .signal-strip-grid {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
      .main-report-context-stack {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
      .supplement-link-card {{ min-height:0; }}
      .decision-headline {{ align-items:flex-start; }}
      .decision-title {{ font-size: clamp(30px, 4.2vw, 46px); }}
      .decision-banner {{ grid-template-columns:1fr; gap:8px; }}
      .hero-metrics {{ grid-template-columns:1fr 1fr; row-gap:8px; }}
      .hero-metric:nth-child(3) {{ border-left:0; }}
      .support-grid {{ grid-template-columns:1fr 1fr; }}
      .risk-context-grid {{ grid-template-columns:1fr 1fr; }}
      .glance-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
      .buy-flow-layout {{ grid-template-columns:1fr; }}
      .buy-steps {{ grid-template-columns:repeat(5,minmax(0,1fr)); }}
      .readiness-panel {{ border-left:0; border-top:1px solid var(--line); padding-left:0; padding-top:14px; }}
    }}
    @media (max-width: 860px) {{
      .main-report-context-stack {{ grid-template-columns:1fr; }}
      .decision-hero-card {{ grid-template-columns:1fr; text-align:center; justify-items:center; }}
      .reading-guide {{ grid-template-columns:1fr; }}
      .reading-guide li + li {{ border-left:0; border-top:1px solid #dbe4ee; }}
      .visual-first-read {{ padding:16px; }}
      .section-title-row {{ align-items:flex-start; }}
      .section-chip {{ white-space:normal; text-align:center; }}
      .candidate-mini-block + .candidate-mini-block {{ border-left:0; border-top:1px solid #dbe4ee; }}
      .glance-grid {{ grid-template-columns:1fr 1fr; }}
      .buy-steps {{ grid-template-columns:1fr; }}
      .buy-step:not(:last-child)::after {{ display:none; }}
    }}
    @media (max-width: 520px) {{
      .topbar {{ gap:8px; margin-bottom:10px; }}
      .status-strip {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }}
      .status-box {{ min-width:0; }}
      .status-box .k {{ font-size:10px; }}
      .status-box .v {{ font-size:12px; white-space:normal; overflow-wrap:anywhere; }}
      .provenance-strip, .monitor-note {{ display:none; }}
      .section-title-row h2 {{ font-size:24px; }}
      .reading-guide {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
      .reading-guide li {{ min-height:58px; gap:7px; padding:8px 6px; }}
      .reading-guide li + li {{ border-top:0; border-left:1px solid #dbe4ee; }}
      .reading-guide b {{ width:24px; height:24px; font-size:12px; }}
      .reading-guide strong {{ font-size:13px; }}
      .reading-guide small {{ display:none; }}
      .decision-hero-card {{ padding:18px; }}
      .decision-hero-icon {{ width:72px; height:72px; font-size:42px; }}
    }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"topbar\">
      <div class=\"brand\">
        <div class=\"brand-mark\">◎</div>
        <div class=\"brand-title\">
          <h1>{html.escape(report['title'])}</h1>
        </div>
      </div>
      <div class=\"status-strip\">
        <div class=\"status-box\"><div class=\"k\">生成日時</div><div class=\"v\">{html.escape(report['generated_at'])} JST</div></div>
        <div class=\"status-box\"><div class=\"k\">データソース</div><div class=\"v\">{html.escape(report['data_source'])}</div></div>
        <div class=\"status-box\"><div class=\"k\">判定信頼性</div><div class=\"v\">{html.escape(_jp_reliability(report.get('data_reliability', {}).get('level', 'high')))}</div></div>
      </div>
      {provenance_strip_html}
      <div class=\"monitor-note\"><span class=\"monitor-note-segment\">本レポートは市場のモニタリングを目的としており、</span><span class=\"monitor-note-segment\">投資助言・推奨を行うものではありません。</span></div>
    </div>

    {approved_report_dashboard_html}

    <div class=\"dashboard-grid detail-summary-grid\">
      <section class=\"hero-card\">
        <div class=\"hero-label\">市場レジーム</div>
        <div class=\"hero-main\">
          <div>
            <div class=\"regime-display\">{html.escape(regime_label)}</div>
            <div class=\"hero-copy-strong\">{hero_summary_copy}</div>
            <div class=\"inline-note\">上昇再開 {html.escape(recovery_grade_label)} / 警戒 {html.escape(blocker_level_label)} / 新判断 {html.escape(decision_action)} / 旧判断 {html.escape(legacy_action_label)} / レジーム減点 {float(report['spot_signal'].get('regime_penalty', 0) or 0):.1f}</div>
          </div>
          <div class=\"hero-side\">
            <div class=\"score-gauge\">
              <svg class=\"score-svg\" viewBox=\"0 0 250 146\" aria-hidden=\"true\">
                <defs>
                  <linearGradient id=\"scoreGradient\" x1=\"25\" y1=\"125\" x2=\"225\" y2=\"125\" gradientUnits=\"userSpaceOnUse\">
                    <stop offset=\"0%\" stop-color=\"#e84c3d\" />
                    <stop offset=\"28%\" stop-color=\"#f7b733\" />
                    <stop offset=\"62%\" stop-color=\"#93c54b\" />
                    <stop offset=\"100%\" stop-color=\"#1e9c6d\" />
                  </linearGradient>
                </defs>
                <path class=\"score-track\" d=\"M 25 125 A 100 100 0 0 1 225 125\" />
                <path class=\"score-progress\" d=\"M 25 125 A 100 100 0 0 1 225 125\" />
              </svg>
              <div class=\"score-needle\" style=\"transform: translateX(-50%) rotate({-90 + score_degrees:.1f}deg);\"></div>
              <div class=\"score-core\">
                <div class=\"k\">合成スコア</div>
                <div class=\"v\">{html.escape(_display_compact_number(report['score'].get('total_score')))}</div>
                <div class=\"sub\">/ 1.00</div>
              </div>
            </div>
          </div>
        </div>
        <div class=\"hero-metrics\">
          <div class=\"hero-metric\"><div class=\"k\">上昇再開の証拠</div><div class=\"v green\">{html.escape(recovery_grade_label)}</div></div>
          <div class=\"hero-metric\"><div class=\"k\">騙し上昇の警戒</div><div class=\"v orange\">{html.escape(blocker_level_label)}</div></div>
          <div class=\"hero-metric\"><div class=\"k\">スポット投資判断</div><div class=\"v blue\">{html.escape(action_label)}</div></div>
          <div class=\"hero-metric\"><div class=\"k\">旧判定用スコア</div><div class=\"v\">{html.escape(_display_compact_number(report['spot_signal'].get('legacy_adjusted_score', report['spot_signal'].get('adjusted_score', report['score'].get('total_score')))))}</div></div>
        </div>
      </section>

      <section class=\"decision-card\">
        <div class=\"decision-label\">スポット投資判断</div>
        <div class=\"decision-headline\">
          <div class=\"decision-icon\">&#10074;&#10074;</div>
          <div class=\"decision-title\">今は{html.escape(decision_action)}</div>
        </div>
        <div class=\"decision-banner\">
          <div class=\"lead\">二段下げリスク: {html.escape(risk_label)}</div>
          <div>
            <div class=\"minor\">市場ストレス段階</div>
            <div class=\"value\">{html.escape(str(risk_lines.get('stage_label', '-')))}</div>
          </div>
        </div>
        <ul class=\"decision-reasons\">
          {"".join(f"<li>{html.escape(reason)}</li>" for reason in primary_reason_lines)}
        </ul>
        <div class=\"candidate-inline\">参考候補: <strong>{html.escape(', '.join(item.get('ticker', '-') for item in candidate.get('candidate_tickers', [])[:2]) or 'なし')}</strong></div>
      </section>
    </div>
    <div class=\"pre-supplement-grid\">
      <section class=\"mini-panel\">
        <h3>サイクル判定</h3>
        <div class=\"mini-content cycle-layout\">
          <div class=\"cycle-wheel\"></div>
          <div>
            <div class=\"cycle-big\">{html.escape(cycle_label)}</div>
            <div class=\"cycle-copy\">サイクル位相 {html.escape(_display_number(report['cycle'].get('phase_angle_deg')))} 度。上昇の勢いと転換準備の位置を補助的に見ます。</div>
            <span class=\"cycle-foot\">平均的な継続期間: 3〜6週</span>
          </div>
        </div>
      </section>
      <section class=\"mini-panel\">
        <h3>危険ライン（現在値と判定）</h3>
        <p class=\"risk-track-note\">棒は各指標の採用ルールを0-100化した危険度です。現在位置、注意ライン、危険ライン、非常に危険ラインの距離感を確認します。</p>
        <div class=\"mini-content risk-track-list\">
          {risk_highlight_rows}
        </div>
      </section>
      <section class=\"overview-panel sector-compact-panel\">
        <div class=\"overview-panel-head\">
          <h3>セクター概要</h3>
          <div class=\"momentum-side\">
            <div class=\"momentum-card\"><div class=\"momentum-title\">相対モメンタム</div><div class=\"momentum-scale\"></div><div class=\"momentum-labels\"><span>弱</span><span>中立</span><span>強</span></div></div>
          </div>
        </div>
        <div class=\"sector-overview-layout\">
          <div class=\"sector-overview-wrap\">
            {sector_overview_html}
          </div>
        </div>
      </section>
    </div>
    {supplemental_signal_strip_html}
    {risk_context_ux_hub_html}

    <div class=\"mini-grid report-ops-grid\">
      <section class=\"support-panel\">
        <h3>データ取得</h3>
        <div class=\"support-body\">
          <div class=\"support-head\"><div class=\"support-icon\">▣</div><div class=\"support-title\">データ健全性</div></div>
          <div class=\"support-meta\">信頼性: <strong>{html.escape(_jp_reliability(report.get('data_reliability', {}).get('level', 'high')))}</strong><br>ソース: <strong>{html.escape(report['data_source'])}</strong><br>データ品質上限: <strong>{html.escape(_jp_action(str(report.get('data_reliability', {}).get('max_action', 'buy_window'))))}</strong><br>実データ取得率: <strong>{html.escape(_display_percent(report.get('data_reliability', {}).get('live_ratio')))}</strong><br>代替取得内訳: <strong>代替ティッカー={html.escape(str(report.get('data_reliability', {}).get('proxy_fallback_count', 0)))} / サンプル代替={html.escape(str(report.get('data_reliability', {}).get('sample_fallback_count', 0)))} / 未取得={html.escape(str(report.get('data_reliability', {}).get('unavailable_count', 0)))}</strong><br>データ品質による降格: <strong>{'あり' if action_decision.get('reliability_cap_applied') else 'なし'} / {html.escape(', '.join(action_decision.get('cap_reason', [])) or str(report.get('data_reliability', {}).get('reason_code', '-')))}</strong></div>
        </div>
      </section>
    </div>

    <section class=\"hero\">
      <div class=\"hero-top\">
        <div class=\"hero-title\">
          <h1>補足レポート</h1>
          <p class=\"hero-copy\">以下は監査性と詳細確認のための既存レポート内容です。最新判断は上のダッシュボードを優先して読み、必要時のみこの下の詳細へ降ります。</p>
        </div>
        <div class=\"hero-link-card\"><div class=\"k\">画面リンク</div><div class=\"v\"><a href=\"dashboard.html\">履歴ダッシュボードを見る</a></div></div>
      </div>
    </section>

    <section class=\"hero history-embed\">
      <div class=\"history-embed-head\">
        <div class=\"history-embed-lead\">
          <h2>過去履歴ブラウズ</h2>
          <p class=\"history-embed-copy\">ここから下は、過去に保存された履歴だけを使うビューです。最新の実行結果とは別枠なので、上段と値が違う場合は過去時点との差です。</p>
        </div>
        <div class=\"history-embed-side\">
          <div class=\"k\">校正基準の見方</div>
          <div id=\"historyEmbedCalibrationNote\" class=\"v\">日次圧縮を主基準にし、全履歴は参考として残します。</div>
          <div class=\"history-embed-strip\">
            <div class=\"history-embed-card\"><div class=\"label\">履歴で現在選択中の時点</div><output id=\"historyEmbedTimestamp\" class=\"value\">履歴なし</output></div>
            <div class=\"history-embed-card\"><div class=\"label\">主基準: daily_latest</div><strong id=\"historyEmbedPrimaryCount\" class=\"value\">0件</strong><small>同日の再生成は最新1件へ圧縮</small></div>
            <div class=\"history-embed-card\"><div class=\"label\">参考: all_history</div><strong id=\"historyEmbedSecondaryCount\" class=\"value\">0件</strong><small>重複を含む全履歴の母数</small></div>
          </div>
        </div>
      </div>
      <div class=\"history-chart-card\">
        <div class=\"history-legend\"><span class=\"on\">リスクオン</span><span class=\"transition\">移行局面</span><span class=\"off\">リスクオフ</span><span class=\"credit\">信用ストレス</span><span class=\"inflation\">インフレ系</span><span class=\"recovery\">初期回復</span></div>
        <div class=\"history-chart-shell\"><svg id=\"historyEmbedChart\" viewBox=\"0 0 900 300\" role=\"img\" aria-label=\"履歴の合成スコア推移チャート\"></svg></div>
        <div class=\"history-toolbar\">
          <input id=\"historyEmbedRange\" type=\"range\" min=\"0\" max=\"0\" value=\"0\" />
          <output id=\"historyEmbedCount\">0件</output>
        </div>
      </div>
    </section>

    <section class=\"section\">
      <h2>セクターローテーション</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['sector'])}</p>
      <div class=\"sector-visual\">
        <h3>簡易ローテーション図</h3>
        <div class=\"sector-top\">
          <div class=\"sector-chart\">
            {sector_svg}
            <div class=\"sector-caption\">外側ほど 12 週騰落率が強く、上側ほど順位が高いセクターです。各週のセクター間の相対位置を見やすく置いた補助図で、絶対差そのものを距離で表したものではありません。</div>
          </div>
          <div class=\"sector-guide\">
            <h4>図の読み方</h4>
            <ul class=\"inline-note\">
              <li><span class="guide-key">出遅れ</span>は、順位も12週騰落率も弱く、まだ弱さが残る領域です。</li>
              <li><span class="guide-key">改善</span>は、順位は低いものの、12週騰落率が持ち直してきた領域です。</li>
              <li><span class="guide-key">先導</span>は、順位も12週騰落率も強く、相対的に主導している領域です。</li>
              <li><span class="guide-key">鈍化</span>は、上位を保ちながらも、12週騰落率の強さが弱くなっている領域です。</li>
              <li><span class="guide-key">出遅れ</span> → <span class="guide-key">改善</span> は、弱かったセクターの立ち直り初動です。</li>
              <li><span class="guide-key">改善</span> → <span class="guide-key">先導</span> は、持ち直しが本格化し、追い風が続く流れです。</li>
              <li><span class="guide-key">先導</span> → <span class="guide-key">鈍化</span> は、強さを保ちながら勢いが落ちる失速警戒です。</li>
              <li><span class="guide-key">鈍化</span> → <span class="guide-key">出遅れ</span> は、弱さが固定化しやすい流れです。</li>
              <li><span class="guide-key">出遅れ</span> → <span class="guide-key">鈍化</span> は、相対順位だけが先に上がっている可能性があります。</li>
              <li><span class="guide-key">先導</span> → <span class="guide-key">改善</span> は、強さは残るものの主導性がやや落ちた状態です。</li>
              <li>全体としては、<span class="guide-key">出遅れ</span> → <span class="guide-key">改善</span> → <span class="guide-key">先導</span> が上向きの王道パスです。<span class="guide-key">改善</span>は持ち直しの初動、<span class="guide-key">鈍化</span>は上位でも勢いが落ちる局面として読むのが実務的です。</li>
            </ul>
          </div>
        </div>
        <div class=\"sector-table\">
          <table>
            <tr><th>ティッカー</th><th>日本語</th><th>12週騰落率</th><th>順位</th><th>位置</th></tr>
            {sector_rows}
          </table>
        </div>
      </div>
    </section>

    <section class=\"section\">
      <h2>判定の読み方</h2>
      <p>このレポートは予測ではなく、現在の観測値を整理して判断を補助するためのものです。数値が良く見えても、単独で売買判断を確定させる用途には使わず、保有方針や資金配分と併せて解釈してください。</p>
      <ul>
        <li>市場レジーム: 地合いの大枠です。リスクオンなら強気寄り、リスクオフなら慎重寄りで見ます。</li>
        <li>サイクル判定: 上昇・終盤・回復・下降のどこに近いかを見る補助線です。</li>
        <li>合成スコア: 条件の揃い具合です。高いほど押し目検討の材料が増えます。</li>
        <li>スポット投資判断: 今すぐ積極化するか、監視を続けるか、待つかの運用向け要約です。</li>
      </ul>
    </section>

    <section class="section">
      <h2>判定理由</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['decision_reasons'])}</p>
      <ul>
        <li>上昇再開の証拠: {html.escape(recovery_grade)} / スコア {html.escape(recovery_score)}</li>
        <li>騙し上昇の警戒: {html.escape(blocker_level)} / {html.escape(str(blocker_assessment.get('summary', '-')))}</li>
        <li>最終判断: {html.escape(decision_action)} / 判定モード {html.escape(str(action_decision.get('mode', '-')))}</li>
        {"".join(f"<li>{html.escape(_localize_display_text(reason))}</li>" for reason in report["spot_signal"].get("rationale", []))}
      </ul>
    </section>

    <section class=\"section\">
      <h2>危険ライン監視</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['risk_lines'])}</p>
      <ul>
        <li>段階: {risk_stage_badge_html}</li>
        <li>要約: {html.escape(str(risk_lines.get("summary", "-")))}</li>
        <li>厳密性: {html.escape(str(risk_lines.get("precision_label", "-")))}</li>
        <li>不足指標: {html.escape(", ".join(risk_lines.get("strict_missing_indicators", []) or risk_lines.get("missing_indicators", [])) or "なし")}</li>
        <li>総合ストレス指数: {html.escape(_display_number(risk_lines.get("composite_risk_score")))}</li>
        <li>合成スコア側の内部警告件数: {internal_warning_count}</li>
        <li>危険ライン本数: {risk_lines.get("danger_count", 0)} / 非常に危険ライン本数: {risk_lines.get("extreme_count", 0)}</li>
        <li>注記: 内部警告件数は alerts/warnings の件数で、危険ライン段階とは別の判定です。</li>
      </ul>
      {risk_line_confidence_audit_html}
      <ul>{risk_line_reason_items}</ul>
      <table>
        <thead><tr><th>指標</th><th>判定</th><th>現在値</th><th>warning</th><th>danger</th><th>extreme</th><th>本判定根拠</th><th>参考・除外</th></tr></thead>
        <tbody>{risk_line_rows}</tbody>
      </table>
    </section>
    <section class=\"section\">
      <h2>投資候補</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['candidates'])}</p>
      <ul>
        <li>判定: {html.escape(candidate.get('label', '候補なし'))}</li>
        <li>要約: {html.escape(candidate.get('summary', '-'))}</li>
        <li>優先資産: {html.escape(f"{candidate_asset.get('asset_class', '-')} ({candidate_asset.get('ticker', '-')} / {candidate_asset.get('ticker_name_ja', '-')})" if candidate_asset else 'なし')}</li>
        <li>優先セクター: {html.escape(f"{candidate_sector.get('sector_name_ja', '-')} ({candidate_sector.get('ticker', '-')})" if candidate_sector else 'なし')}</li>
        <li>候補ティッカー: {html.escape(candidate_tickers)}</li>
      </ul>
      <ul>{candidate_items}</ul>
    </section>

    {_multi_asset_candidate_html(report)}

    <section class=\"section\">
      <h2>先回り候補</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['recovery_candidates'])}</p>
      <ul>
        <li>判定: {html.escape(recovery.get('label', '候補なし'))}</li>
        <li>要約: {html.escape(recovery.get('summary', '-'))}</li>
        <li>優先資産: {html.escape(f"{recovery_asset.get('label', '-')} ({recovery_asset.get('ticker', '-')} / {recovery_asset.get('ticker_name_ja', '-')})" if recovery_asset else 'なし')}</li>
        <li>優先セクター: {html.escape(f"{recovery_sector.get('ticker_name_ja', '-')} ({recovery_sector.get('ticker', '-')})" if recovery_sector else 'なし')}</li>
        <li>候補ティッカー: {html.escape(recovery_tickers)}</li>
      </ul>
      <ul>{recovery_items}</ul>
    </section>

    <section class=\"section\">
      <h2>レジーム先回り候補</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['regime_leading_candidates'])}</p>
      <ul>
        <li>判定: {html.escape(regime_leading.get('label', '候補なし'))}</li>
        <li>要約: {html.escape(regime_leading.get('summary', '-'))}</li>
        <li>優先セクター: {html.escape(f"{regime_leading_sector.get('ticker_name_ja', '-')} ({regime_leading_sector.get('ticker', '-')})" if regime_leading_sector else 'なし')}</li>
        <li>優先地域: {html.escape(f"{regime_leading_region.get('ticker_name_ja', '-')} ({regime_leading_region.get('ticker', '-')})" if regime_leading_region else 'なし')}</li>
        <li>優先資産: {html.escape(f"{regime_leading_asset.get('ticker_name_ja', '-')} ({regime_leading_asset.get('ticker', '-')})" if regime_leading_asset else 'なし')}</li>
        <li>候補ティッカー: {html.escape(regime_leading_tickers)}</li>
      </ul>
      <ul>{regime_leading_items}</ul>
    </section>

    <section class="section">
      <h2>セクターローテーション内部構造</h2>
      <p>Phase 2 のベクトル分析を補助入力として要約した内部構造です。主判定を上書きせず、レジーム・ランキング・Spot 判定の補助材料としてのみ使います。</p>
      <ul>
        <li>内部構造ラベル: {html.escape(str(sector_structure.get('structure_label', 'Noisy / Unclear')))}</li>
        <li>市場内部構造コメント: {html.escape(str(sector_market_structure_comment))}</li>
        <li>セクター分散指標: {html.escape(str(sector_structure.get('dispersion_score', 0.0)))}</li>
        <li>相対広がり指標: {html.escape(f"watch_share={sector_structure.get('watch_share', 0.0)} / promising_share={sector_structure.get('promising_share', 0.0)}")}</li>
        <li>相対広がり要約: {html.escape(_share_summary_ja(sector_structure))}</li>
        <li>内部構造3層: {html.escape(f"breadth={sector_structure.get('structure', {}).get('breadth', '-')} / leadership={sector_structure.get('structure', {}).get('leadership', '-')} / stability={sector_structure.get('structure', {}).get('stability', '-')}")}</li>
        <li>内部構造要約: {html.escape(_structure_summary_ja(sector_structure))}</li>
        <li>stability内訳: {html.escape(_stability_detail_summary_ja(sector_structure))}</li>
        <li>単独主導セクター: {html.escape(str(sector_structure.get('dominant_sector') or '-'))}</li>
        <li>単独主導強度: {html.escape(str(sector_structure.get('dominance_strength') or '-'))}</li>
        <li>単独主導理由: {html.escape(str(sector_structure.get('dominance_reason_short') or '-'))}</li>
        <li>単独主導内訳: {html.escape(_dominance_components_ja(sector_structure))}</li>
        <li>次候補セクター: {html.escape(', '.join(f"{row.get('ticker', '-')}({row.get('sector_name_ja', '-')})" for row in sector_next_candidates) or 'なし')}</li>
        <li>失速警戒セクター: {html.escape(', '.join(f"{row.get('ticker', '-')}({row.get('sector_name_ja', '-')})" for row in sector_peakout_sectors) or 'なし')}</li>
        {sector_adjustment_items}
      </ul>
    </section>

    <section class=\"section\">
      <h2>資産クラス比較</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['asset'])}</p>
      <table>
        <tr><th>資産クラス</th><th>ティッカー</th><th>12週モメンタム</th><th>年率ボラ</th><th>最大DD</th></tr>
        {asset_rows}
      </table>
    </section>

    <section class=\"section\">
      <h2>信用監視</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['credit'])}</p>
      <table>
        <tr><th>系列</th><th>現在値</th><th>1週</th><th>4週</th><th>12週</th><th>z スコア</th><th>判定</th></tr>
        {credit_rows}
      </table>
    </section>

    <section class=\"section\">
      <h2>インフレ監視</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['inflation'])}</p>
      <table>
        <tr><th>系列</th><th>現在値</th><th>1週</th><th>4週</th><th>12週</th><th>z スコア</th><th>判定</th></tr>
        {inflation_rows}
      </table>
    </section>

    <section class=\"section\">
      <h2>円建て・為替リスク</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['japan_risk'])}</p>
      <ul>
        <li>判定: {html.escape(_jp_japan_risk_level(japan_risk.get('level')))}</li>
        <li>要約: {html.escape(str(japan_risk.get('summary', '-')))}</li>
      </ul>
      <table>
        <tr><th>為替</th><th>現在値</th><th>1週</th><th>4週</th><th>12週</th><th>z スコア</th><th>判定</th></tr>
        {japan_fx_rows}
      </table>
      <table>
        <tr><th>資産</th><th>ティッカー</th><th>USD建て4週</th><th>円建て4週</th><th>為替寄与</th><th>円建て最大DD</th><th>判定</th></tr>
        {japan_asset_rows}
      </table>
    </section>

    <section class=\"section\">
      <h2>警告レイヤー</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['alerts'])}</p>
      <ul>{alert_items}</ul>
    </section>

    <section class=\"section\">
      <h2>類似局面</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['analogues'])}</p>
      <table>
        <tr><th>基準日</th><th>類似度</th><th>その後12週リターン</th></tr>
        {analogue_rows}
      </table>
    </section>

    <section class=\"section\">
      <h2>データ取得状況</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['availability'])}</p>
      <table>
        <tr><th>要求系列</th><th>状態</th><th>実使用系列</th><th>代替候補</th><th>説明</th></tr>
        {availability_rows}
      </table>
    </section>

    <section class=\"section\">
      <h2>接続診断</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['diagnostics'])}</p>
      <table>
        <tr><th>項目</th><th>内容</th></tr>
        {diagnostic_rows}
      </table>
      <h3>代表エラー</h3>
      <ul>{diagnostic_error_items}</ul>
    </section>

    <section class=\"section\">
      <h2>警告</h2>
      <ul>{warning_items}</ul>
    </section>
  </div>
  <script id="historyEmbedPayload" type="application/json">{history_payload_json}</script>
  <script>
    (() => {{
      const payload = JSON.parse(document.getElementById('historyEmbedPayload').textContent || '{{}}');
      const entries = payload.history || [];
      const meta = payload.meta || {{ history_count: entries.length, daily_latest_count: entries.length, primary_basis: 'daily_latest' }};
      const colors = {{
        risk_on: '#3f7d5e',
        transition: '#b38a3a',
        risk_off: '#a24f4b',
        credit_stress: '#7d5d49',
        inflation_shock: '#c56d3d',
        stagflation_warning: '#b15b42',
        data_unavailable: '#52606d',
        early_recovery: '#5f8792',
        default: '#7a5c4d'
      }};
      const byId = (id) => document.getElementById(id);
      const svg = byId('historyEmbedChart');
      const range = byId('historyEmbedRange');
      const timestamp = byId('historyEmbedTimestamp');
      const count = byId('historyEmbedCount');
      byId('historyEmbedPrimaryCount').textContent = `${{meta.daily_latest_count || 0}}件`;
      byId('historyEmbedSecondaryCount').textContent = `${{meta.history_count || 0}}件`;
      byId('historyEmbedCalibrationNote').textContent = `主基準は ${{meta.primary_basis || 'daily_latest'}} です。同日の再生成は圧縮し、全履歴は参考として残します。`;
      if (!entries.length) {{
        svg.innerHTML = '<text x="450" y="150" text-anchor="middle" fill="#52606d" font-size="18">履歴データなし</text>';
        count.value = '0件';
        return;
      }}
      range.max = String(entries.length - 1);
      range.value = String(entries.length - 1);
      const width = 900;
      const height = 300;
      const margin = {{ top: 36, right: 34, bottom: 42, left: 54 }};
      const innerWidth = width - margin.left - margin.right;
      const innerHeight = height - margin.top - margin.bottom;
      const values = entries.map((entry) => (typeof entry.score === 'number' ? entry.score : 0));
      const minValue = Math.min(...values, 0);
      const maxValue = Math.max(...values, 1);
      const yPad = Math.max((maxValue - minValue) * 0.08, 0.08);
      const yMin = Math.max(0, minValue - yPad);
      const yMax = Math.min(1.05, maxValue + yPad);
      const xAt = (index) => margin.left + (entries.length === 1 ? innerWidth : (innerWidth * index) / (entries.length - 1));
      const yAt = (value) => margin.top + (1 - ((value - yMin) / Math.max(yMax - yMin, 0.001))) * innerHeight;
      function formatTimestampLabel(value) {{
        return String(value || '履歴なし').replace('T', ' ').slice(0, 16);
      }}
      function redraw(selectedIndex) {{
        const lines = [];
        for (let step = 0; step <= 4; step += 1) {{
          const v = yMin + ((yMax - yMin) * step) / 4;
          const y = yAt(v);
          lines.push(`<line x1="${{margin.left}}" y1="${{y.toFixed(1)}}" x2="${{width - margin.right}}" y2="${{y.toFixed(1)}}" stroke="#d9e2ec" stroke-width="1" />`);
          lines.push(`<text x="${{margin.left - 14}}" y="${{(y + 5).toFixed(1)}}" text-anchor="end" fill="#52606d" font-size="12">${{v.toFixed(2)}}</text>`);
        }}
        const path = entries.map((entry, index) => `${{index === 0 ? 'M' : 'L'}} ${{xAt(index).toFixed(1)}} ${{yAt(typeof entry.score === 'number' ? entry.score : 0).toFixed(1)}}`).join(' ');
        const points = entries.map((entry, index) => `<circle cx="${{xAt(index).toFixed(1)}}" cy="${{yAt(typeof entry.score === 'number' ? entry.score : 0).toFixed(1)}}" r="${{index === selectedIndex ? 6 : 4.5}}" fill="${{colors[entry.regime?.key] || colors.default}}" stroke="#ffffff" stroke-width="2" />`).join('');
        const selectedX = xAt(selectedIndex);
        svg.innerHTML = `
          <rect x="${{margin.left}}" y="${{margin.top}}" width="${{innerWidth}}" height="${{innerHeight}}" rx="18" fill="rgba(255,255,255,0.42)" stroke="#d9e2ec" />
          ${{lines.join('')}}
          <path d="${{path}}" fill="none" stroke="#8aa4c8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
          <line x1="${{selectedX.toFixed(1)}}" y1="${{margin.top}}" x2="${{selectedX.toFixed(1)}}" y2="${{(height - margin.bottom).toFixed(1)}}" stroke="#173f7a" stroke-width="2.5" stroke-dasharray="8 7" />
          ${{points}}
        `;
        timestamp.value = formatTimestampLabel(entries[selectedIndex]?.generated_at);
        count.value = `${{entries.length}}件の履歴`;
      }}
      redraw(entries.length - 1);
      range.addEventListener('input', (event) => {{
        redraw(Number(event.target.value || 0));
      }});
    }})();
  </script>
</body>
</html>
"""

    legacy_marker = '    <section class="hero">'
    if legacy_marker in html_output:
        html_output = html_output.split(legacy_marker, 1)[0].rstrip() + "\n  </div>\n</body>\n</html>\n"
    multi_asset_html = _multi_asset_candidate_html(report)
    if multi_asset_html:
        html_output = html_output.replace("\n  </div>\n</body>", f"\n{multi_asset_html}\n  </div>\n</body>", 1)
    return html_output


def _build_sector_rotation_context(sector_rotation: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in sector_rotation.get("table", [])]
    history_rows = sector_rotation.get("history") or sector_rotation.get("history_points") or []
    if not rows or not history_rows:
        return {"rows": rows, "analysis": {}}

    normalized_history: list[dict[str, Any]] = []
    for item in history_rows:
        ticker = str(item.get("sector") or item.get("ticker") or "").strip()
        if not ticker:
            continue
        normalized_item = dict(item)
        normalized_item["sector"] = ticker
        normalized_history.append(normalized_item)

    if not normalized_history:
        return {"rows": rows, "analysis": {}}

    try:
        fallback_analysis_map = calculate_sector_vectors(pd.DataFrame(normalized_history))
    except Exception:
        fallback_analysis_map = {}

    raw_candidate_map = sector_rotation.get("candidate_map") if isinstance(sector_rotation, dict) else None
    candidate_map = raw_candidate_map if isinstance(raw_candidate_map, dict) else {}
    raw_vector_analysis = sector_rotation.get("vector_analysis") if isinstance(sector_rotation, dict) else None
    vector_analysis = raw_vector_analysis if isinstance(raw_vector_analysis, dict) else {}

    enriched_rows: list[dict[str, Any]] = []
    enriched_analysis: dict[str, Any] = {}
    for row in rows:
        ticker = str(row.get("ticker", "")).strip()
        if not ticker:
            enriched_rows.append(row)
            continue

        analysis = dict(fallback_analysis_map.get(ticker, {}))
        server_analysis = vector_analysis.get(ticker)
        if isinstance(server_analysis, dict):
            analysis.update(server_analysis)
        if not analysis:
            enriched_rows.append(row)
            continue

        server_candidate = candidate_map.get(ticker) if isinstance(candidate_map.get(ticker), dict) else {}
        candidate_label = str(server_candidate.get("candidate_label") or analysis.get("candidate_label") or "")
        if not candidate_label:
            candidate_label = classify_sector_candidate(
                current_quadrant=str(analysis.get("current_quadrant", "center")),
                vec1=analysis.get("vectors", {}).get("previous", {}),
                vec2=analysis.get("vectors", {}).get("current", {}),
                normalized_length=float(analysis.get("normalized_length", 0.0) or 0.0),
                consistency=analysis.get("consistency", {}),
                radius=float(analysis.get("radius", 0.0) or 0.0),
            )

        enriched = dict(row)
        enriched["candidate_label"] = candidate_label
        enriched_rows.append(enriched)
        enriched_analysis[ticker] = {
            **analysis,
            "candidate_label": candidate_label,
            "candidate_reason": _sector_candidate_reason(analysis, candidate_label),
        }
    return {"rows": enriched_rows, "analysis": enriched_analysis}


def _render_sector_rotation_svg(sector_rotation: dict[str, Any], sector_context: dict[str, Any] | None = None) -> str:
    rows = sector_rotation.get("table", []) if isinstance(sector_rotation, dict) else []
    if not rows:
        return "<div>有効データなし</div>"

    sector_context = sector_context or _build_sector_rotation_context(sector_rotation if isinstance(sector_rotation, dict) else {})
    analysis_map = sector_context.get("analysis", {}) if isinstance(sector_context, dict) else {}
    if not analysis_map:
        return _render_sector_rotation_svg_legacy(rows)

    width = 640
    height = 600
    plot_min_x = 68
    plot_max_x = width - 68
    plot_min_y = 52
    plot_max_y = plot_min_y + (plot_max_x - plot_min_x)
    current_points: list[tuple[float, float]] = []
    for analysis in analysis_map.values():
        points = analysis.get("points", {})
        for key in ("two_weeks_ago", "one_week_ago", "current"):
            point = points.get(key)
            if point:
                current_points.append((float(point.get("x", 0.0) or 0.0), float(point.get("y", 0.0) or 0.0)))

    xs = [point[0] for point in current_points] or [0.0]
    ys = [point[1] for point in current_points] or [0.0]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    span_x = max(max_x - min_x, 0.0001)
    span_y = max(max_y - min_y, 0.0001)

    def scale_point(point: dict[str, Any]) -> tuple[float, float]:
        px = float(point.get("x", 0.0) or 0.0)
        py = float(point.get("y", 0.0) or 0.0)
        sx = plot_min_x + ((px - min_x) / span_x) * (plot_max_x - plot_min_x)
        sy = plot_max_y - ((py - min_y) / span_y) * (plot_max_y - plot_min_y)
        return sx, sy

    badge_gap = 14
    quadrant_badges = [
        (plot_max_x + badge_gap + 10, plot_min_y - 32, 54, 24, "先導"),
        (plot_min_x - badge_gap - 8, plot_min_y - 32, 54, 24, "改善"),
        (plot_max_x + badge_gap + 10, plot_max_y + badge_gap, 54, 24, "鈍化"),
        (plot_min_x - badge_gap - 16, plot_max_y + badge_gap, 62, 24, "出遅れ"),
    ]

    parts = [
        f"<svg viewBox='0 0 {width} {height}' width='{width}' height='{height}' role='img' aria-label='セクターローテーション図'>",
        f"<rect x='{plot_min_x}' y='{plot_min_y}' width='{plot_max_x - plot_min_x}' height='{plot_max_y - plot_min_y}' fill='none' stroke='#d9e2ec' stroke-width='1' rx='16' />",
        f"<line x1='{(plot_min_x + plot_max_x) / 2:.1f}' y1='{plot_min_y}' x2='{(plot_min_x + plot_max_x) / 2:.1f}' y2='{plot_max_y}' stroke='#d9e2ec' stroke-width='1' />",
        f"<line x1='{plot_min_x}' y1='{(plot_min_y + plot_max_y) / 2:.1f}' x2='{plot_max_x}' y2='{(plot_min_y + plot_max_y) / 2:.1f}' stroke='#d9e2ec' stroke-width='1' />",
    ]
    for cx, cy, badge_w, badge_h, label in quadrant_badges:
        parts.append(f"<rect x='{cx - badge_w / 2:.1f}' y='{cy:.1f}' width='{badge_w}' height='{badge_h}' rx='12' fill='#eef2f6' />")
        parts.append(
            f"<text x='{cx:.1f}' y='{cy + 16:.1f}' text-anchor='middle' font-size='11.5' font-weight='700' fill='#243b53'>{label}</text>"
        )
    previous_vectors: list[str] = []
    current_vectors: list[str] = []
    old_points: list[str] = []
    mid_points: list[str] = []
    current_points_svg: list[str] = []
    labels: list[str] = []

    for row in sector_context.get("rows", []):
        ticker = str(row.get("ticker", ""))
        analysis = analysis_map.get(ticker)
        if not analysis:
            continue
        points = analysis.get("points", {})
        point_old = points.get("two_weeks_ago")
        point_mid = points.get("one_week_ago")
        point_cur = points.get("current")
        if not point_old or not point_mid or not point_cur:
            continue
        x_old, y_old = scale_point(point_old)
        x_mid, y_mid = scale_point(point_mid)
        x_cur, y_cur = scale_point(point_cur)
        base_color = _sector_base_color(ticker)
        middle_color = _blend_hex_color(base_color, "#cbd5e0", 0.45)
        tooltip = html.escape(_sector_tooltip(ticker, row, analysis))
        label = html.escape(ticker)
        candidate_label = html.escape(str(analysis.get("candidate_label", "")))
        show_label = bool(candidate_label)

        previous_vectors.append(_sector_vector_segment(x_old, y_old, x_mid, y_mid, middle_color, tooltip, 2.2))
        current_vectors.append(_sector_vector_segment(x_mid, y_mid, x_cur, y_cur, base_color, tooltip, 2.8))
        old_points.append(f"<circle cx='{x_old:.1f}' cy='{y_old:.1f}' r='4.2' fill='#d4d8dd'><title>{tooltip}</title></circle>")
        mid_points.append(
            f"<circle cx='{x_mid:.1f}' cy='{y_mid:.1f}' r='5' fill='{middle_color}' stroke='#ffffff' stroke-width='0.8'><title>{tooltip}</title></circle>"
        )
        current_points_svg.append(
            f"<circle cx='{x_cur:.1f}' cy='{y_cur:.1f}' r='6.2' fill='{base_color}' stroke='#ffffff' stroke-width='0.9'><title>{tooltip}</title></circle>"
        )
        labels.append(f"<text x='{x_cur + 8:.1f}' y='{y_cur - 8:.1f}' font-size='11' font-weight='700' fill='#1f2933'>{label}</text>")
        if show_label:
            labels.append(f"<text x='{x_cur + 8:.1f}' y='{y_cur + 6:.1f}' font-size='10' fill='#52606d'>{candidate_label}</text>")

    parts.extend(previous_vectors)
    parts.extend(current_vectors)
    parts.extend(old_points)
    parts.extend(mid_points)
    parts.extend(current_points_svg)
    parts.extend(labels)
    parts.append("</svg>")
    return "".join(parts)


def _sector_vector_segment(x1: float, y1: float, x2: float, y2: float, color: str, tooltip: str, width: float) -> str:
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_length = 9.0
    arrow_half_width = 4.0
    left_x = x2 - arrow_length * math.cos(angle) + arrow_half_width * math.sin(angle)
    left_y = y2 - arrow_length * math.sin(angle) - arrow_half_width * math.cos(angle)
    right_x = x2 - arrow_length * math.cos(angle) - arrow_half_width * math.sin(angle)
    right_y = y2 - arrow_length * math.sin(angle) + arrow_half_width * math.cos(angle)
    return (
        f"<g><line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='{color}' stroke-width='{width:.1f}' stroke-linecap='round'><title>{tooltip}</title></line>"
        f"<polygon points='{x2:.1f},{y2:.1f} {left_x:.1f},{left_y:.1f} {right_x:.1f},{right_y:.1f}' fill='{color}'><title>{tooltip}</title></polygon></g>"
    )


def _render_sector_rotation_svg_legacy(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div>有効データなし</div>"

    width = 640
    height = 640
    cx = 320
    cy = 320
    max_radius = 230
    min_return = min(row["return_12w"] for row in rows)
    max_return = max(row["return_12w"] for row in rows)
    span = max(max_return - min_return, 0.0001)
    colors = {
        "leading": "#2f855a",
        "improving": "#3182ce",
        "weakening": "#d69e2e",
        "lagging": "#c53030",
    }

    parts = [
        f"<svg viewBox='0 0 {width} {height}' width='{width}' height='{height}' role='img' aria-label='セクターローテーション図'>",
        f"<circle cx='{cx}' cy='{cy}' r='{max_radius}' fill='none' stroke='#d9e2ec' stroke-width='1' />",
        f"<circle cx='{cx}' cy='{cy}' r='{max_radius * 0.66}' fill='none' stroke='#e9eef2' stroke-width='1' />",
        f"<circle cx='{cx}' cy='{cy}' r='{max_radius * 0.33}' fill='none' stroke='#f1f5f8' stroke-width='1' />",
        f"<line x1='{cx}' y1='{cy - max_radius - 10}' x2='{cx}' y2='{cy + max_radius + 10}' stroke='#d9e2ec' />",
        f"<line x1='{cx - max_radius - 10}' y1='{cy}' x2='{cx + max_radius + 10}' y2='{cy}' stroke='#d9e2ec' />",
        f"<text x='{cx}' y='24' text-anchor='middle' font-size='12' fill='#52606d'>先導</text>",
        f"<text x='{width - 36}' y='{cy + 4}' text-anchor='middle' font-size='12' fill='#52606d'>改善</text>",
        f"<text x='{cx}' y='{height - 18}' text-anchor='middle' font-size='12' fill='#52606d'>鈍化</text>",
        f"<text x='34' y='{cy + 4}' text-anchor='middle' font-size='12' fill='#52606d'>出遅れ</text>",
    ]

    count = len(rows)
    for idx, row in enumerate(rows):
        angle_deg = -90 + (360 / count) * idx
        angle = math.radians(angle_deg)
        radius = 40 + ((row["return_12w"] - min_return) / span) * (max_radius - 40)
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        color = colors.get(row["rotation_phase"], "#8d6e63")
        label = html.escape(row["ticker"])
        title = html.escape(f"{row['ticker']} {row['sector_name_ja']} / {row['return_12w']}")
        parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='6' fill='{color}'><title>{title}</title></circle>")
        parts.append(f"<text x='{x + 8:.1f}' y='{y - 8:.1f}' font-size='11' fill='#1f2933'>{label}</text>")

    parts.append("</svg>")
    return "".join(parts)


def _sector_tooltip(ticker: str, row: dict[str, Any], analysis: dict[str, Any]) -> str:
    consistency = analysis.get("consistency", {})
    return (
        f"{ticker} {row.get('sector_name_ja', '')} | 象限 {analysis.get('current_quadrant', '-')} | "
        f"前ベクトル {analysis.get('vectors', {}).get('previous', {}).get('direction', '-')} | "
        f"現ベクトル {analysis.get('vectors', {}).get('current', {}).get('direction', '-')} | "
        f"正規化長 {float(analysis.get('normalized_length', 0.0) or 0.0):.2f} | "
        f"一貫性 {float(consistency.get('consistency_score', 0.0) or 0.0):.2f} | "
        f"判定 {analysis.get('candidate_label', '-')}: {analysis.get('candidate_reason', '-')}"
    )


def _sector_candidate_reason(analysis: dict[str, Any], candidate_label: str) -> str:
    direction = str(analysis.get("vectors", {}).get("current", {}).get("direction", "-"))
    normalized_length = float(analysis.get("normalized_length", 0.0) or 0.0)
    consistency = float(analysis.get("consistency", {}).get("consistency_score", 0.0) or 0.0)
    if candidate_label == "有望":
        return f"方向 {direction} が続き、正規化長 {normalized_length:.2f} と一貫性 {consistency:.2f} が十分です。"
    if candidate_label == "監視":
        return f"改善の兆しはありますが、正規化長 {normalized_length:.2f} か一貫性 {consistency:.2f} はまだ過熱前です。"
    if candidate_label == "失速警戒":
        return f"直近方向 {direction} が弱く、伸びの鈍化を警戒する局面です。"
    return "中心近傍または方向感不足のため、まだ様子見です。"


def _sector_label_badge_html(label: Any) -> str:
    if not label:
        return ""
    return f"<br><span class='sector-label-badge'>{html.escape(str(label))}</span>"


def _sector_base_color(ticker: str) -> str:
    colors = {
        "XLK": "#2563eb",
        "XLF": "#0f766e",
        "XLE": "#b45309",
        "XLI": "#475569",
        "XLP": "#2f855a",
        "XLU": "#7c3aed",
        "XLV": "#0ea5a4",
        "XLY": "#db2777",
        "XLB": "#ca8a04",
    }
    return colors.get(ticker, "#5b6c7d")


def _blend_hex_color(base_hex: str, mix_hex: str, mix_ratio: float) -> str:
    ratio = min(max(float(mix_ratio), 0.0), 1.0)
    base = [int(base_hex[index : index + 2], 16) for index in (1, 3, 5)]
    mix = [int(mix_hex[index : index + 2], 16) for index in (1, 3, 5)]
    blended = [round((base_value * (1.0 - ratio)) + (mix_value * ratio)) for base_value, mix_value in zip(base, mix, strict=False)]
    return "#" + "".join(f"{value:02x}" for value in blended)


def _vector_display_color(dx: float, dy: float) -> str:
    if abs(dy) >= abs(dx):
        return "#2f855a" if dy >= 0 else "#d69e2e"
    return "#3182ce" if dx >= 0 else "#c53030"


def _timestamp_slug(generated_at: str) -> str:
    return generated_at.replace(":", "").replace("T", "_")


def _jp_action(value: str) -> str:
    return action_label_ja(value)


def _jp_risk(value: str) -> str:
    return RISK_LABELS.get(value, value)


def _jp_regime(value: str) -> str:
    return REGIME_LABELS.get(value, value)


def _jp_cycle(value: str) -> str:
    return CYCLE_LABELS.get(value, value)


def _jp_reliability(value: str) -> str:
    return {"high": "高", "medium": "中", "low": "低", "diagnostic": "診断用"}.get(value, value)


def _data_quality_markdown_lines(report: dict[str, Any]) -> list[str]:
    return data_quality_markdown_lines(report)


def _data_quality_html_rows(report: dict[str, Any]) -> list[tuple[str, str]]:
    return data_quality_html_rows(report)


def _execution_mode_html_rows(report: dict[str, Any]) -> list[tuple[str, str]]:
    diagnostics = report.get("fetch_diagnostics") or {}
    summary = diagnostics.get("summary") or {}
    rows: list[tuple[str, str]] = []
    data_mode = summary.get("data_mode_label")
    execution_mode = summary.get("execution_mode")
    if data_mode or execution_mode:
        rows.append(("データモード", str(data_mode or execution_mode)))
    snapshot_observed_at = summary.get("snapshot_observed_at")
    if snapshot_observed_at:
        rows.append(("キャッシュ観測時刻", str(snapshot_observed_at)))
    snapshot_prices_path = summary.get("snapshot_prices_path")
    if snapshot_prices_path:
        rows.append(("キャッシュ価格ファイル", str(snapshot_prices_path)))
    network_access = summary.get("network_access")
    if network_access:
        rows.append(("ネットワーク取得", str(network_access)))
    return rows


def _top_provenance_strip_html(report: dict[str, Any]) -> str:
    provenance = report.get("data_provenance") or {}
    if not isinstance(provenance, dict):
        return ""
    mode = str(provenance.get("data_mode_label") or report.get("data_source", "-"))
    price_date = str(provenance.get("price_basis_date") or provenance.get("latest_observation_date") or "-")
    retrieved_at = _format_provenance_datetime(provenance.get("retrieved_at") or provenance.get("cache_observed_at"))
    live_label = str(
        provenance.get("live_fetch_label") or ("ライブ更新あり" if provenance.get("live_fetch_performed") else "ライブ更新なし")
    )
    freshness = str(provenance.get("freshness_label") or provenance.get("freshness_status") or "-")
    stale_reason = str(provenance.get("stale_reason") or "")
    freshness_text = freshness if not stale_reason or stale_reason == freshness else f"{freshness} / {stale_reason}"
    tone = "danger" if provenance.get("freshness_status") == "stale" else "warn" if mode in {"サンプルデータ", "過去時点再生"} else ""
    chips = [
        ("データモード", mode, tone),
        ("価格基準日", price_date, ""),
        ("取得日時", retrieved_at, ""),
        ("ライブ取得", live_label, ""),
        ("鮮度", freshness_text, tone),
    ]
    return (
        "<div class='provenance-strip'>"
        + "".join(
            f"<div class='provenance-chip {html.escape(chip_tone)}'><strong>{html.escape(label)}</strong><span>{html.escape(value)}</span></div>"
            for label, value, chip_tone in chips
        )
        + "</div>"
    )


def _format_provenance_datetime(value: Any) -> str:
    if not value:
        return "-"
    text = str(value).replace("T", " ")
    if len(text) >= 16:
        return f"{text[:16]} JST"
    return text


def _action_validation_markdown_lines(report: dict[str, Any]) -> list[str]:
    validation = report.get("action_validation") or {}
    lines = ["", "## 判断検証"]
    status = validation.get("status", "not_available")
    lines.append(f"- 状態: {status}")
    if validation.get("reason"):
        lines.append(f"- 理由: {validation.get('reason')}")
    summary = validation.get("action_summary") or {}
    if not summary:
        lines.append("- 要約: 履歴検証はまだ利用できません。")
        return lines
    for action, item in summary.items():
        horizon = (item.get("horizons") or {}).get("13w", {})
        lines.append(
            f"- {_jp_action(str(action))}: 件数 {item.get('count', 0)} / 13週平均 {_display_percent(horizon.get('mean_return'))} / 13週勝率 {_display_percent(horizon.get('win_rate'))} / 最大DD {_display_percent(horizon.get('worst_max_drawdown'))}"
        )
    diagnostics = validation.get("diagnostics") or {}
    if diagnostics:
        lines.append(f"- 買い検討ゾーン後13週マイナス率: {_display_percent(diagnostics.get('buy_window_negative_rate_13w'))}")
        lines.append(f"- 待機後13週大幅上昇率: {_display_percent(diagnostics.get('wait_missed_rally_rate_13w'))}")
    return lines


def _jp_japan_risk_level(value: Any) -> str:
    return {
        "high": "高",
        "moderate": "中",
        "low": "低",
        "unknown": "判定保留",
    }.get(str(value or "unknown"), str(value or "判定保留"))


def _display_number(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if math.isnan(value):
            return "-"
        return f"{value:.4f}"
    return str(value)


def _display_percent(value: Any) -> str:
    if value is None:
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(numeric):
        return "-"
    return f"{numeric:.0%}"


def _display_compact_number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if math.isnan(value):
            return "-"
        text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
        return text or "0"
    return str(value)


def _alert_category_label(value: str) -> str:
    labels = {
        "market": "市場警告",
        "life": "生活影響警告",
        "memo": "補足メモ",
    }
    return labels.get(value, value)


def _alert_severity_label(value: str) -> str:
    labels = {
        "high": "重要",
        "moderate": "注意",
        "low": "監視",
    }
    return labels.get(value, value)


def render_supplement_dashboard_html(report: dict[str, Any], history_entries: list[dict[str, Any]] | None = None) -> str:
    """Render the supplemental report as a dense five-screen design board."""
    sector_payload = report.get("sector_rotation", {})
    sector_context = _build_sector_rotation_context(sector_payload)
    sector_svg = _render_sector_rotation_svg(sector_payload, sector_context)
    sector_structure = sector_payload.get("internal_structure") or report.get("internal_structure", {})
    risk_lines = report.get("risk_lines", {})
    spot_signal = report.get("spot_signal", {})
    recovery_evidence = spot_signal.get("recovery_evidence", {})
    blocker_assessment = spot_signal.get("blocker_assessment", {})
    action_decision = spot_signal.get("action_decision", {})
    candidate = report.get("investment_candidates", {})
    recovery = report.get("recovery_candidates", {})
    regime_leading = report.get("regime_leading_candidates", {})
    domestic_danger = report.get("domestic_danger_context") or {}
    integrated_context = report.get("japan_resident_integrated_risk_context") or {}
    japan_risk = report.get("japan_risk", {})
    threshold_drift = report.get("risk_threshold_drift") or {}
    drift_summary = threshold_drift.get("summary") or {}
    threshold_review = report.get("risk_threshold_review") or {}
    threshold_maintenance = report.get("risk_threshold_maintenance") or {}
    diagnostics = report.get("fetch_diagnostics", {})
    diagnostic_summary = diagnostics.get("summary", {})
    runtime_context = report.get("runtime_context", {})
    history_payload = _build_history_embed_payload(history_entries or [])
    episode_chronicle = report.get("risk_engine_v2_episode_chronicle") or {}

    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else "-"))

    def compact(value: Any) -> str:
        return html.escape(_display_compact_number(value))

    def number(value: Any) -> str:
        return html.escape(_display_number(value))

    def source(name: str) -> str:
        return ""

    def metric(label: str, value: Any, tone: str = "", note: str = "") -> str:
        cls = f" metric-{tone}" if tone else ""
        note_html = f"<small>{esc(note)}</small>" if note else ""
        return f'<div class="metric{cls}"><span>{esc(label)}</span><b>{value}</b>{note_html}</div>'

    def status(text: Any, tone: str = "good") -> str:
        return f'<span class="status status-{tone}">{esc(text)}</span>'

    def signal_status(text: Any) -> str:
        label = str(text if text is not None else "-")
        if any(token in label for token in ("警戒", "危険", "悪化", "注意", "下落")):
            tone = "warn"
        elif any(token in label for token in ("中立", "監視", "様子見")):
            tone = "neutral"
        elif any(token in label for token in ("通常", "安全", "良好")):
            tone = "good"
        else:
            tone = "neutral"
        return status(label, tone)

    def table(headers: list[str], rows: list[list[Any]], compact_table: bool = True) -> str:
        head = "".join(f"<th>{esc(header)}</th>" for header in headers)
        if rows:
            body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
        else:
            body = f'<tr><td colspan="{len(headers)}">有効データなし</td></tr>'
        cls = "table compact" if compact_table else "table"
        return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'

    def mini_nav(active: str) -> str:
        icons = {
            "history": "<svg viewBox='0 0 16 16'><path d='M8 3v5l3 2'/><circle cx='8' cy='8' r='6'/></svg>",
            "decision": "<svg viewBox='0 0 16 16'><path d='M4 8l3 3 5-6'/><circle cx='8' cy='8' r='6'/></svg>",
            "sector": "<svg viewBox='0 0 16 16'><path d='M3 11h10M3 8h7M3 5h4'/><path d='M11 4l2 2-2 2'/></svg>",
            "market": "<svg viewBox='0 0 16 16'><path d='M3 12V4M3 12h10'/><path d='M5 10l2-3 2 2 3-5'/></svg>",
            "audit": "<svg viewBox='0 0 16 16'><path d='M5 3h6l2 2v8H3V3h2z'/><path d='M5 7h6M5 10h6'/></svg>",
        }
        items = [("履歴", "history"), ("判定", "decision"), ("セクター", "sector"), ("市場監視", "market"), ("監査", "audit")]
        tab_header = (
            "<div class='mini-nav-title'>"
            "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M6 7h12M6 12h12M6 17h12'/><path d='M3 5h18v14H3z'/></svg>"
            "<b>画面切替</b>"
            "</div>"
        )
        return (
            '<nav class="mini-nav" aria-label="画面切替">'
            + tab_header
            + "".join(
                f'<label class="{"active" if key == active else ""}" for="view-{key}"><span>{icons[key]}</span>{label}</label>'
                for label, key in items
            )
            + "</nav>"
        )

    def ticker_cell(ticker: Any, name: Any = None) -> str:
        label = esc(ticker)
        name_text = esc(name if name is not None else ticker)
        return f"<b>{label}</b><small>{name_text}</small>"

    def sector_board_svg() -> str:
        rows = sector_context.get("rows", [])
        if not rows:
            return "<div>有効データなし</div>"
        phase_slots = {
            "先導": [(250, 70), (294, 102), (224, 112)],
            "改善": [(88, 84), (126, 128), (58, 150)],
            "鈍化": [(252, 220), (300, 202), (218, 236)],
            "出遅れ": [(70, 232), (112, 204), (48, 194)],
        }
        used: dict[str, int] = {}
        colors = {"先導": "#087d75", "改善": "#1e9a73", "鈍化": "#d98200", "出遅れ": "#cf3f49"}
        points: list[str] = []
        labels: list[str] = []
        for row in rows[:10]:
            phase = str(row.get("rotation_phase_ja", "改善"))
            slot_list = phase_slots.get(phase, phase_slots["改善"])
            index = used.get(phase, 0)
            used[phase] = index + 1
            base_x, base_y = slot_list[index % len(slot_list)]
            jitter = (index // len(slot_list)) * 9
            x = base_x + jitter
            y = base_y - jitter
            ticker = esc(row.get("ticker", "-"))
            title = esc(f"{row.get('ticker', '-')} {row.get('sector_name_ja', '-')} {row.get('return_12w', '-')}")
            color = colors.get(phase, "#087d75")
            points.append(
                f"<circle cx='{x}' cy='{y}' r='5.3' fill='{color}' stroke='#ffffff' stroke-width='1.2'><title>{title}</title></circle>"
            )
            labels.append(f"<text x='{x + 8}' y='{y - 7}' font-size='9.5' font-weight='700' fill='#273642'>{ticker}</text>")
        return (
            "<svg viewBox='0 0 360 292' role='img' aria-label='セクターローテーション象限図'>"
            "<rect x='8' y='8' width='344' height='276' rx='10' fill='#ffffff' stroke='#dce6eb'/>"
            "<line x1='180' y1='8' x2='180' y2='284' stroke='#dce6eb'/>"
            "<line x1='8' y1='146' x2='352' y2='146' stroke='#dce6eb'/>"
            "<text x='24' y='34' font-size='18' font-weight='900' fill='#1e9a73'>改善</text>"
            "<text x='336' y='34' text-anchor='end' font-size='18' font-weight='900' fill='#08806f'>先導</text>"
            "<text x='336' y='268' text-anchor='end' font-size='16' font-weight='900' fill='#d98200'>鈍化</text>"
            "<text x='24' y='268' font-size='16' font-weight='900' fill='#cf3f49'>出遅れ</text>"
            "<path d='M98 146 A82 82 0 0 1 180 64' fill='none' stroke='#b7bdc2' stroke-width='11' opacity='.58' stroke-linecap='round'/>"
            "<path d='M180 64 A82 82 0 0 1 262 146' fill='none' stroke='#b7bdc2' stroke-width='11' opacity='.58' stroke-linecap='round'/>"
            "<path d='M262 146 A82 82 0 0 1 180 228' fill='none' stroke='#b7bdc2' stroke-width='11' opacity='.58' stroke-linecap='round'/>"
            "<path d='M180 228 A82 82 0 0 1 98 146' fill='none' stroke='#b7bdc2' stroke-width='11' opacity='.58' stroke-linecap='round'/>"
            "<polygon points='250,96 229,90 243,76' fill='#b7bdc2' opacity='.66'/>"
            "<polygon points='230,214 236,193 250,209' fill='#b7bdc2' opacity='.66'/>"
            "<polygon points='110,196 131,202 116,216' fill='#b7bdc2' opacity='.66'/>"
            "<polygon points='130,78 124,99 110,83' fill='#b7bdc2' opacity='.66'/>" + "".join(points) + "".join(labels) + "</svg>"
        )

    sector_svg = sector_board_svg()

    latest_history = (history_payload.get("history") or [{}])[-1]
    latest_regime = latest_history.get("regime", {}) if isinstance(latest_history, dict) else {}
    history_meta = history_payload.get("meta", {})
    generated_at = esc(report.get("generated_at", "-"))
    source_name = esc(report.get("data_source", "-"))
    reliability = report.get("data_reliability", {})
    quality_limit = esc(_jp_action(str(reliability.get("max_action", "buy_window"))))
    quality_live_ratio = esc(_display_percent(reliability.get("live_ratio")))
    quality_cap_note = esc(", ".join(action_decision.get("cap_reason", [])) or reliability.get("reason_code", "-"))

    risk_line_rows = [
        [
            ticker_cell(row.get("ticker"), row.get("ticker_name_ja", row.get("ticker"))),
            status(row.get("line_level_label", "-"), _risk_label_tone(row.get("line_level_label"))),
            number(row.get("current")),
            _format_risk_threshold_beginner_html(row.get("warning_line")),
            _format_risk_threshold_beginner_html(row.get("danger_line")),
            _format_risk_threshold_beginner_html(row.get("extreme_line")),
            esc(_risk_accepted_rule_summary(row)),
            esc(_risk_diagnostic_rule_summary(row)),
        ]
        for row in risk_lines.get("indicators", [])
    ]
    candidate_rows = [
        [
            esc(item.get("ticker", "-")),
            esc(item.get("label", "-")),
            esc(item.get("reason", "-")),
        ]
        for item in candidate.get("candidate_tickers", [])
    ]
    recovery_rows = [
        [
            esc(item.get("ticker", "-")),
            esc(item.get("label", "-")),
            esc(item.get("reason", "-")),
        ]
        for item in recovery.get("candidate_tickers", [])
    ]
    regime_leading_rows = [
        [
            esc(item.get("ticker", "-")),
            esc(item.get("label", "-")),
            esc(item.get("reason", "-")),
        ]
        for item in regime_leading.get("candidate_tickers", [])
    ]
    sector_rows = [
        [
            esc(row.get("rank")),
            esc(row.get("ticker")),
            esc(row.get("sector_name_ja")),
            esc(row.get("return_12w")),
            status(
                row.get("rotation_phase_ja", "-"),
                "bad" if row.get("rotation_phase_ja") == "出遅れ" else "warn" if row.get("rotation_phase_ja") == "鈍化" else "good",
            ),
        ]
        for row in sector_context.get("rows", [])
    ]
    asset_rows = [
        [
            esc(row.get("asset_class")),
            ticker_cell(row.get("ticker"), row.get("ticker_name_ja")),
            esc(row.get("momentum_12w")),
            esc(row.get("annualized_volatility")),
            esc(row.get("max_drawdown")),
        ]
        for row in report.get("asset_compare", [])
    ]
    credit_rows = [
        [
            ticker_cell(row.get("ticker"), row.get("ticker_name_ja")),
            esc(row.get("current")),
            esc(row.get("change_1w")),
            esc(row.get("change_4w")),
            esc(row.get("change_12w")),
            esc(row.get("zscore")),
            status(row.get("signal_label", "-"), "bad" if "警戒" in str(row.get("signal_label", "")) else "good"),
        ]
        for row in report.get("credit_monitor", [])
    ]
    inflation_rows = [
        [
            ticker_cell(row.get("ticker"), row.get("ticker_name_ja")),
            esc(row.get("current")),
            esc(row.get("change_1w")),
            esc(row.get("change_4w")),
            esc(row.get("change_12w")),
            esc(row.get("zscore")),
            status(row.get("signal_label", "-"), "bad" if "警戒" in str(row.get("signal_label", "")) else "good"),
        ]
        for row in report.get("inflation_monitor", [])
    ]
    yen_asset_rows = [
        [
            esc(row.get("asset_class")),
            ticker_cell(row.get("ticker"), row.get("ticker_name_ja")),
            esc(row.get("usd_return_4w")),
            esc(row.get("jpy_return_4w")),
            esc(row.get("fx_contribution_4w")),
            esc(row.get("jpy_max_drawdown")),
            signal_status(row.get("signal_label")),
        ]
        for row in japan_risk.get("foreign_assets", [])
    ]
    usd_jpy = japan_risk.get("usd_jpy", {})
    fx_rows = (
        [
            [
                ticker_cell(usd_jpy.get("ticker", "USDJPY=X"), usd_jpy.get("ticker_name_ja", "米ドル円")),
                number(usd_jpy.get("current")),
                number(usd_jpy.get("change_1w")),
                number(usd_jpy.get("change_4w")),
                number(usd_jpy.get("change_12w")),
                signal_status(usd_jpy.get("signal_label", "-")),
            ]
        ]
        if usd_jpy
        else []
    )
    availability_rows = [
        [
            ticker_cell(entry.get("requested_ticker"), entry.get("requested_ticker_name_ja", entry.get("requested_ticker"))),
            status(STATUS_LABELS.get(entry.get("status"), entry.get("status")), "good" if entry.get("status") == "ok" else "warn"),
            ticker_cell(entry.get("used_ticker") or "-", entry.get("used_ticker_name_ja") or "-"),
            esc(entry.get("message", "-")),
        ]
        for entry in report.get("data_availability", [])
    ]
    diagnostic_rows = [
        ["実行形態", "配布 exe" if runtime_context.get("is_frozen") else "Python 実行"],
        ["実行ファイル", runtime_context.get("python_executable", "-")],
        ["作業フォルダ", runtime_context.get("working_directory", "-")],
        ["取得ソース", diagnostic_summary.get("source", report.get("data_source", "-"))],
        *_execution_mode_html_rows(report),
        *_data_quality_html_rows(report),
        ["失敗試行数", diagnostic_summary.get("failed_attempt_count", 0)],
        ["接続不良疑い", "あり" if diagnostic_summary.get("suspected_network_issue") else "なし"],
        ["代表エラー", diagnostics.get("failure_samples", ["記録なし"])[0] if diagnostics.get("failure_samples") else "記録なし"],
    ]
    alert_cards = (
        "".join(
            f'<div class="warn-card"><b>{esc(alert.get("title", "-"))}</b><em>{esc(_alert_category_label(alert.get("category", "memo")))} / {esc(_alert_severity_label(alert.get("severity", "low")))}</em><p>{esc(alert.get("message", "-"))}</p></div>'
            for alert in report.get("alerts", [])
        )
        or '<div class="empty-note">重要な警告はありません。</div>'
    )
    warning_items = "".join(f"<li>{esc(warning)}</li>" for warning in report.get("warnings", [])) or "<li>重要な警告はありません。</li>"
    domestic_danger_panel = _domestic_danger_panel_html(domestic_danger, table, esc, source)
    integrated_context_panel = _japan_resident_integrated_context_panel_html(integrated_context, table, esc, source)
    hindenburg_omen_panel = _hindenburg_omen_panel_html(report.get("hindenburg_omen_context") or {}, esc)
    chronicle_page = episode_chronicle.get("page_filename")
    chronicle_ready = (
        episode_chronicle.get("status") == "ready"
        and episode_chronicle.get("freshness_status") == "current"
        and episode_chronicle.get("policy_status") == "diagnostic_only_not_promoted"
        and episode_chronicle.get("affects_final_action") is False
        and episode_chronicle.get("promotion_allowed") is False
        and isinstance(chronicle_page, str)
        and Path(chronicle_page).name == chronicle_page
    )
    if chronicle_ready:
        chronicle_action = (
            f'<a class="chronicle-launch" href="{esc(chronicle_page)}" target="_blank" rel="noopener">'
            '市場警戒年代記を別窓で開く <span aria-hidden="true">↗</span></a>'
        )
        chronicle_state = '<span class="chronicle-state ready">閲覧可能</span>'
    else:
        chronicle_action = '<span class="chronicle-launch disabled" aria-disabled="true">市場警戒年代記は現在開けません</span>'
        chronicle_state = '<span class="chronicle-state unavailable">未生成・更新待ち</span>'
    chronicle_reason = episode_chronicle.get("reason") or (
        "読み取り専用の歴史・証拠画面です。本体判断と売買候補には影響しません。"
        if chronicle_ready
        else "証拠連鎖の検証後に利用可能になります。"
    )
    chronicle_panel = f"""
      <div class="chronicle-launch-layout">
        <div class="chronicle-copy">
          <div class="chronicle-kicker">READ-ONLY CHRONICLE {chronicle_state}</div>
          <p>アラート前後の価格、警戒段階、証拠、評価をエピソード単位で読み返します。年では区切らず、同じイベントIDの進行中記録を更新します。</p>
          <small>{esc(chronicle_reason)}</small>
        </div>
        <dl class="chronicle-stats">
          <div><dt>全エピソード</dt><dd>{esc(episode_chronicle.get('episode_count', 0))}</dd></div>
          <div><dt>成熟済み</dt><dd>{esc(episode_chronicle.get('mature_count', 0))}</dd></div>
          <div><dt>進行中</dt><dd>{esc(episode_chronicle.get('pending_count', 0))}</dd></div>
        </dl>
        <div class="chronicle-latest"><span>最新の章</span><strong>{esc(episode_chronicle.get('latest_event_title', '-'))}</strong><small>生成: {esc(episode_chronicle.get('generated_at', '-'))}</small></div>
        <div class="chronicle-action-wrap">{chronicle_action}</div>
      </div>
    """

    def localize_signal_value(value: Any) -> str:
        text = str(value)
        mapping = {
            "building": "形成中",
            "confirmed": "確認済み",
            "weak": "弱い",
            "caution": "注意",
            "neutral": "中立",
            "normal": "通常",
            "watch": "監視",
            "review": "要確認",
            "stable": "安定",
            "transition": "移行局面",
            "upswing": "上昇局面",
            "risk_on": "リスクオン",
            "risk_off": "リスクオフ",
            "inflation_shock": "インフレショック",
            "downswing": "下落局面",
            "block": "強い警戒",
            "high": "高い",
            "moderate": "中程度",
            "low": "低い",
            "extreme": "非常に高い",
            "buy_window": "買い検討ゾーン",
            "wait": "待機",
            "diagnostic_only": "診断用",
        }
        return mapping.get(text, text)

    def localize_decision_reason(reason: Any) -> str:
        text = str(reason)
        exact = {
            "市場レジームは transition です。": "市場レジームは移行局面です。",
            "サイクル位相は upswing です。": "サイクル位相は上昇局面です。",
        }
        if text in exact:
            return exact[text]
        replacements = [
            ("transition と", "移行局面と"),
            ("upswing と", "上昇局面と"),
            ("risk_on と", "リスクオンと"),
            ("risk_off と", "リスクオフと"),
            (" transition ", " 移行局面 "),
            (" upswing ", " 上昇局面 "),
            (" risk_on ", " リスクオン "),
            (" risk_off ", " リスクオフ "),
            ("transition", "移行局面"),
            ("upswing", "上昇局面"),
            ("inflation_shock", "インフレショック"),
            ("downswing", "下落局面"),
            ("building", "形成中"),
            ("caution", "注意"),
            ("neutral", "中立"),
            ("block", "強い警戒"),
            ("high", "高い"),
            ("moderate", "中程度"),
            ("low", "低い"),
        ]
        for src, dst in replacements:
            text = text.replace(src, dst)
        return text

    def trend_icon(direction: str) -> str:
        if direction == "down":
            path = "M4 5l7 7M11 7v5H6"
            label = "下降"
        else:
            path = "M4 11l7-7M7 4h4v4"
            label = "上昇"
        return f"<svg class='trend-icon trend-{direction}' viewBox='0 0 16 16' role='img' aria-label='{label}'>" f"<path d='{path}'/></svg>"

    decision_rationale = (
        "".join(f"<li>{esc(localize_decision_reason(reason))}</li>" for reason in spot_signal.get("rationale", []))
        or "<li>追加理由はありません。</li>"
    )
    risk_reason_items = (
        "".join(f"<li>{esc(localize_decision_reason(reason))}</li>" for reason in risk_lines.get("reasons", []))
        or "<li>追加理由はありません。</li>"
    )
    analogue_rows = [
        [esc(row.get("end_date")), esc(row.get("similarity")), esc(row.get("forward_12w_return"))] for row in report.get("analogues", [])
    ]
    if not analogue_rows:
        analogue_rows = [["十分に近い類似局面は抽出されませんでした。", "", ""]]
    phase_counts = {
        "先導": sum(1 for row in sector_context.get("rows", []) if row.get("rotation_phase_ja") == "先導"),
        "改善": sum(1 for row in sector_context.get("rows", []) if row.get("rotation_phase_ja") == "改善"),
        "鈍化": sum(1 for row in sector_context.get("rows", []) if row.get("rotation_phase_ja") == "鈍化"),
        "出遅れ": sum(1 for row in sector_context.get("rows", []) if row.get("rotation_phase_ja") == "出遅れ"),
    }
    warning_sectors = sector_payload.get("peakout_sectors") or report.get("peakout_sectors", [])
    warning_sector = warning_sectors[0].get("ticker") if warning_sectors else "-"
    _legacy_board_values = (
        sector_structure,
        recovery_evidence,
        blocker_assessment,
        sector_svg,
        latest_regime,
        recovery_rows,
        regime_leading_rows,
        sector_rows,
        credit_rows,
        inflation_rows,
        yen_asset_rows,
        fx_rows,
        alert_cards,
        decision_rationale,
        phase_counts,
        warning_sector,
    )

    style = """
    :root {
      --bg:#fbfcfd; --paper:#ffffff; --ink:#111922; --muted:#5f6c77; --line:#8fb4c4; --line2:#dbe6eb;
      --teal:#0a7f7c; --teal-dark:#00666d; --teal-soft:#e7f5f3; --green:#13865d; --orange:#f3a42c; --red:#d6525b;
      --warn-soft:#fff6e6; --bad-soft:#ffe9eb; --shadow:0 5px 18px rgba(26,62,76,.055);
    }
    * { box-sizing:border-box; }
    body { margin:0; background:linear-gradient(180deg,#fff 0,#fbfcfd 74%,#f8fbfc 100%); color:var(--ink); font-family:'Yu Gothic UI', Meiryo, sans-serif; letter-spacing:0; }
    a { color:inherit; text-decoration:none; }
    .wrap { width:calc(100vw - 20px); max-width:1518px; margin:0 auto; padding:9px 0 20px; }
    .board-head { display:flex; align-items:center; justify-content:space-between; gap:18px; height:34px; margin:0 0 4px; }
    h1 { margin:0; font-size:25px; line-height:1.05; font-weight:900; }
    .subhead { margin-left:14px; font-size:14px; font-weight:800; color:#1f2f3a; }
    .legend { display:flex; gap:17px; align-items:center; color:#25333f; font-size:12px; font-weight:700; white-space:nowrap; }
    .legend i { display:inline-block; width:14px; height:14px; margin-right:6px; vertical-align:-2px; border-radius:1px; }
    .top-row { display:grid; grid-template-columns:1fr 1.09fr; gap:12px; }
    .bottom-row { display:grid; grid-template-columns:.91fr 1.25fr 1.02fr; gap:12px; margin-top:12px; }
    .screen { min-width:0; border:1.25px solid var(--line); border-radius:7px; background:rgba(255,255,255,.98); box-shadow:var(--shadow); overflow:hidden; }
    .top-row .screen { height:386px; }
    .bottom-row .screen { height:518px; }
    .screen-head { display:flex; align-items:center; gap:9px; min-height:36px; padding:0 10px; border-bottom:1px solid var(--line2); background:linear-gradient(180deg,#fff,#f9fbfc); }
    .screen-no { display:grid; place-items:center; width:34px; height:30px; margin-left:-10px; border-radius:0 6px 6px 0; background:var(--teal-dark); color:#fff; font-size:20px; font-weight:900; }
    .screen-title { font-size:17px; color:var(--teal-dark); font-weight:900; }
    .source { color:#52616e; font-size:10px; font-weight:700; }
    .screen-tools { margin-left:auto; display:flex; align-items:center; gap:8px; color:#3e4d58; font-size:10px; white-space:nowrap; }
    .tool-btn { padding:4px 8px; border:1px solid #9ec3cf; border-radius:5px; color:var(--teal-dark); background:#fff; font-weight:800; }
    .screen-body { display:grid; grid-template-columns:62px minmax(0,1fr); height:calc(100% - 36px); min-height:0; }
    .bottom-row .screen-body { min-height:0; }
    .mini-nav { border-right:1px solid var(--line2); padding:38px 0 8px; background:#fbfdfe; }
    .mini-nav label { display:flex; align-items:center; gap:6px; height:28px; padding:0 8px; color:#263743; font-size:10px; font-weight:800; cursor:pointer; }
    .mini-nav span { display:grid; place-items:center; width:14px; height:14px; color:#203541; }
    .mini-nav svg { width:13px; height:13px; fill:none; stroke:currentColor; stroke-width:1.55; stroke-linecap:round; stroke-linejoin:round; }
    .mini-nav label.active { color:var(--teal-dark); background:#e8f5f4; box-shadow:inset 4px 0 0 var(--teal); }
    .mini-nav label.active span { color:var(--teal); }
    .content { min-width:0; padding:10px 10px 9px; overflow:hidden; scrollbar-width:thin; }
    .card { border:1px solid var(--line2); border-radius:6px; background:#fff; padding:8px; min-width:0; }
    .card + .card { margin-top:8px; }
    .card h3 { display:flex; justify-content:space-between; gap:6px; align-items:center; margin:0 0 7px; font-size:12px; line-height:1.15; }
    .card p { margin:0; color:#53616d; font-size:9.5px; line-height:1.45; }
    .metrics { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:8px; margin-bottom:8px; }
    .metric { min-width:0; border:1px solid var(--line2); border-radius:6px; background:#fff; padding:7px 9px; }
    .metric span { display:block; color:#596671; font-size:9.2px; font-weight:800; }
    .metric b { display:block; margin-top:3px; color:#111922; font-size:16px; line-height:1.08; overflow-wrap:anywhere; }
    .metric small { display:block; margin-top:2px; color:#64727e; font-size:9px; }
    .metric-good b { color:var(--teal-dark); }
    .metric-warn b { color:#d87900; }
    .metric-bad b { color:var(--red); }
    .split { display:grid; grid-template-columns:minmax(0,1fr) 184px; gap:9px; align-items:start; }
    .split-even { display:grid; grid-template-columns:1fr 1fr; gap:8px; align-items:start; }
    .split-3 { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; align-items:start; }
    .chart { height:165px; border:1px solid var(--line2); border-radius:6px; background:#fff; overflow:hidden; }
    .chart svg { display:block; width:100%; height:100%; }
    .chart-legend { display:flex; justify-content:center; gap:20px; margin:-1px 0 5px; color:#53616d; font-size:9px; font-weight:700; }
    .chart-legend i { display:inline-block; width:10px; height:10px; margin-right:4px; vertical-align:-1px; opacity:.55; }
    .range-row { display:grid; grid-template-columns:110px 1fr 94px; gap:8px; align-items:center; margin-top:7px; color:#52616e; font-size:9px; }
    .range-row code { border:1px solid var(--line2); border-radius:4px; padding:4px 6px; background:#fff; color:#24313b; font-family:inherit; }
    .chart-count { display:block; margin-top:4px; text-align:center; color:#53616d; font-size:9px; }
    input[type=range] { accent-color:var(--teal); }
    .table-wrap { overflow:auto; max-height:190px; border:1px solid var(--line2); border-radius:5px; scrollbar-width:thin; }
    .table { width:100%; border-collapse:collapse; background:#fff; font-size:8.6px; }
    .table th, .table td { border-bottom:1px solid #e7eef2; border-right:1px solid #edf2f5; padding:3.4px 5px; text-align:left; vertical-align:top; white-space:nowrap; }
    .table th { position:sticky; top:0; z-index:1; background:#f7fafb; color:#4b5964; font-size:8.4px; font-weight:900; }
    .table td small { display:block; color:#71808c; font-size:7.8px; line-height:1.1; }
    .status { display:inline-block; min-width:34px; padding:2px 5px; border-radius:4px; text-align:center; font-size:8.5px; font-weight:900; }
    .status-good, .status-ok, .status-safe { background:#e9f6ef; color:#0f7d54; }
    .status-warn, .status-caution, .status-neutral { background:#fff3dd; color:#c46d00; }
    .status-bad, .status-danger { background:#ffe6e8; color:#c9313a; }
    .note-list, .compact-list { margin:0; padding-left:15px; color:#394854; font-size:9.5px; line-height:1.48; }
    .note-list li + li, .compact-list li + li { margin-top:3px; }
    .decision-matrix { display:grid; grid-template-columns:1.08fr .92fr; gap:9px; }
    .flow { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:7px; margin-bottom:9px; }
    .flow div { border:1px solid var(--line2); border-radius:5px; padding:7px; background:#fff; }
    .flow b { display:block; color:#52616e; font-size:8.6px; }
    .flow span { display:block; margin-top:3px; color:#101820; font-size:10.5px; font-weight:900; }
    .candidate-combo { margin-top:9px; }
    .candidate-combo h4 { margin:0 0 6px; color:#102033; font-size:11px; line-height:1.2; }
    .candidate-combo h4:not(:first-child) { margin-top:12px; padding-top:10px; border-top:1px solid var(--line2); }
    .candidate-combo .table-wrap { margin-top:0; }
    .risk-detail-block { margin-top:12px; padding-top:10px; border-top:1px solid var(--line2); }
    .risk-detail-block h4 { margin:0 0 7px; font-size:11px; line-height:1.2; }
    .sector-grid { display:grid; grid-template-columns:minmax(0,1.48fr) minmax(138px,.62fr); gap:8px; }
    .sector-figure { height:248px; overflow:hidden; }
    .sector-figure svg { width:100%; height:100%; }
    .structure-strip { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:7px; margin-top:9px; }
    .market-grid { display:grid; grid-template-columns:1.06fr .94fr; gap:9px; }
    .warn-card { border:1px solid #efc06f; background:#fff7e8; border-radius:6px; padding:8px; color:#4a3320; }
    .warn-card + .warn-card { margin-top:6px; }
    .warn-card b { display:block; color:#a25500; font-size:11px; }
    .warn-card em { display:block; margin-top:2px; color:#c06b00; font-size:8.5px; font-style:normal; font-weight:900; }
    .warn-card p { margin-top:5px; color:#5a4632; }
    .empty-note { border:1px dashed var(--line2); border-radius:7px; padding:12px; color:#60707c; font-size:11px; }
    .audit-grid { display:grid; grid-template-columns:130px minmax(0,1fr); gap:10px; }
    .drift-list { display:grid; gap:6px; }
    .drift-list div { display:flex; justify-content:space-between; border:1px solid var(--line2); border-radius:5px; padding:6px 8px; font-size:10px; font-weight:900; }
    .review-targets { display:flex; flex-wrap:wrap; gap:5px; margin-top:8px; }
    .review-targets span { padding:4px 6px; border-radius:5px; background:#fff3dd; color:#b15e00; font-size:10px; font-weight:900; }
    .audit-table .table-wrap { max-height:302px; }
    #history .metric b { font-size:15px; }
    #history .metrics:last-child .metric { padding:6px 9px; }
    #history .metrics:last-child .metric b { font-size:10px; font-weight:700; }
    #decision .table-wrap { max-height:104px; }
    #decision .table td:nth-child(3), #decision .table th:nth-child(3) { min-width:150px; white-space:normal; }
    #decision .compact-list { max-height:101px; overflow:auto; scrollbar-width:thin; }
    #sector .table-wrap { max-height:248px !important; }
    #sector .table { font-size:8px; }
    #sector .table th, #sector .table td { padding:3px 4px; }
    #sector .structure-strip { grid-template-columns:repeat(6,minmax(0,1fr)); gap:5px; }
    #sector .structure-strip .metric { padding:5px 6px; }
    #sector .structure-strip .metric b { font-size:11px; }
    #market .table-wrap { max-height:101px; }
    #market .card { padding:7px; }
    #market .warn-card { padding:7px; }
    #market .split-even { margin-top:7px !important; }
    #market .market-grid { gap:7px; }
    #audit .table-wrap { max-height:286px; }
    #market .content, #audit .content { transform:scale(.92); transform-origin:top left; width:108.7%; height:108.7%; }
    #audit .metrics { gap:6px; }
    #audit .metric { padding:6px 7px; }
    #market .warn-card p { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
    #sector .sector-kpis { grid-template-columns:.7fr .7fr .7fr .7fr .82fr 1.02fr; }
    .sector-kpis .metric b { display:flex; align-items:center; gap:7px; }
    .trend-icon { width:20px; height:20px; flex:0 0 auto; fill:none; stroke:currentColor; stroke-width:3.2; stroke-linecap:round; stroke-linejoin:round; filter:drop-shadow(0 1px 0 rgba(255,255,255,.75)); }
    #sector .metric b, #audit .metric b { font-size:14px; overflow-wrap:normal; word-break:normal; }
    .view-radio { position:absolute; opacity:0; pointer-events:none; }
    .top-actions { display:flex; justify-content:flex-end; gap:12px; margin:8px 0 12px; }
    .top-actions .tool-btn { display:inline-flex; align-items:center; justify-content:center; min-height:44px; padding:0 18px; border:1.5px solid var(--line); border-radius:7px; background:#fff; color:var(--teal-dark); font-size:18px; font-weight:900; }
    .top-actions .tool-btn:hover { background:var(--teal-soft); box-shadow:inset 0 -4px 0 var(--teal); }
    #view-history:checked ~ .wrap #history,
    #view-decision:checked ~ .wrap #decision,
    #view-sector:checked ~ .wrap #sector,
    #view-market:checked ~ .wrap #market,
    #view-audit:checked ~ .wrap #audit { display:block; }
    .top-row, .bottom-row { display:contents; margin:0; }
    .screen { display:none; height:auto !important; min-height:calc(100vh - 122px); }
    .wrap { max-width:1640px; padding-bottom:40px; }
    .board-head { height:42px; }
    h1 { font-size:34px; }
    .subhead { font-size:18px; }
    .legend { font-size:16px; }
    .legend i { width:18px; height:18px; }
    .screen-head { min-height:64px; padding:0 18px; gap:16px; }
    .screen-no { width:58px; height:52px; margin-left:-18px; font-size:34px; border-radius:0 8px 8px 0; }
    .screen-title { font-size:30px; }
    .source { font-size:15px; }
    .screen-tools { font-size:15px; }
    .tool-btn { padding:8px 13px; font-size:15px; }
    .screen-body { grid-template-columns:124px minmax(0,1fr); height:auto; min-height:calc(100vh - 198px); }
    .mini-nav { padding:48px 0 16px; }
    .mini-nav label { height:50px; gap:12px; padding:0 16px; font-size:17px; }
    .mini-nav span { width:24px; height:24px; }
    .mini-nav svg { width:23px; height:23px; stroke-width:1.7; }
    .content { padding:20px; overflow:visible; }
    .metrics { gap:14px; margin-bottom:16px; }
    .metric { padding:15px 17px; border-radius:8px; }
    .metric span { font-size:15px; }
    .metric b { margin-top:7px; font-size:30px; }
    .metric small { font-size:14px; }
    .card { padding:16px; border-radius:8px; }
    .card + .card { margin-top:16px; }
    .card h3 { margin-bottom:13px; font-size:21px; }
    .card p { font-size:16px; line-height:1.65; }
    .split { grid-template-columns:minmax(0,1fr) 350px; gap:16px; }
    .split-even, .market-grid, .decision-matrix { gap:16px; }
    .chart { height:350px; }
    .chart-legend { gap:28px; margin:0 0 8px; font-size:14px; }
    .chart-legend i { width:16px; height:16px; margin-right:6px; }
    .range-row { grid-template-columns:180px 1fr 160px; gap:14px; margin-top:12px; font-size:15px; }
    .range-row code { padding:8px 10px; }
    .chart-count { margin-top:8px; font-size:15px; }
    .note-list, .compact-list { font-size:16px; line-height:1.7; padding-left:24px; }
    .flow { gap:12px; margin-bottom:14px; }
    .flow div { padding:14px; border-radius:8px; }
    .flow b { font-size:14px; }
    .flow span { font-size:18px; }
    .candidate-combo { margin-top:16px; }
    .candidate-combo h4 { margin-bottom:10px; font-size:19px; }
    .candidate-combo h4:not(:first-child) { margin-top:18px; padding-top:16px; }
    .risk-detail-block { margin-top:18px; padding-top:16px; }
    .risk-detail-block h4 { margin-bottom:11px; font-size:19px; }
    .table-wrap { max-height:none; border-radius:7px; }
    .table { font-size:15px; }
    .table th, .table td { padding:8px 10px; }
    .table th { font-size:14px; }
    .table td small { font-size:12px; line-height:1.25; }
    .status { min-width:58px; padding:4px 8px; font-size:14px; }
    .sector-grid { grid-template-columns:minmax(0,1.4fr) minmax(320px,.7fr); gap:16px; }
    .sector-figure { height:540px; }
    .structure-strip { gap:10px; margin-top:14px; }
    .warn-card { padding:15px; border-radius:8px; }
    .warn-card + .warn-card { margin-top:12px; }
    .warn-card b { font-size:18px; }
    .warn-card em { font-size:14px; }
    .warn-card p { margin-top:9px; }
    .audit-grid { grid-template-columns:230px minmax(0,1fr); gap:18px; }
    .drift-list { gap:10px; }
    .drift-list div { padding:11px 13px; font-size:16px; }
    .review-targets span { padding:7px 10px; font-size:14px; }
    #history .metric b { font-size:28px; }
    #history .metrics:last-child .metric b { font-size:18px; }
    #history .history-chart-card .chart { height:430px; }
    #history .history-reading { margin-top:16px; }
    #history .history-reading .note-list { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px 24px; }
    #decision .table-wrap, #decision .compact-list, #sector .table-wrap, #market .table-wrap, #audit .table-wrap { max-height:none !important; }
    #decision .table td:nth-child(3), #decision .table th:nth-child(3) { min-width:250px; }
    #market .content, #audit .content { transform:none; width:auto; height:auto; }
    #market .card, #market .warn-card, #audit .metric, #sector .structure-strip .metric { padding:15px 17px; }
    #market .warn-card p { display:block; overflow:visible; }
    #sector .sector-kpis { grid-template-columns:repeat(6,minmax(0,1fr)); }
    #sector .table { font-size:15px; }
    #sector .table th, #sector .table td { padding:8px 10px; }
    #sector .structure-strip .metric b, #sector .metric b, #audit .metric b { font-size:26px; }
    #sector .sector-kpis .metric b { align-items:center; gap:8px; }
    #sector .trend-icon { width:28px; height:28px; stroke-width:3.6; }
    #audit .content > .metrics:first-child { grid-template-columns:repeat(5,minmax(0,1fr)); }
    #audit .content > .metrics:first-child .metric { padding:12px 13px; }
    #audit .content > .metrics:first-child .metric b { font-size:15px; line-height:1.2; overflow-wrap:anywhere; word-break:break-word; }
    #audit .content > .metrics:first-child .metric span { font-size:13px; line-height:1.2; }
    #view-history:checked ~ .wrap #history,
    #view-decision:checked ~ .wrap #decision,
    #view-sector:checked ~ .wrap #sector,
    #view-market:checked ~ .wrap #market,
    #view-audit:checked ~ .wrap #audit { display:grid; }
    .screen { grid-template-columns:124px minmax(0,1fr); grid-template-rows:auto 1fr; }
    .screen-head { grid-column:2; grid-row:1; }
    .screen-body { display:contents; min-height:0; height:auto; }
    .mini-nav { grid-column:1; grid-row:1 / span 2; padding-top:0; }
    .mini-nav-title { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:5px; min-height:64px; border-bottom:1px solid var(--line2); background:linear-gradient(180deg,#edf9f8,#dff2f1); color:var(--teal-dark); font-size:12px; font-weight:900; }
    .mini-nav-title svg { width:26px; height:26px; fill:none; stroke:currentColor; stroke-width:1.7; stroke-linecap:round; stroke-linejoin:round; }
    .mini-nav-title b { display:block; line-height:1; }
    .content { grid-column:2; grid-row:2; }
    .board-head { display:grid; grid-template-columns:minmax(260px,1fr) auto; grid-template-rows:auto auto; align-items:center; gap:6px 24px; min-height:112px; margin:0 0 14px; padding:14px 18px; border:1px solid var(--line2); border-radius:20px; background:rgba(255,255,255,.88); }
    .supplement-brand { grid-column:1; grid-row:1 / span 2; display:flex; align-items:center; justify-content:center; gap:14px; min-width:0; align-self:center; }
    .supplement-brand-mark { width:46px; height:46px; border-radius:999px; background:#183c76; color:#fff; display:grid; place-items:center; font-size:22px; font-weight:800; }
    .supplement-brand h1 { margin:0; font-size:24px; line-height:1.1; color:#17366d; white-space:nowrap; }
    .scope-note { margin:6px 0 0; color:#243b53; font-size:13px; line-height:1.35; font-weight:700; }
    .supplement-chip-row { display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
    .supplement-chip { display:inline-flex; align-items:center; min-height:32px; padding:0 12px; border-radius:8px; border:1px solid #c7d7eb; background:#f6f9fd; color:#17366d; font-size:13px; font-weight:900; white-space:nowrap; }
    .supplement-chip.limit { border-color:#f3d28c; background:#fff7e6; color:#b45309; }
    .supplement-chip.safe { border-color:#d5dee9; background:#f8fafc; color:#243b53; }
    .section-jump-nav { display:flex; gap:10px; flex-wrap:wrap; margin:0 0 14px; padding:10px 12px; border:1px solid var(--line2); border-radius:14px; background:rgba(255,255,255,.86); }
    .section-jump-nav a { display:inline-flex; align-items:center; gap:7px; min-height:32px; padding:0 11px; border:1px solid #9eb7d6; border-radius:8px; background:#fff; color:#17366d; font-size:13px; font-weight:900; text-decoration:none; }
    .section-jump-nav b { display:inline-grid; place-items:center; width:20px; height:20px; border-radius:5px; background:#edf4ff; color:#17366d; font-size:12px; }
    .top-actions { grid-column:2; grid-row:1; justify-self:end; justify-content:flex-end; margin:0; }
    .top-actions .tool-btn { min-height:34px; padding:0 14px; border-width:1.25px; border-radius:6px; font-size:14px; box-shadow:0 2px 8px rgba(10,127,124,.08); }
    .supplement-status-strip { grid-column:2; grid-row:2; display:flex; justify-content:flex-end; gap:18px; flex-wrap:wrap; }
    .supplement-status-box { min-width:150px; padding-left:18px; border-left:1px solid var(--line2); color:#17366d; }
    .supplement-status-box:first-child { border-left:0; padding-left:0; }
    .supplement-status-box .k { font-size:12px; color:#52616e; font-weight:700; }
    .supplement-status-box .v { margin-top:4px; font-size:14px; font-weight:800; color:#1f3b67; }
    .supplement-legend { display:flex; gap:17px; align-items:center; color:#25333f; font-size:14px; font-weight:800; white-space:nowrap; }
    .supplement-legend i { display:inline-block; width:18px; height:18px; margin-right:6px; vertical-align:-4px; border-radius:1px; }
    #sector .sector-grid { grid-template-columns:minmax(0,1fr) minmax(430px,.76fr); gap:14px; }
    #sector .sector-grid > .card { padding:12px; }
    #sector .sector-grid > .card:nth-child(2) { padding:10px 12px 12px; }
    #sector .sector-grid > .card:nth-child(2) h3 { margin-bottom:9px; }
    #sector .sector-figure { height:auto; aspect-ratio:360 / 292; }
    #sector .sector-figure svg { display:block; width:100%; height:100%; }
    #sector .table-wrap { margin:0; }
    #sector .table { font-size:14px; }
    #sector .table th, #sector .table td { padding:7px 9px; }
    @media (max-width: 1200px) {
      .top-actions { justify-content:flex-end; }
      .top-actions .tool-btn { flex:0 0 auto; }
      .screen { grid-template-columns:110px minmax(0,1fr); }
      .metrics, .sector-kpis, #sector .sector-kpis { grid-template-columns:repeat(2,minmax(0,1fr)); }
      .split, .split-even, .decision-matrix, .market-grid, .audit-grid { grid-template-columns:1fr; }
      .sector-grid { grid-template-columns:1fr; }
      #sector .sector-grid { grid-template-columns:minmax(0,1fr) minmax(360px,.74fr); }
      #sector .sector-figure { height:auto; aspect-ratio:360 / 292; }
    }
    @media (max-width: 720px) {
      .wrap { width:calc(100vw - 14px); padding-top:8px; }
      .board-head { display:grid; grid-template-columns:1fr; gap:10px; min-height:0; padding:12px; }
      .supplement-brand, .top-actions, .supplement-status-strip { grid-column:1; grid-row:auto; justify-self:stretch; justify-content:flex-start; }
      .supplement-brand { justify-content:flex-start; }
      .supplement-status-box { min-width:0; }
      .supplement-chip-row { justify-content:flex-start; }
      h1 { font-size:21px; }
      .subhead { display:block; margin:4px 0 0; font-size:12px; }
      .screen-head { display:grid; grid-template-columns:52px minmax(0,1fr); align-items:center; gap:6px 10px; padding:8px 10px 10px; }
      .screen-no { grid-row:1 / span 2; width:52px; height:48px; margin-left:0; border-radius:7px; font-size:28px; }
      .screen-title { font-size:24px; writing-mode:horizontal-tb; word-break:keep-all; }
      .source { grid-column:2; font-size:12px; line-height:1.35; }
      .screen { grid-template-columns:1fr; }
      .screen-head { grid-column:1; grid-row:1; }
      .mini-nav { grid-column:1; grid-row:2; padding-top:0; }
      .content { grid-column:1; grid-row:3; }
      .top-actions { gap:8px; }
      .top-actions .tool-btn { min-height:34px; padding:0 10px; font-size:13px; }
      .mini-nav { display:flex; overflow:auto; padding:0; border-right:0; border-bottom:1px solid var(--line2); }
      .mini-nav-title { min-width:92px; min-height:50px; border-bottom:0; border-right:1px solid var(--line2); font-size:11px; }
      .mini-nav-title svg { width:20px; height:20px; }
      .mini-nav label { min-width:86px; justify-content:center; }
      .metrics, .split, .split-even, .split-3, .decision-matrix, .flow, .sector-grid, .market-grid, .audit-grid, .structure-strip { grid-template-columns:1fr; }
      #sector .sector-grid { grid-template-columns:1fr; }
      .screen-tools { display:none; }
    }
    """

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>補足レポート</title>
  <style>{style}
    html, body {{ overflow-x:hidden; }}
    body {{ background:#f7f9fc; font-size:16px; line-height:1.65; }}
    .supplement-dashboard-shell {{ max-width:1380px; margin:0 auto; padding:0 28px 40px; }}
    .supplement-topbar {{ display:flex; justify-content:space-between; gap:18px; align-items:center; min-height:44px; margin:0 -28px 22px; padding:0 28px; background:#102a55; color:#fff; }}
    .supplement-topbar strong {{ font-size:14px; }}
    .supplement-topbar span {{ color:#d8e6fa; font-size:13px; }}
    .supplement-hero {{ display:grid; grid-template-columns:minmax(320px,1fr) auto; gap:28px; align-items:center; margin-bottom:18px; }}
    .supplement-title-block {{ display:flex; gap:16px; align-items:center; }}
    .supplement-title-icon {{ width:52px; height:52px; flex:0 0 auto; border-radius:12px; display:grid; place-items:center; background:#e8f0fb; color:#173f7a; font-size:30px; }}
    .supplement-title-block h1 {{ margin:0; color:#0b1830; font-size:clamp(28px,3vw,40px); letter-spacing:-.02em; }}
    .scope-note {{ margin:5px 0 0; color:#425466; font-size:15px; font-weight:800; }}
    .supplement-chip-row {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }}
    .supplement-chip {{ display:inline-flex; align-items:center; min-height:38px; padding:0 14px; border:1px solid #cbd8e6; border-radius:8px; background:#fff; color:#17366d; font-size:13px; font-weight:900; white-space:normal; overflow-wrap:anywhere; }}
    .supplement-chip.limit {{ border-color:#efd09c; background:#fff7e8; color:#9a5700; }}
    .supplement-chip.safe {{ background:#f1f4f8; color:#344054; }}
    .supplement-chip-row .chronicle-launch {{ min-height:38px; padding:7px 14px; font-size:13px; line-height:1.35; }}
    .supplement-reading-guide {{ display:grid; grid-template-columns:minmax(210px,.72fr) minmax(0,1.28fr); gap:18px; align-items:center; margin:0 0 18px; padding:16px 18px; border-left:5px solid #2f5f9f; border-radius:0 12px 12px 0; background:#eef4fb; }}
    .supplement-reading-guide strong {{ color:#102a55; font-size:17px; }}
    .supplement-reading-guide span {{ color:#425466; font-size:14px; line-height:1.6; overflow-wrap:anywhere; }}
    .supplement-nav {{ position:sticky; top:0; z-index:8; display:flex; gap:8px; flex-wrap:wrap; align-items:stretch; margin:0 0 22px; padding:10px 0; border-block:1px solid #cbd8e6; background:rgba(247,249,252,.96); backdrop-filter:blur(8px); }}
    .supplement-nav strong {{ display:flex; align-items:center; margin-right:4px; color:#17366d; font-size:14px; }}
    .supplement-nav a {{ display:flex; align-items:center; gap:8px; min-height:44px; padding:5px 12px; border:1px solid #cbd8e6; border-radius:9px; background:#fff; color:#17366d; font-size:13px; font-weight:900; text-decoration:none; }}
    .supplement-nav a small {{ display:block; color:#66788e; font-size:10px; font-weight:800; }}
    .supplement-nav b {{ display:inline-grid; place-items:center; width:24px; height:24px; flex:0 0 auto; border-radius:999px; background:#e8f0fb; }}
    .summary-intro {{ margin:0 0 12px; }}
    .summary-intro h2 {{ margin:0; color:#102a55; font-size:24px; }}
    .summary-intro p {{ margin:5px 0 0; color:#5f6c77; font-size:14px; }}
    .evidence-summary-grid {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:0; margin-bottom:28px; border-block:1px solid #d5e0eb; background:#fff; }}
    .evidence-summary-card, .evidence-card {{ background:#fff; box-shadow:none; }}
    .evidence-summary-card {{ padding:18px; border:0; border-radius:0; }}
    .evidence-summary-card + .evidence-summary-card {{ border-left:1px solid #d5e0eb; }}
    .evidence-summary-card h2 {{ margin:0 0 13px; color:#17366d; font-size:16px; line-height:1.45; }}
    .evidence-summary-card dl {{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px 10px; margin:0; font-size:14px; }}
    .evidence-summary-card dt {{ color:#52606d; font-weight:700; }}
    .evidence-summary-card dd {{ margin:0; color:#0f1828; font-weight:900; }}
    .supplement-evidence-grid {{ display:grid; grid-template-columns:minmax(0,1fr); gap:18px; align-items:start; }}
    .evidence-card {{ padding:20px 22px; min-width:0; border:1px solid #d5e0eb; border-radius:12px; scroll-margin-top:82px; }}
    .evidence-card.wide {{ grid-column:auto; }}
    .evidence-card h2 {{ margin:0 0 14px; color:#17366d; font-size:21px; line-height:1.4; }}
    .evidence-card .table-wrap {{ max-height:none; overflow:auto; border-radius:8px; }}
    .evidence-card .table {{ min-width:720px; font-size:14px; font-variant-numeric:tabular-nums; }}
    .evidence-card .table th, .evidence-card .table td {{ padding:10px 12px; line-height:1.5; }}
    .evidence-card .table tbody tr:nth-child(even) {{ background:#f8fafc; }}
    .risk-line-detail-section {{ grid-column:auto; border-top:4px solid #2f5f9f; }}
    .hindenburg-history-section .mini-panel {{ margin:0; }}
    .hindenburg-history-section .hindenburg-panel {{ border:0; padding:0; }}
    .manual-link-wrap {{ float:right; margin-left:8px; }}
    .manual-link {{ display:inline-flex; align-items:center; min-height:24px; padding:0 8px; border:1px solid #9eb7d6; border-radius:6px; background:#fff; color:#17366d; font-size:12px; font-weight:800; text-decoration:none; white-space:nowrap; }}
    .hindenburg-history-section .table-wrap {{ max-height:150px; }}
    .episode-chronicle-launch-section {{ border-color:#9fb2c2; border-top:4px solid #102a55; background:linear-gradient(90deg,#f5f1e8 0,#fff 72%); }}
    .chronicle-launch-layout {{ display:grid; grid-template-columns:minmax(280px,1.5fr) minmax(270px,.9fr) minmax(210px,.8fr); gap:22px; align-items:center; }}
    .chronicle-copy p {{ margin:8px 0 6px; color:#263d54; line-height:1.7; }}
    .chronicle-copy small, .chronicle-latest small {{ color:#66788e; overflow-wrap:anywhere; }}
    .chronicle-kicker {{ display:flex; gap:10px; align-items:center; color:#102a55; font-size:12px; font-weight:900; letter-spacing:.06em; }}
    .chronicle-state {{ display:inline-flex; align-items:center; min-height:25px; padding:2px 8px; border:1px solid; border-radius:999px; letter-spacing:0; }}
    .chronicle-state.ready {{ color:#21633c; border-color:#83a68c; background:#edf6ee; }}
    .chronicle-state.unavailable {{ color:#8b5a10; border-color:#d8aa66; background:#fff6e8; }}
    .chronicle-stats {{ display:grid; grid-template-columns:repeat(3,1fr); margin:0; border-block:1px solid #cbd8e6; }}
    .chronicle-stats div {{ padding:12px 8px; text-align:center; }}
    .chronicle-stats div + div {{ border-left:1px solid #cbd8e6; }}
    .chronicle-stats dt {{ color:#66788e; font-size:11px; font-weight:800; }}
    .chronicle-stats dd {{ margin:3px 0 0; color:#102a55; font-family:Georgia,serif; font-size:25px; font-weight:700; }}
    .chronicle-latest {{ display:grid; gap:3px; min-width:0; }}
    .chronicle-latest span {{ color:#66788e; font-size:11px; font-weight:800; }}
    .chronicle-latest strong {{ color:#102a55; overflow-wrap:anywhere; }}
    .chronicle-action-wrap {{ grid-column:1/-1; display:flex; justify-content:flex-end; margin-top:-4px; }}
    .chronicle-launch {{ display:inline-flex; align-items:center; justify-content:center; gap:8px; min-height:46px; padding:8px 18px; border:1px solid #102a55; border-radius:7px; background:#102a55; color:#fff; font-weight:900; text-decoration:none; }}
    .chronicle-launch:hover {{ background:#1e4673; }}
    .chronicle-launch.disabled {{ border-color:#b8c0c8; background:#eef1f4; color:#677482; cursor:not-allowed; }}
    .history-browser-section {{ grid-column:span 1; }}
    .history-mini-chart {{ height:150px; border:1px solid #dbe6eb; border-radius:6px; background:linear-gradient(180deg,#fff,#f8fbff); display:grid; place-items:center; color:#6b7785; font-weight:900; }}
    .supplement-footer-note {{ margin-top:22px; padding:14px 18px; border-left:4px solid #2f5f9f; background:#edf4fb; color:#17366d; font-size:13px; font-weight:800; }}
    @media (max-width: 1180px) {{
      .evidence-summary-grid {{ grid-template-columns:1fr 1fr; }}
      .evidence-summary-card + .evidence-summary-card {{ border-left:0; border-top:1px solid #d5e0eb; }}
    }}
    @media (max-width: 760px) {{
      .supplement-dashboard-shell {{ padding:0 14px 28px; }}
      .supplement-topbar {{ align-items:flex-start; flex-direction:column; gap:2px; min-height:0; margin:0 -14px 16px; padding:9px 14px; }}
      .supplement-topbar span {{ font-size:11px; overflow-wrap:anywhere; }}
      .supplement-hero, .supplement-reading-guide, .evidence-summary-grid {{ grid-template-columns:1fr; }}
      .supplement-hero {{ gap:14px; }}
      .supplement-title-block {{ align-items:flex-start; }}
      .supplement-title-icon {{ width:42px; height:42px; font-size:24px; }}
      .scope-note {{ font-size:14px; line-height:1.5; }}
      .supplement-chip-row {{ justify-content:flex-start; }}
      .supplement-chip {{ min-height:36px; padding:7px 11px; line-height:1.35; }}
      .supplement-reading-guide {{ gap:5px; padding:14px; }}
      .supplement-nav {{ flex-wrap:nowrap; margin-inline:-14px; padding:9px 14px; overflow-x:auto; scrollbar-width:thin; }}
      .supplement-nav strong {{ display:none; }}
      .supplement-nav a {{ min-width:max-content; }}
      .evidence-summary-card + .evidence-summary-card {{ border-top:1px solid #d5e0eb; }}
      .evidence-card {{ padding:17px 15px; }}
      .evidence-card h2 {{ font-size:19px; }}
      .chronicle-launch-layout {{ grid-template-columns:1fr; gap:14px; }}
      .chronicle-action-wrap {{ grid-column:auto; justify-content:stretch; margin-top:0; }}
      .chronicle-launch {{ width:100%; }}
      .table-wrap {{ position:relative; }}
    }}
  </style>
</head>
<body>
  <main class="supplement-dashboard-shell">
    <header class="supplement-topbar">
      <strong>グローバル市場モニター</strong>
      <span>最終更新: {generated_at} / {source_name}</span>
    </header>
    <section class="supplement-hero" aria-label="補足レポート概要">
      <div class="supplement-title-block">
        <div class="supplement-title-icon">▤</div>
        <div>
          <h1>補足レポート</h1>
          <p class="scope-note">本体判断ではなく、補助確認と検証用の詳細です</p>
        </div>
      </div>
      <div class="supplement-chip-row">
        <span class="supplement-chip limit">データ制約</span>
        <span class="supplement-chip safe">本体判断への影響なし</span>
        {chronicle_action}
        <a class="supplement-chip" href="report.html">本体レポートへ戻る</a>
      </div>
    </section>
    <aside class="supplement-reading-guide" aria-label="補足レポートの読み方">
      <strong>この画面は、気になる理由を深掘りするときに使います</strong>
      <span>最初に「5つの要点」を確認し、必要な項目だけ下へ進んでください。データ品質上限: {quality_limit} / 実データ {quality_live_ratio} / {quality_cap_note}</span>
    </aside>
    <nav class="supplement-nav" aria-label="補足レポート セクション">
      <strong>見たい内容へ移動</strong>
      <a href="#risk-lines"><b>1</b><span>判断の根拠<small>危険ライン</small></span></a>
      <a href="#resident-context"><b>2</b><span>日本在住者向け<small>日本在住者文脈・国内文脈</small></span></a>
      <a href="#hindenburg-detail"><b>3</b><span>市場データ<small>ヒンデンブルグ・年代記・候補</small></span></a>
      <a href="#data-acquisition"><b>4</b><span>データ品質<small>データ取得・しきい値・実行環境</small></span></a>
      <a href="#history-browser"><b>5</b><span>履歴<small>過去との比較</small></span></a>
    </nav>
    <div class="summary-intro">
      <h2>まず確認する5つの要点</h2>
      <p>数値の細部よりも、評価が「通常・注意・警戒」のどこにあるかを先に見ます。</p>
    </div>
    <section class="evidence-summary-grid" aria-label="補足サマリー">
      <article class="evidence-summary-card"><h2>1. 市場全体の危険度</h2><dl><dt>総合評価</dt><dd>{esc(risk_lines.get('stage_label', '-'))}</dd><dt>危険/非常に危険</dt><dd>{esc(risk_lines.get('danger_count', 0))} / {esc(risk_lines.get('extreme_count', 0))}</dd><dt>要注意理由</dt><dd>{esc(len(risk_lines.get('reasons', [])))}</dd></dl></article>
      <article class="evidence-summary-card"><h2>2. 日本から投資するときの注意</h2><dl><dt>統合評価</dt><dd>{esc(_domestic_danger_level_label(integrated_context.get('combined_context_level')))}</dd><dt>為替の影響</dt><dd>{esc(_domestic_danger_level_label(integrated_context.get('fx_risk_level')))}</dd><dt>確認項目</dt><dd>{esc(len(integrated_context.get('watch_items', [])))}</dd></dl></article>
      <article class="evidence-summary-card"><h2>3. 国内市場の状態</h2><dl><dt>国内資産</dt><dd>{esc(_domestic_danger_level_label(domestic_danger.get('domestic_asset_level')))}</dd><dt>国内為替</dt><dd>{esc(_domestic_danger_level_label(domestic_danger.get('domestic_fx_level')))}</dd><dt>データ制約</dt><dd>{esc(len(domestic_danger.get('domestic_data_limitations', [])))}</dd></dl></article>
      <article class="evidence-summary-card"><h2>4. 急落の予兆を補助確認</h2><dl><dt>ヒンデンブルグオーメン</dt><dd>{esc(_hindenburg_signal_label((report.get('hindenburg_omen_context') or {}).get('current_signal')))}</dd><dt>最新トリガー日</dt><dd>{esc((report.get('hindenburg_omen_context') or {}).get('latest_trigger_date', '-'))}</dd><dt>発動期間中か</dt><dd>{'はい' if (report.get('hindenburg_omen_context') or {}).get('is_currently_active') else 'いいえ'}</dd></dl></article>
      <article class="evidence-summary-card"><h2>5. 観察候補の数</h2><dl><dt>資産クラス比較</dt><dd>{esc(len(report.get('asset_compare', [])))}</dd><dt>候補数</dt><dd>{esc(len(candidate.get('candidate_tickers', [])))}</dd><dt>位置づけ</dt><dd>参考表示</dd></dl></article>
    </section>
    <section class="supplement-evidence-grid" aria-label="補足詳細">
      <section class="evidence-card risk-line-detail-section" id="risk-lines"><h2>1. 危険ライン詳細と信頼度監査</h2><div class="table-wrap">{table(['指標','判定','現在値','注意ライン','危険ライン','非常に危険','本判定根拠','参考・除外'], risk_line_rows)}</div><ul class="compact-list">{risk_reason_items}</ul></section>
      <section class="evidence-card resident-context-detail-section" id="resident-context"><h2>2. 日本在住者文脈（統合）詳細</h2>{integrated_context_panel}<div class="table-wrap" style="margin-top:8px;">{table(['為替','現在値','1週','4週','12週','判定'], fx_rows)}</div></section>
      <section class="evidence-card domestic-context-detail-section" id="domestic-context"><h2>3. 国内文脈（危険シグナル）詳細</h2>{domestic_danger_panel}</section>
      <section class="evidence-card hindenburg-history-section" id="hindenburg-detail"><h2>4. ヒンデンブルグオーメンのトリガー / 発動履歴</h2>{hindenburg_omen_panel}</section>
      <section class="evidence-card episode-chronicle-launch-section" id="episode-chronicle"><h2>5. 市場警戒年代記</h2>{chronicle_panel}</section>
      <section class="evidence-card asset-candidate-evidence-section" id="asset-candidate-evidence"><h2>6. 資産クラス / 候補証拠 詳細</h2><div class="table-wrap">{table(['資産クラス','ティッカー','12週','年率ボラ','最大DD'], asset_rows)}</div><div class="table-wrap" style="margin-top:8px;">{table(['銘柄','判定','理由'], candidate_rows)}</div></section>
      <section class="evidence-card data-acquisition-section" id="data-acquisition"><h2>7. データ取得状況</h2><div class="table-wrap">{table(['要求系列','状態','実使用系列','説明'], availability_rows)}</div></section>
      <section class="evidence-card threshold-audit-section" id="threshold-audit"><h2>8. しきい値の使用状況と認証</h2><div class="metrics" style="grid-template-columns:repeat(3,minmax(0,1fr));">{metric('レビュー状態', f"{esc(_jp_threshold_status(threshold_review.get('status', '-')))} / 推奨={esc(_display_bool(threshold_review.get('review_recommended', False)))}", 'warn' if threshold_review.get('review_recommended') else '')}{metric('メンテナンス', f"{esc(_localize_display_text(threshold_maintenance.get('status', '-')))} / {number(threshold_maintenance.get('elapsed_seconds'))}秒")}{metric('提案生成', esc(_display_bool(threshold_maintenance.get('proposal_generated_this_run', False))))}</div><div class="drift-list"><div><span>安定</span><b>{esc(drift_summary.get('stable_count', 0))}</b></div><div><span>監視</span><b style="color:var(--orange)">{esc(drift_summary.get('watch_count', 0))}</b></div><div><span>要確認</span><b style="color:var(--red)">{esc(drift_summary.get('review_count', 0))}</b></div><div><span>未取得</span><b>{esc(drift_summary.get('unavailable_count', 0))}</b></div></div>{_threshold_usage_html(report)}{_threshold_rule_certification_html(report)}</section>
      <section class="evidence-card runtime-diagnostics-section" id="runtime-diagnostics"><h2>9. 実行環境 / 接続診断</h2><div class="table-wrap">{table(['項目','内容'], [[esc(k), esc(v)] for k, v in diagnostic_rows], False)}</div><div style="margin-top:8px;">{alert_cards}</div><ul class="compact-list" style="margin-top:8px;">{warning_items}</ul></section>
      <section class="evidence-card history-browser-section" id="history-browser"><h2>10. 履歴ブラウザ</h2><div class="metrics" style="grid-template-columns:repeat(3,minmax(0,1fr));">{metric('主基準 daily_latest', f"{esc(history_meta.get('daily_latest_count', 0))}件")}{metric('参考 all_history', f"{esc(history_meta.get('history_count', 0))}件")}{metric('最新スコア', esc(latest_history.get('score', '-')))}</div><div class="history-mini-chart">履歴確認用の参考表示</div></section>
    </section>
    <footer class="supplement-footer-note">本画面および生成されたレポート / キャッシュ / 診断アーティファクトは、本体判断の入力には利用されません。補助確認・監査・トラブルシュートのための情報です。</footer>
  </main>
</body>
</html>
"""
