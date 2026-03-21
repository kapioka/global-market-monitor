from __future__ import annotations

from typing import Any


def build_alerts(
    regime: dict[str, Any],
    spot_signal: dict[str, Any],
    credit_monitor: list[dict[str, Any]],
    inflation_monitor: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    credit_flag = str(regime.get("credit_regime_flag", "neutral"))
    inflation_flag = str(regime.get("inflation_regime_flag", "neutral"))
    regime_label = str(regime.get("regime_label", ""))
    by_inflation_ticker = {str(row.get("ticker")): row for row in inflation_monitor}
    oil_signal = str(by_inflation_ticker.get("CL=F", {}).get("signal_label", ""))
    dollar_signal = str(by_inflation_ticker.get("DX-Y.NYB", {}).get("signal_label", ""))
    wheat_signal = str(by_inflation_ticker.get("ZW=F", {}).get("signal_label", ""))
    corn_signal = str(by_inflation_ticker.get("ZC=F", {}).get("signal_label", ""))
    mortgage_signal = str(by_inflation_ticker.get("FRED:MORTGAGE30US", {}).get("signal_label", "")) or str(
        by_inflation_ticker.get("^TNX", {}).get("signal_label", "")
    )
    life_pressure_count = 0

    if credit_flag == "credit_stress_severe":
        alerts.append(
            _alert(
                "credit_stress_severe",
                "market",
                "high",
                "信用ストレス強め",
                "信用市場の悪化が強く、株価の見た目より地合いが重い局面です。",
                ["HYG", "HYG/LQD"],
                [credit_flag, regime_label],
            )
        )
    elif credit_flag == "credit_stress_moderate":
        alerts.append(
            _alert(
                "credit_stress_moderate",
                "market",
                "moderate",
                "信用ストレス中程度",
                "信用市場で悪化の兆しが出ており、リスク資産の戻りを慎重に見る局面です。",
                ["HYG/LQD"],
                [credit_flag, regime_label],
            )
        )

    if inflation_flag == "stagflation_warning":
        life_pressure_count += 1
        alerts.append(
            _alert(
                "stagflation_warning",
                "life",
                "high",
                "スタグフレーション警戒",
                "原油高、ドル高、金上昇が重なり、生活コストと景気の両面に逆風が出やすい局面です。",
                ["CL=F", "DX-Y.NYB", "GC=F"],
                [inflation_flag, regime_label],
            )
        )
    elif inflation_flag in {"inflation_shock_broad", "inflation_shock_oil_only"}:
        life_pressure_count += 1
        alerts.append(
            _alert(
                "living_cost_pressure",
                "life",
                "moderate",
                "生活コスト上昇警戒",
                "資源価格と為替の影響で、生活関連コストの上振れに注意が必要な局面です。",
                ["CL=F", "DX-Y.NYB"] if inflation_flag == "inflation_shock_broad" else ["CL=F"],
                [inflation_flag, regime_label],
            )
        )

    if oil_signal == "インフレ圧力上昇" and dollar_signal == "ドル高進行":
        life_pressure_count += 1
        alerts.append(
            _alert(
                "purchasing_power_pressure",
                "life",
                "moderate",
                "購買力低下警戒",
                "原油高とドル高が同時に進み、輸入コストや購買力の低下を意識しやすい局面です。",
                ["CL=F", "DX-Y.NYB"],
                [inflation_flag],
            )
        )

    food_pressure = any(signal == "食品価格上昇圧力" for signal in {wheat_signal, corn_signal})
    if food_pressure:
        life_pressure_count += 1
        evidence = [ticker for ticker, signal in (("ZW=F", wheat_signal), ("ZC=F", corn_signal)) if signal == "食品価格上昇圧力"]
        if dollar_signal == "ドル高進行":
            evidence.append("DX-Y.NYB")
        alerts.append(
            _alert(
                "food_price_pressure",
                "life",
                "moderate",
                "食品価格警戒",
                "穀物価格の上昇が見られ、為替や輸送コスト次第では食料品価格へ波及しやすい局面です。",
                evidence,
                [wheat_signal, corn_signal, dollar_signal],
            )
        )

    if mortgage_signal == "住宅ローン負担上昇":
        life_pressure_count += 1
        alerts.append(
            _alert(
                "mortgage_burden_pressure",
                "life",
                "moderate",
                "住宅ローン負担警戒",
                "長期金利が上がっており、住宅ローンや借入負担の重さを意識しやすい局面です。",
                ["FRED:MORTGAGE30US"] if str(by_inflation_ticker.get("FRED:MORTGAGE30US", {}).get("signal_label", "")) == "住宅ローン負担上昇" else ["^TNX"],
                [mortgage_signal, regime_label],
            )
        )

    if regime_label in {"risk_off", "credit_stress"} and credit_flag in {"credit_stress_severe", "credit_stress_moderate"}:
        alerts.append(
            _alert(
                "slowdown_warning",
                "market",
                "moderate",
                "景気減速警戒",
                "リスク回避と信用悪化が重なっており、景気減速を意識しやすい局面です。",
                ["ACWI", "HYG/LQD"],
                [regime_label, credit_flag],
            )
        )

    if bool(spot_signal.get("risk_off_relief_applied", False)):
        alerts.append(
            _alert(
                "risk_off_relief_applied",
                "market",
                "low",
                "risk_off救済あり",
                "リスクオフでも元スコアが比較的高く、監視継続へ救済されたケースです。",
                ["adjusted_score", "regime_penalty"],
                [regime_label],
            )
        )

    if credit_flag == "credit_improving":
        alerts.append(
            _alert(
                "credit_improving",
                "memo",
                "low",
                "信用改善",
                "信用市場は持ち直し寄りで、悪化一辺倒ではない状態です。",
                ["HYG/LQD"],
                [credit_flag],
            )
        )

    if regime_label == "early_recovery":
        alerts.append(
            _alert(
                "early_recovery",
                "memo",
                "low",
                "初期回復",
                "地合いはまだ強気一色ではないものの、回復初期の兆しが見える状態です。",
                ["ACWI", "HYG/LQD"],
                [regime_label],
            )
        )

    if regime_label in {"credit_stress", "stagflation_warning"}:
        alerts.append(
            _alert(
                "defense_priority",
                "memo",
                "moderate",
                "防御優先",
                "この局面では攻めより守りを優先し、資金配分や追加投資を慎重に扱う方が妥当です。",
                ["adjusted_score", "regime_penalty"],
                [regime_label],
            )
        )

    if life_pressure_count >= 2:
        alerts.append(
            _alert(
                "household_defense_warning",
                "life",
                "high" if life_pressure_count >= 3 else "moderate",
                "家計防衛警戒",
                "生活影響の警戒灯が複数同時に点灯しており、支出管理や追加投資を慎重に扱いたい局面です。",
                ["life_pressure_count"],
                [str(life_pressure_count), inflation_flag, regime_label],
            )
        )

    return alerts


def _alert(
    alert_id: str,
    category: str,
    severity: str,
    title: str,
    message: str,
    evidence: list[str],
    source_flags: list[str],
) -> dict[str, Any]:
    return {
        "id": alert_id,
        "category": category,
        "severity": severity,
        "title": title,
        "message": message,
        "evidence": evidence,
        "source_flags": source_flags,
    }
