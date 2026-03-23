from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any


STATUS_LABELS = {
    "ok": "取得成功",
    "proxy_fallback": "代替ティッカーで取得",
    "sample_fallback": "サンプルデータ代替",
    "unavailable": "未取得",
}

ACTION_LABELS = {
    "buy_window": "買い検討ゾーン",
    "watch": "監視継続",
    "wait": "待機",
}

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

SECTION_EXPLANATIONS = {
    "regime": "市場レジームは、モメンタム、トレンド強度、最大ドローダウン、ボラティリティ圧縮をまとめて地合いを分類したものです。",
    "cycle": "サイクル判定は週次データの位相から、相場が上昇・終盤・回復・下降のどこに近いかを見る補助指標です。",
    "score": "合成スコアは 0 から 1 の範囲で、数値が高いほど押し目検討の条件が揃っていることを示します。",
    "spot": "スポット投資判定は、地合いとサイクルとドローダウンを合わせて、今すぐ強気に入るか、監視か、待機かを示します。",
    "sector": "セクターローテーションは 12 週騰落率の順位で、資金がどこへ向かっているかを見るための一覧です。簡易ローテーション図は、順位と騰落率を円上に置いた見やすい補助図です。",
    "asset": "資産クラス比較は、各資産の 12 週モメンタム、年率ボラティリティ、最大ドローダウンを並べて相対比較するものです。",
    "credit": "信用監視は、ハイイールド債、投資適格社債、その比率を週次変化率と z スコアで並べ、株価だけでは見えにくい信用市場の悪化や改善を補助的に見るものです。",
    "inflation": "インフレ監視は、原油、金、ドル指数を週次変化率と z スコアで並べ、物価圧力や安全資産選好が強まっていないかを見る補助セクションです。",
    "risk_lines": "危険ライン監視は、VIX、MOVE、米10年、原油、ドル、SPY、HYG、LQD、HYG/LQD をまとめて、通常・警戒・危険ライン・非常に危険ラインのどこにあるかを示す判定層です。",
    "analogues": "類似局面は、直近 12 週の値動きに近い過去パターンを探し、その後 12 週の結果を参考情報として表示します。",
    "availability": "データ取得状況では、各系列が主系列で取れたか、代替ティッカーへ切り替わったか、サンプル代替か、完全未取得かを示します。",
    "diagnostics": "接続診断では、今回の実行が live 取得だったか、配布 exe 実行か、失敗時にどのホストや例外が出たかを後から追えるようにまとめます。",
    "decision_reasons": "判定理由は、地合い、サイクル、合成スコア、信用市場の補助情報を文章でつないだ要約です。数値一覧だけで見落としやすい悪化要因を先に読むために使います。",
    "candidates": "投資候補は、既存の地合い判定を前提に、相対強度の高い資産クラスや先導セクターを候補として整理する補助層です。強い推奨ではなく、優先候補・観察候補・候補なしの三段で示します。",
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
    html_text = render_html(report)
    timestamp = _timestamp_slug(report["generated_at"])

    markdown_path = reports_path / "report.md"
    html_path = reports_path / "report.html"
    history_markdown_path = history_path / f"report_{timestamp}.md"
    history_html_path = history_path / f"report_{timestamp}.html"
    history_json_path = history_path / f"report_{timestamp}.json"

    markdown_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    history_markdown_path.write_text(markdown_text, encoding="utf-8")
    history_html_path.write_text(html_text, encoding="utf-8")

    if sample_output_dir is not None:
        sample_path = Path(sample_output_dir)
        sample_path.mkdir(parents=True, exist_ok=True)
        (sample_path / "report_sample.md").write_text(markdown_text, encoding="utf-8")
        (sample_path / "report_sample.html").write_text(html_text, encoding="utf-8")

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
    return f'**{safe}**'


def _risk_badge_html(label: str | None, tone: str) -> str:
    safe = html.escape(str(label or "-"))
    if tone == "normal":
        return f'<strong>{safe}</strong>'
    return f'<span class="risk-badge {tone}">{safe}</span>'


def render_markdown(report: dict[str, Any]) -> str:
    regime_label = _jp_regime(report["regime"]["regime_label"])
    cycle_label = _jp_cycle(report["cycle"]["phase_label"])
    action_label = _jp_action(report["spot_signal"]["action"])
    risk_label = _jp_risk(report["spot_signal"]["second_leg_risk"])
    risk_lines = report.get("risk_lines", {})
    risk_stage_badge_html = _risk_badge_html(risk_lines.get("stage_label", "-"), _risk_stage_tone(risk_lines.get("stage_key")))
    risk_stage_badge = _risk_badge_markdown(risk_lines.get("stage_label", "-"), _risk_stage_tone(risk_lines.get("stage_key")))
    internal_warning_count = len(report.get("warnings", []))

    lines = [
        f"# {report['title']}",
        "",
        "## サマリー",
        f"- 生成時刻: {report['generated_at']}",
        f"- データソース: {report['data_source']}",
        f"- 判定信頼性: {_jp_reliability(report.get('data_reliability', {}).get('level', 'high'))}",
        f"- 市場レジーム: {regime_label}",
        f"- サイクル判定: {cycle_label} ({_display_number(report['cycle'].get('phase_angle_deg'))} 度)",
        f"- 合成スコア: {_display_number(report['score'].get('total_score'))}",
        f"- 判定用スコア: {_display_number(report['spot_signal'].get('adjusted_score', report['score'].get('total_score')))}",
        f"- スポット投資判断: {action_label}",
        f"- 二段下げリスク: {risk_label}",
        f"- 市場ストレス段階: {risk_stage_badge}",
        "",
        "## 解説",
        f"- 市場レジーム: {SECTION_EXPLANATIONS['regime']}",
        f"- サイクル判定: {SECTION_EXPLANATIONS['cycle']}",
        f"- 合成スコア: {SECTION_EXPLANATIONS['score']}",
        f"- スポット投資判断: {SECTION_EXPLANATIONS['spot']}",
        "",
    ]
    lines.extend(["## 判定理由", f"- {SECTION_EXPLANATIONS['decision_reasons']}"])
    for reason in report["spot_signal"].get("rationale", []):
        lines.append(f"- {reason}")

    lines.extend(["", "## セクターローテーション", f"- {SECTION_EXPLANATIONS['sector']}"])
    for row in report["sector_rotation"]["table"]:
        lines.append(
            f"- {row['ticker']} ({row['sector_name_ja']}): 12週騰落率 {row['return_12w']} / 順位 {row['rank']}位 / 位置 {row['rotation_phase_ja']}"
        )

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

    candidate = report.get("investment_candidates", {})
    lines.extend(["", "## 危険ライン監視", f"- {SECTION_EXPLANATIONS['risk_lines']}"])
    lines.append(f"- 段階: {risk_stage_badge}")
    lines.append(f"- 要約: {risk_lines.get('summary', '-')}")
    lines.append(f"- 厳密性: {risk_lines.get('precision_label', '-')}")
    lines.append(f"- 不足指標: {', '.join(risk_lines.get('strict_missing_indicators', []) or risk_lines.get('missing_indicators', [])) or 'なし'}")
    lines.append(f"- 総合ストレス指数: {_display_number(risk_lines.get('composite_risk_score'))}")
    lines.append(f"- 合成スコア側の内部警告件数: {internal_warning_count}")
    lines.append("- 注記: 内部警告件数は alerts/warnings の件数で、危険ライン段階とは別の判定です。")
    lines.append(f"- 危険ライン本数: {risk_lines.get('danger_count', 0)} / 非常に危険ライン本数: {risk_lines.get('extreme_count', 0)}")
    for reason in risk_lines.get("reasons", []):
        lines.append(f"- {reason}")
    for row in risk_lines.get("indicators", []):
        line_badge = _risk_badge_markdown(row.get('line_level_label', '-'), _risk_label_tone(row.get('line_level_label')))
        lines.append(
            f"- {row.get('ticker_name_ja', row.get('ticker', '-'))} ({row.get('ticker', '-')}): 現在値 {_display_number(row.get('current'))} / 1週 {_display_number(row.get('change_1w'))} / 4週 {_display_number(row.get('change_4w'))} / z {_display_number(row.get('zscore'))} / 判定 {line_badge} / warning {row.get('warning_line', '-')} / danger {row.get('danger_line', '-')} / extreme {row.get('extreme_line', '-')}"
        )

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
        lines.append(
            f"- 優先セクター: {sector_candidate.get('sector_name_ja', '-')} ({sector_candidate.get('ticker', '-')})"
        )
    tickers = candidate.get("candidate_tickers", [])
    if tickers:
        lines.append("- 候補ティッカー: " + ", ".join(f"{item.get('ticker', '-')}({item.get('label', '-')})" for item in tickers))
    for reason in candidate.get("rationale", []):
        lines.append(f"- {reason}")

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
        lines.append(
            f"- 優先セクター: {recovery_sector.get('ticker_name_ja', '-')} ({recovery_sector.get('ticker', '-')})"
        )
    recovery_tickers = recovery.get("candidate_tickers", [])
    if recovery_tickers:
        lines.append("- 候補ティッカー: " + ", ".join(f"{item.get('ticker', '-')}({item.get('label', '-')})" for item in recovery_tickers))
    for reason in recovery.get("rationale", []):
        lines.append(f"- {reason}")

    regime_leading = report.get("regime_leading_candidates", {})
    lines.extend(["", "## レジーム先回り候補", f"- {SECTION_EXPLANATIONS['regime_leading_candidates']}"])
    lines.append(f"- 判定: {regime_leading.get('label', '候補なし')}")
    lines.append(f"- 要約: {regime_leading.get('summary', '-')}")
    leading_sector = regime_leading.get("preferred_sector")
    if leading_sector:
        lines.append(
            f"- 優先セクター: {leading_sector.get('ticker_name_ja', '-')} ({leading_sector.get('ticker', '-')})"
        )
    leading_region = regime_leading.get("preferred_region")
    if leading_region:
        lines.append(
            f"- 優先地域: {leading_region.get('ticker_name_ja', '-')} ({leading_region.get('ticker', '-')})"
        )
    leading_asset = regime_leading.get("preferred_asset_class")
    if leading_asset:
        lines.append(
            f"- 優先資産: {leading_asset.get('ticker_name_ja', '-')} ({leading_asset.get('ticker', '-')})"
        )
    leading_tickers = regime_leading.get("candidate_tickers", [])
    if leading_tickers:
        lines.append("- 候補ティッカー: " + ", ".join(f"{item.get('ticker', '-')}({item.get('label', '-')}: {item.get('reason', '-')})" for item in leading_tickers))
    for reason in regime_leading.get("rationale", []):
        lines.append(f"- {reason}")

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
            lines.append(
                f"- {row['end_date']}: 類似度 {row['similarity']}, その後12週リターン {row['forward_12w_return']}"
            )
    else:
        lines.append("- 十分に近い類似局面は抽出されませんでした。")

    lines.extend(["", "## データ取得状況", f"- {SECTION_EXPLANATIONS['availability']}" ])
    for entry in report.get("data_availability", []):
        requested_name = entry.get("requested_ticker_name_ja") or entry["requested_ticker"]
        used = entry.get("used_ticker") or "-"
        used_name = entry.get("used_ticker_name_ja") or "-"
        alt = ", ".join(
            f"{ticker}({name})"
            for ticker, name in zip(entry.get("alternatives", []), entry.get("alternatives_name_ja", []))
        ) if entry.get("alternatives") else "なし"
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
    lines.append(f"- 失敗試行数: {summary.get('failed_attempt_count', 0)}")
    lines.append(f"- 接続不良疑い: {'あり' if summary.get('suspected_network_issue') else 'なし'}")
    hosts = diagnostics.get("suspected_hosts", [])
    lines.append(f"- 接続先候補ホスト: {', '.join(hosts) if hosts else '記録なし'}")
    samples = diagnostics.get("failure_samples", [])
    if samples:
        lines.append("- 代表エラー:")
        lines.extend([f"  - {sample}" for sample in samples])

    lines.extend(["", "## 警告"])
    if report["warnings"]:
        lines.extend([f"- {warning}" for warning in report["warnings"]])
    else:
        lines.append("- 重要な警告はありません。")
    return "\n".join(lines) + "\n"


def render_html(report: dict[str, Any]) -> str:
    regime_label = _jp_regime(report["regime"]["regime_label"])
    cycle_label = _jp_cycle(report["cycle"]["phase_label"])
    action_label = _jp_action(report["spot_signal"]["action"])
    risk_label = _jp_risk(report["spot_signal"]["second_leg_risk"])
    internal_warning_count = len(report.get("warnings", []))

    warning_items = "".join(
        f"<li>{html.escape(warning)}</li>" for warning in report["warnings"]
    ) or "<li>重要な警告はありません。</li>"
    sector_rows = "".join(
        f"<tr><td>{html.escape(row['ticker'])}</td><td>{html.escape(row['sector_name_ja'])}</td><td>{row['return_12w']}</td><td>{row['rank']}</td><td>{html.escape(row['rotation_phase_ja'])}</td></tr>"
        for row in report["sector_rotation"]["table"]
    ) or "<tr><td colspan='5'>有効データなし</td></tr>"
    asset_rows = "".join(
        "<tr>"
        f"<td>{html.escape(row['asset_class'])}</td>"
        f"<td>{html.escape(row['ticker'])}<br><span style='color:#52606d;font-size:12px'>{html.escape(row['ticker_name_ja'])}</span></td>"
        f"<td>{row['momentum_12w']}</td>"
        f"<td>{row['annualized_volatility']}</td>"
        f"<td>{row['max_drawdown']}</td>"
        "</tr>"
        for row in report["asset_compare"]
    ) or "<tr><td colspan='5'>有効データなし</td></tr>"
    credit_rows = "".join(
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
    ) or "<tr><td colspan='7'>有効データなし</td></tr>"
    risk_lines = report.get("risk_lines", {})
    risk_stage_badge_html = _risk_badge_html(risk_lines.get("stage_label", "-"), _risk_stage_tone(risk_lines.get("stage_key")))

    inflation_rows = "".join(
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
    ) or "<tr><td colspan='7'>有効データなし</td></tr>"
    risk_line_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('ticker_name_ja', row.get('ticker', '-'))))}<br><span style='color:#52606d;font-size:12px'>{html.escape(str(row.get('ticker', '-')))}</span></td>"
        f"<td>{_risk_badge_html(row.get('line_level_label', '-'), _risk_label_tone(row.get('line_level_label')))}</td>"
        f"<td>{_display_number(row.get('current'))}</td>"
        f"<td>{_display_number(row.get('warning_line'))}</td>"
        f"<td>{_display_number(row.get('danger_line'))}</td>"
        f"<td>{_display_number(row.get('extreme_line'))}</td>"
        f"<td>{html.escape(str(row.get('line_reason', '-')))}</td>"
        "</tr>"
        for row in risk_lines.get("indicators", [])
    ) or "<tr><td colspan='7'>有効データなし</td></tr>"
    risk_line_reason_items = "".join(f"<li>{html.escape(str(reason))}</li>" for reason in risk_lines.get("reasons", [])) or "<li>追加理由はありません。</li>"
    alert_items = "".join(
        "<li>"
        f"<strong>{html.escape(alert.get('title', '-'))}</strong>"
        f" <span class='pill'>{html.escape(_alert_category_label(alert.get('category', 'memo')))} / {html.escape(_alert_severity_label(alert.get('severity', 'low')))}</span>"
        f"<br><span style='color:#52606d'>{html.escape(alert.get('message', '-'))}</span>"
        "</li>"
        for alert in report.get("alerts", [])
    ) or "<li>現時点で追加の警告はありません。</li>"
    candidate = report.get("investment_candidates", {})
    candidate_items = "".join(
        f"<li>{html.escape(reason)}</li>" for reason in candidate.get("rationale", [])
    ) or "<li>候補提示の条件がまだ揃っていません。</li>"
    candidate_asset = candidate.get("preferred_asset_class")
    candidate_sector = candidate.get("preferred_sector")
    candidate_tickers = ", ".join(
        f"{item.get('ticker', '-')}({item.get('label', '-')})" for item in candidate.get("candidate_tickers", [])
    ) or "なし"
    recovery = report.get("recovery_candidates", {})
    recovery_items = "".join(
        f"<li>{html.escape(reason)}</li>" for reason in recovery.get("rationale", [])
    ) or "<li>先回り候補の条件はまだ揃っていません。</li>"
    recovery_asset = recovery.get("preferred_asset_class")
    recovery_sector = recovery.get("preferred_sector")
    recovery_tickers = ", ".join(
        f"{item.get('ticker', '-')}({item.get('label', '-')})" for item in recovery.get("candidate_tickers", [])
    ) or "なし"
    regime_leading = report.get("regime_leading_candidates", {})
    regime_leading_items = "".join(
        f"<li>{html.escape(reason)}</li>" for reason in regime_leading.get("rationale", [])
    ) or "<li>レジーム先回り候補の条件はまだ揃っていません。</li>"
    regime_leading_sector = regime_leading.get("preferred_sector")
    regime_leading_region = regime_leading.get("preferred_region")
    regime_leading_asset = regime_leading.get("preferred_asset_class")
    regime_leading_tickers = ", ".join(
        f"{item.get('ticker', '-')}({item.get('label', '-')}: {item.get('reason', '-')})" for item in regime_leading.get("candidate_tickers", [])
    ) or "なし"
    analogue_rows = "".join(
        "<tr>"
        f"<td>{row['end_date']}</td><td>{row['similarity']}</td><td>{row['forward_12w_return']}</td>"
        "</tr>"
        for row in report["analogues"]
    ) or "<tr><td colspan='3'>十分に近い類似局面は抽出されませんでした。</td></tr>"
    availability_rows = "".join(
        "<tr>"
        f"<td>{html.escape(entry['requested_ticker'])}<br><span style='color:#52606d;font-size:12px'>{html.escape(entry.get('requested_ticker_name_ja', entry['requested_ticker']))}</span></td>"
        f"<td>{html.escape(STATUS_LABELS.get(entry['status'], entry['status']))}</td>"
        f"<td>{html.escape(entry.get('used_ticker') or '-')}<br><span style='color:#52606d;font-size:12px'>{html.escape(entry.get('used_ticker_name_ja') or '-')}</span></td>"
        f"<td>{html.escape(', '.join(f'{ticker}({name})' for ticker, name in zip(entry.get('alternatives', []), entry.get('alternatives_name_ja', []))) if entry.get('alternatives') else 'なし')}</td>"
        f"<td>{html.escape(entry['message'])}</td>"
        "</tr>"
        for entry in report.get("data_availability", [])
    ) or "<tr><td colspan='5'>取得状況データなし</td></tr>"
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
            ("失敗試行数", str(summary.get("failed_attempt_count", 0))),
            ("接続不良疑い", "あり" if summary.get("suspected_network_issue") else "なし"),
            ("接続先候補ホスト", ", ".join(diagnostics.get("suspected_hosts", [])) or "記録なし"),
        ]
    )
    diagnostic_error_items = "".join(
        f"<li>{html.escape(item)}</li>" for item in diagnostics.get("failure_samples", [])
    ) or "<li>代表エラーは記録されていません。</li>"
    sector_svg = _render_sector_rotation_svg(report["sector_rotation"].get("table", []))

    return f"""<!doctype html>
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
    body {{ font-family: 'Yu Gothic UI', 'Hiragino Sans', sans-serif; margin: 0; background: linear-gradient(180deg, #f7faff 0%, #eaf0f7 100%); color: var(--ink); }}
    .wrap {{ max-width: 1160px; margin: 0 auto; padding: 28px 20px 56px; }}
    .hero {{ background: var(--panel); border: 1px solid var(--line); border-radius: 24px; padding: 22px 24px; box-shadow: none; }}
    .hero h1 {{ margin: 0; font-size: 34px; line-height: 1.12; }}
    .hero-copy {{ margin: 10px 0 0; max-width: 76ch; color: var(--muted); line-height: 1.7; }}
    .meta {{ display: flex; gap: 10px; flex-wrap: wrap; color: var(--muted); font-size: 14px; margin-top: 14px; }}
    .hero-status {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }}
    .status-chip {{ min-width: 180px; padding: 12px 14px; border-radius: 16px; border: 1px solid var(--line); background: rgba(255,255,255,0.72); }}
    .status-chip .k {{ font-size: 11px; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: .03em; }}
    .status-chip .v {{ margin-top: 4px; font-size: 15px; font-weight: 800; line-height: 1.35; color: var(--ink); }}
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
    .pill {{ display: inline-block; padding: 4px 10px; border-radius: 999px; background: var(--accent-soft); color: #1d4ed8; font-size: 13px; }}
    .risk-badge {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 13px; font-weight: 800; }}
    .risk-badge.caution {{ background: rgba(183,121,31,0.12); color: var(--caution); }}
    .risk-badge.danger {{ background: rgba(192,86,33,0.14); color: var(--danger); }}
    .risk-badge.extreme {{ background: rgba(197,48,48,0.14); color: var(--bad); }}
    .inline-note {{ margin-top: 8px; font-size: 13px; color: var(--muted); line-height: 1.6; }}
    .sector-visual {{ display: grid; grid-template-columns: minmax(260px, 360px) 1fr; gap: 18px; align-items: start; }}
    .sector-caption {{ font-size: 13px; color: var(--muted); }}
    ul {{ margin: 0; padding-left: 20px; }}
    @media (max-width: 860px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .summary-main {{ grid-template-columns: 1fr; }}
      .summary-metrics {{ grid-template-columns: 1fr; }}
      .hero-status {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <section class=\"hero\">
      <h1>{html.escape(report['title'])}</h1>
      <p class=\"hero-copy\">市場レジーム、危険ライン、候補層、取得状況を分離して、運用判断に必要な順序で読めるようにしたレポートです。</p>
      <div class=\"meta\">
        <span>生成時刻: {html.escape(report['generated_at'])}</span>
        <span>データソース: <span class=\"pill\">{html.escape(report['data_source'])}</span></span>
        <span>判定信頼性: <span class=\"pill\">{html.escape(_jp_reliability(report.get('data_reliability', {}).get('level', 'high')))}</span></span>
      </div>
      <div class=\"hero-status\">
        <div class=\"status-chip\"><div class=\"k\">最優先</div><div class=\"v\">市場レジームと危険ライン</div></div>
        <div class=\"status-chip\"><div class=\"k\">次に見る</div><div class=\"v\">合成スコアとスポット判断</div></div>
        <div class=\"status-chip\"><div class=\"k\">補助層</div><div class=\"v\">候補、取得状況、診断</div></div>
      </div>
      <div class=\"grid\">
        <div class=\"summary-panel\">
          <div class=\"summary-head\"><h2>最重要シグナル</h2></div>
          <div class=\"summary-main\">
            <div>
              <div class=\"summary-value\">{html.escape(regime_label)}</div>
              <div class=\"summary-copy\">{html.escape(SECTION_EXPLANATIONS['regime'])}</div>
            </div>
            <div class=\"summary-side\">
              <div class=\"k\">合成スコア</div>
              <div class=\"v\">{html.escape(_display_number(report['score'].get('total_score')))}</div>
              <div class=\"explain\">判定用スコア {html.escape(_display_number(report['spot_signal'].get('adjusted_score', report['score'].get('total_score'))))}</div>
            </div>
          </div>
          <div class=\"summary-metrics\">
            <div class=\"mini-metric\"><div class=\"k\">サイクル判定</div><div class=\"v\">{html.escape(cycle_label)}</div></div>
            <div class=\"mini-metric\"><div class=\"k\">スポット判断</div><div class=\"v\">{html.escape(action_label)}</div></div>
            <div class=\"mini-metric\"><div class=\"k\">二段下げリスク</div><div class=\"v\">{html.escape(risk_label)}</div></div>
          </div>
        </div>
        <div class=\"side-grid\">
          <div class=\"card\">
            <h2>判定補足</h2>
            <div class=\"value\">{html.escape(_display_number(report['spot_signal'].get('regime_penalty', 0)))}</div>
            <div class=\"explain\">レジーム減点 {html.escape(_display_number(report['spot_signal'].get('regime_penalty', 0)))} / 信用ストレス補助 {html.escape(_display_number(report['score'].get('credit_stress_component', '-')))}</div>
          </div>
          <div class=\"card\">
            <h2>スポット投資判断</h2>
            <div class=\"value\">{html.escape(action_label)}</div>
            <div class=\"explain\">二段下げリスクは {html.escape(risk_label)}。{html.escape(SECTION_EXPLANATIONS['spot'])}</div>
          </div>
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

    <section class=\"section\">
      <h2>判定理由</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['decision_reasons'])}</p>
      <ul>{"".join(f"<li>{html.escape(reason)}</li>" for reason in report["spot_signal"].get("rationale", []))}</ul>
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
      <ul>{risk_line_reason_items}</ul>
      <table>
        <thead><tr><th>指標</th><th>判定</th><th>現在値</th><th>warning</th><th>danger</th><th>extreme</th><th>根拠</th></tr></thead>
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

    <section class=\"section\">
      <h2>セクターローテーション</h2>
      <p>{html.escape(SECTION_EXPLANATIONS['sector'])}</p>
      <div class=\"sector-visual\">
        <div>
          <h3>簡易ローテーション図</h3>
          {sector_svg}
          <div class=\"sector-caption\">外側ほど 12 週騰落率が強く、上側ほど順位が高いセクターです。一般的な厳密な RRG ではなく、順位と騰落率を見やすく配置した補助図です。</div>
        </div>
        <div>
          <table>
            <tr><th>ティッカー</th><th>日本語</th><th>12週騰落率</th><th>順位</th><th>位置</th></tr>
            {sector_rows}
          </table>
        </div>
      </div>
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
</body>
</html>
"""


def _render_sector_rotation_svg(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div>有効データなし</div>"

    width = 320
    height = 320
    cx = 160
    cy = 160
    max_radius = 115
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


def _timestamp_slug(generated_at: str) -> str:
    return generated_at.replace(":", "").replace("T", "_")


def _jp_action(value: str) -> str:
    return ACTION_LABELS.get(value, value)


def _jp_risk(value: str) -> str:
    return RISK_LABELS.get(value, value)


def _jp_regime(value: str) -> str:
    return REGIME_LABELS.get(value, value)


def _jp_cycle(value: str) -> str:
    return CYCLE_LABELS.get(value, value)


def _jp_reliability(value: str) -> str:
    return {"high": "高", "medium": "中", "low": "低"}.get(value, value)


def _display_number(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if math.isnan(value):
            return "-"
        return f"{value:.4f}"
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
