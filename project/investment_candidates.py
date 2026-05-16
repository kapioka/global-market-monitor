from __future__ import annotations

from typing import Any


def build_investment_candidates(
    report_inputs: dict[str, Any],
) -> dict[str, Any]:
    spot_signal = report_inputs.get("spot_signal", {})
    reliability = report_inputs.get("data_reliability", {})
    alerts = report_inputs.get("alerts", [])
    asset_compare = report_inputs.get("asset_compare", [])
    sector_rotation = report_inputs.get("sector_rotation", {})

    primary_action = spot_signal.get("action_decision", {}).get("action")
    spot_action = str(primary_action or spot_signal.get("action", ""))
    legacy_action = str(spot_signal.get("legacy_action", spot_signal.get("action", "")))
    reliability_level = str(reliability.get("level", "low"))
    decision_allowed = bool(reliability.get("decision_allowed", False))
    market_high_alert = any(
        alert.get("category") == "market" and alert.get("severity") == "high"
        for alert in alerts
    )
    sector_table = sector_rotation.get("table", []) if isinstance(sector_rotation, dict) else []

    asset_candidate = asset_compare[0] if asset_compare else None
    sector_candidate = sector_table[0] if sector_table else None
    usable_asset = asset_candidate is not None
    usable_sector = sector_candidate is not None

    if (
        spot_action == "buy_window"
        and decision_allowed
        and usable_asset
        and usable_sector
    ):
        return {
            "tier": "priority",
            "label": "優先候補",
            "summary": "強めに監視してよい候補があります。",
            "preferred_asset_class": _asset_payload(asset_candidate),
            "preferred_sector": _sector_payload(sector_candidate),
            "candidate_tickers": _candidate_tickers(asset_candidate, sector_candidate),
            "rationale": [
                "スポット投資判断が買い検討ゾーンです。",
                "判定信頼性が確保されており、通常ロジックを継続できます。",
                "高重要度の市場警告があるため、強い推奨ではなく参考候補として扱ってください。" if market_high_alert else "高重要度の市場警告は発火していません。",
                "資産クラスとセクターの両方で相対優位が確認できています。",
            ],
        }

    if (
        spot_action in {"buy_window", "watch"}
        and reliability_level in {"high", "medium"}
        and (usable_asset or usable_sector)
        and report_inputs.get("regime", {}).get("regime_label") != "data_unavailable"
    ):
        candidate_tickers = _candidate_tickers(asset_candidate, sector_candidate)
        return {
            "tier": "watch",
            "label": "観察候補",
            "summary": "まだ強い推奨ではないものの、追う価値のある候補です。",
            "preferred_asset_class": _asset_payload(asset_candidate) if usable_asset else None,
            "preferred_sector": _sector_payload(sector_candidate) if usable_sector else None,
            "candidate_tickers": candidate_tickers,
            "rationale": [
                f"スポット投資判断は {spot_action} です。",
                f"legacy 判定は {legacy_action} です。" if legacy_action != spot_action else f"legacy 判定との差はありません。",
                f"判定信頼性は {reliability_level} で、極端なデータ不足ではありません。",
                "高重要度の市場警告があるため、売買推奨ではなく参考候補として見てください。" if market_high_alert else "高重要度の市場警告は候補抽出を妨げていません。",
                "相対比較で優位な資産かセクターが少なくとも一つあります。",
            ],
        }

    if (
        decision_allowed
        and reliability_level in {"high", "medium"}
        and (usable_asset or usable_sector)
        and report_inputs.get("regime", {}).get("regime_label") != "data_unavailable"
    ):
        candidate_tickers = _candidate_tickers(asset_candidate, sector_candidate)
        return {
            "tier": "reference",
            "label": "参考候補",
            "summary": "売買推奨ではなく、相対優位の確認用に表示している参考候補です。",
            "preferred_asset_class": _asset_payload(asset_candidate) if usable_asset else None,
            "preferred_sector": _sector_payload(sector_candidate) if usable_sector else None,
            "candidate_tickers": candidate_tickers,
            "rationale": [
                f"スポット投資判断は {spot_action} で、積極的な候補提示向きではありません。",
                f"legacy 判定は {legacy_action} です。" if legacy_action != spot_action else f"legacy 判定との差はありません。",
                f"判定信頼性は {reliability_level} で、比較自体は継続できます。",
                "高重要度の市場警告があるため、売買推奨ではなく参考候補として見てください。" if market_high_alert else "相対比較の知見として参考候補を表示しています。",
                "資産かセクターの少なくとも一方で相対優位が確認できています。",
            ],
        }

    return {
        "tier": "none",
        "label": "候補なし",
        "summary": "現時点では候補提示を見送ります。",
        "preferred_asset_class": None,
        "preferred_sector": None,
        "candidate_tickers": [],
        "rationale": _no_candidate_reasons(
            spot_action=spot_action,
            reliability_level=reliability_level,
            decision_allowed=decision_allowed,
            market_high_alert=market_high_alert,
            usable_asset=usable_asset,
            usable_sector=usable_sector,
        ),
    }


def _asset_payload(asset_candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if asset_candidate is None:
        return None
    return {
        "asset_class": asset_candidate.get("asset_class"),
        "ticker": asset_candidate.get("ticker"),
        "ticker_name_ja": asset_candidate.get("ticker_name_ja"),
        "momentum_12w": asset_candidate.get("momentum_12w"),
    }


def _sector_payload(sector_candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if sector_candidate is None:
        return None
    return {
        "ticker": sector_candidate.get("ticker"),
        "sector_name_ja": sector_candidate.get("sector_name_ja"),
        "return_12w": sector_candidate.get("return_12w"),
        "rotation_phase_ja": sector_candidate.get("rotation_phase_ja"),
    }


def _candidate_tickers(
    asset_candidate: dict[str, Any] | None,
    sector_candidate: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    if asset_candidate and asset_candidate.get("ticker") not in seen:
        seen.add(str(asset_candidate.get("ticker")))
        candidates.append(
            {
                "ticker": asset_candidate.get("ticker"),
                "label": asset_candidate.get("ticker_name_ja") or asset_candidate.get("asset_class"),
                "kind": "asset",
            }
        )
    if sector_candidate and sector_candidate.get("ticker") not in seen:
        seen.add(str(sector_candidate.get("ticker")))
        candidates.append(
            {
                "ticker": sector_candidate.get("ticker"),
                "label": sector_candidate.get("sector_name_ja"),
                "kind": "sector",
            }
        )
    return candidates


def _no_candidate_reasons(
    *,
    spot_action: str,
    reliability_level: str,
    decision_allowed: bool,
    market_high_alert: bool,
    usable_asset: bool,
    usable_sector: bool,
) -> list[str]:
    reasons: list[str] = []
    if spot_action not in {"buy_window", "watch"}:
        reasons.append("スポット投資判断が候補提示に向く状態ではありません。参考候補のみ検討余地があります。")
    if not decision_allowed:
        reasons.append("重要系列の live 取得不足により、通常判断を保留しています。")
    elif reliability_level not in {"high", "medium"}:
        reasons.append("判定信頼性が低いため、候補提示を見送ります。")
    if market_high_alert:
        reasons.append("高重要度の市場警告があるため、候補提示を抑制しています。")
    if not usable_asset and not usable_sector:
        reasons.append("資産クラス比較とセクター比較の両方で十分な比較結果がありません。")
    return reasons or ["候補提示の条件がまだ揃っていません。"]
