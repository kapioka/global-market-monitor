from __future__ import annotations

import json
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from project.alerts import build_alerts
from project.analogue_search import find_analogues
from project.asset_compare import compare_asset_classes
from project.buy_decision_card import build_buy_decision_card
from project.credit_monitor import build_credit_monitor
from project.cycle_analysis import analyze_cycle
from project.data_fetcher import FetchResult, fetch_market_data
from project.data_provenance import build_report_data_provenance
from project.decision_attribution import build_decision_attribution
from project.decision_boundary_experiment import build_decision_boundary_experiment
from project.domestic_danger_context import build_domestic_danger_context
from project.domestic_market_metrics import build_domestic_market_metrics
from project.fx_risk_policy import apply_fx_policy_candidate, classify_fx_policy
from project.hindenburg_omen import build_hindenburg_omen_context
from project.inflation_monitor import build_inflation_monitor
from project.investment_candidates import build_investment_candidates
from project.japan_macro_adapters import build_optional_japan_macro_context
from project.japan_resident_integrated_context import build_japan_resident_integrated_risk_context
from project.japan_risk_monitor import build_japan_risk_monitor
from project.multi_asset_candidates import build_multi_asset_candidates
from project.oil_context import attach_oil_context_to_rows, build_oil_context
from project.preprocess import compute_returns, preprocess_prices
from project.recovery_candidates import build_recovery_candidates
from project.regime_analysis import analyze_market_regime
from project.regime_leading_candidates import build_regime_leading_candidates
from project.reliability_policy import assess_data_reliability
from project.risk_domain_state import apply_risk_domain_persistence, default_risk_domain_state_path, load_risk_domain_state
from project.risk_domains import evaluate_risk_domains
from project.risk_line_confidence_audit import build_risk_line_confidence_audit
from project.risk_line_review_status import load_risk_line_review_status
from project.risk_line_threshold_drift_report import load_risk_line_threshold_drift_snapshot
from project.risk_line_threshold_store import load_threshold_payload
from project.risk_lines import evaluate_risk_lines
from project.scoring import score_market, score_recovery_evidence
from project.sector_rotation import analyze_sector_rotation
from project.spot_signal import evaluate_spot_signal
from project.stress_monitor import build_stress_monitor, default_risk_indicator_map
from project.threshold_certainty import build_threshold_certainty
from project.threshold_decision_policy import build_threshold_usage
from project.threshold_metadata import metadata_for_payload
from project.threshold_rule_certification_report import load_threshold_rule_certification_summary


def collect_tickers(config: dict[str, Any]) -> list[str]:
    ticker_groups = config["tickers"]
    tickers: list[str] = []
    for mapping in ticker_groups.values():
        tickers.extend(mapping.values())
    official_series = (config.get("risk_engine_v2") or {}).get("official_series") or {}
    if isinstance(official_series, dict):
        tickers.extend(str(value) for value in official_series.values() if value)
    deduped: list[str] = []
    for ticker in tickers:
        if ticker not in deduped:
            deduped.append(ticker)
    return deduped


def fetch_market_snapshot(
    config: dict[str, Any],
    logger: Any,
    sample_only: bool = False,
    interval_override: str | None = None,
) -> FetchResult:
    tickers = collect_tickers(config)
    return fetch_market_data(
        tickers=tickers,
        period_years=config["data"]["period_years"],
        interval=interval_override or config["data"]["interval"],
        logger=logger,
        use_sample_on_failure=True if sample_only else config["data"]["use_sample_on_failure"],
        cache_dir=config["paths"]["cache_dir"],
        force_sample=sample_only,
    )


def generated_at_for_date(config: dict[str, Any], as_of_date: date | None) -> str:
    if as_of_date is None:
        return datetime.now().isoformat(timespec="seconds")
    scheduler_config = config.get("scheduler", {})
    hour = int(scheduler_config.get("hour", 7))
    minute = int(scheduler_config.get("minute", 30))
    return datetime.combine(as_of_date, time(hour=hour, minute=minute)).isoformat(timespec="seconds")


def resample_weekly_closes(prices: Any) -> Any:
    if prices.empty:
        return prices
    weekly = prices.resample("W-FRI").last().dropna(how="all")
    if not weekly.empty:
        latest_observation = prices.dropna(how="all").index.max()
        if latest_observation is not None:
            weekly = weekly.loc[weekly.index <= latest_observation]
    return weekly.ffill()


def build_report(
    config: dict[str, Any],
    fetch: FetchResult,
    as_of_date: date | None = None,
    resample_weekly: bool = False,
    maintenance_summary: dict[str, Any] | None = None,
    history_alignment: dict[str, Any] | None = None,
    japan_macro_context: dict[str, Any] | None = None,
    episode_chronicle_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at_for_date(config, as_of_date)
    prices = fetch.prices
    if as_of_date is not None and not prices.empty:
        cutoff = datetime.combine(as_of_date, time.max)
        prices = prices.loc[prices.index <= cutoff]
    if resample_weekly:
        prices = resample_weekly_closes(prices)

    prices, preprocessing_warnings = preprocess_prices(prices, config["data"]["min_history_points"])
    data_provenance = build_report_data_provenance(
        prices,
        generated_at=generated_at,
        fetch_diagnostics=fetch.diagnostics,
        data_source=fetch.source,
        as_of_date=as_of_date,
        freshness_max_business_days=int(config.get("data", {}).get("freshness_max_business_days", 2)),
    )
    returns = compute_returns(prices)
    availability_map = {entry.get("requested_ticker"): entry for entry in fetch.acquisition_log}

    credit_monitor = build_credit_monitor(
        prices,
        config["tickers"].get("credit", {}),
        config["data"].get("monitor_windows_weeks", {"short": 1, "medium": 4, "long": 12}),
        int(config["data"].get("zscore_window_weeks", 52)),
    )
    inflation_monitor = build_inflation_monitor(
        prices,
        config["tickers"].get("inflation", {}),
        config["data"].get("monitor_windows_weeks", {"short": 1, "medium": 4, "long": 12}),
        int(config["data"].get("zscore_window_weeks", 52)),
    )
    active_threshold_payload = load_threshold_payload()
    paths = config.get("paths", {})
    reports_dir = paths.get("reports_dir")
    risk_threshold_drift = load_risk_line_threshold_drift_snapshot(reports_dir) if reports_dir else None
    action_validation = load_action_validation_summary(reports_dir) if reports_dir else {}
    buy_window_diagnostics = load_buy_window_diagnostics_summary(reports_dir) if reports_dir else {}
    japan_fx_downgrade_diagnostics = load_japan_fx_downgrade_diagnostics_summary(reports_dir) if reports_dir else {}
    buy_candidate_near_miss = load_buy_candidate_near_miss_summary(reports_dir) if reports_dir else {}
    fx_policy_replay = load_fx_policy_replay_summary(reports_dir) if reports_dir else {}
    fx_soft_cap_historical_replay = load_fx_soft_cap_historical_replay_summary(reports_dir) if reports_dir else {}
    fx_conditional_soft_cap_replay = load_fx_conditional_soft_cap_replay_summary(reports_dir) if reports_dir else {}
    fx_soft_cap_dd_guard_replay = load_fx_soft_cap_dd_guard_replay_summary(reports_dir) if reports_dir else {}
    fx_soft_cap_balanced_guard = load_fx_soft_cap_balanced_guard_summary(reports_dir) if reports_dir else {}
    fx_soft_cap_long_range_guard_replay = load_fx_soft_cap_long_range_guard_replay_summary(reports_dir) if reports_dir else {}
    regime_aware_fx_policy_replay = load_regime_aware_fx_policy_replay_summary(reports_dir) if reports_dir else {}
    risk_engine_v2_replay = load_risk_engine_v2_replay_summary(reports_dir) if reports_dir else {}
    risk_engine_v2_reconstructed_replay = load_risk_engine_v2_reconstructed_replay_summary(reports_dir) if reports_dir else {}
    risk_engine_v2_holdout_validation = load_risk_engine_v2_holdout_validation_summary(reports_dir) if reports_dir else {}
    risk_engine_v2_episode_chronicle = (
        dict(episode_chronicle_summary)
        if episode_chronicle_summary is not None
        else load_risk_engine_v2_episode_chronicle_summary(reports_dir) if reports_dir else {}
    )
    fx_soft_cap_watchlist = load_fx_soft_cap_watchlist_summary(reports_dir) if reports_dir else {}
    proposed_threshold_payload = load_threshold_payload(Path(__file__).resolve().parent / "risk_line_thresholds_proposed.json")
    proposed_metadata = metadata_for_payload(proposed_threshold_payload)
    threshold_replay_summary = load_threshold_replay_summary(reports_dir)
    threshold_certainty = build_threshold_certainty(
        active_summary=_active_threshold_certainty_summary(action_validation, threshold_replay_summary),
        proposed_summary=threshold_replay_summary.get("proposed", {}),
        candidate_summary=load_candidate_v2_summary(reports_dir) or threshold_replay_summary.get("proposed", {}),
        metadata_summary=proposed_metadata,
    )
    threshold_rule_certification = load_threshold_rule_certification_summary(reports_dir)
    threshold_usage = build_threshold_usage(threshold_certainty, proposed_metadata, threshold_rule_certification)
    risk_threshold_review = (
        load_risk_line_review_status(
            reports_dir,
            active_threshold_payload,
            config.get("risk_line_recalibration", {}),
        )
        if reports_dir
        else None
    )
    risk_monitor = build_stress_monitor(
        prices,
        default_risk_indicator_map(config),
        config["data"].get("monitor_windows_weeks", {"short": 1, "medium": 4, "long": 12}),
        int(config["data"].get("zscore_window_weeks", 52)),
        threshold_definitions=active_threshold_payload.get("indicators", {}),
    )
    japan_risk = build_japan_risk_monitor(
        prices,
        config["tickers"].get("asset_classes", {}),
        config["tickers"].get("japan", {}),
        config["data"].get("monitor_windows_weeks", {"short": 1, "medium": 4, "long": 12}),
        int(config["data"].get("zscore_window_weeks", 52)),
        settings=config.get("japan_risk", {}),
    )
    japan_macro_context = japan_macro_context if japan_macro_context is not None else build_optional_japan_macro_context()
    usable_credit_monitor = _filter_live_monitor_rows(credit_monitor, availability_map)
    usable_inflation_monitor = _filter_live_monitor_rows(inflation_monitor, availability_map)
    usable_risk_monitor = _filter_live_monitor_rows(risk_monitor, availability_map)
    oil_context = build_oil_context(usable_risk_monitor, settings=config.get("risk_engine_v2", {}))
    usable_risk_monitor = attach_oil_context_to_rows(usable_risk_monitor, oil_context)
    reliability = assess_data_reliability(config, fetch)
    sector_vector_config = config.get("sector_vector_analysis", {})
    sector_rotation = analyze_sector_rotation(prices, config["tickers"]["sector_etfs"], vector_config=sector_vector_config)
    regime = analyze_market_regime(
        prices,
        returns,
        usable_credit_monitor,
        usable_inflation_monitor,
        config["thresholds"],
        sector_rotation=sector_rotation,
        sector_config=sector_vector_config,
    )
    cycle_ticker = regime["benchmark"]
    cycle = analyze_cycle(prices[cycle_ticker])
    risk_lines = evaluate_risk_lines(regime, cycle, usable_credit_monitor, usable_inflation_monitor, usable_risk_monitor)
    risk_line_confidence_audit = build_risk_line_confidence_audit(active_threshold_payload, risk_lines)
    hindenburg_omen_config = config.get("hindenburg_omen", {})
    hindenburg_omen_context = build_hindenburg_omen_context(
        auto_csv_url=hindenburg_omen_config.get("auto_csv_url"),
        auto_fetch=bool(hindenburg_omen_config.get("auto_fetch", True)),
        experimental_builtin_auto_fetch=bool(hindenburg_omen_config.get("builtin_auto_fetch_experimental", True)),
        provider_priority=list(hindenburg_omen_config.get("provider_priority", [])) or None,
    )
    score = score_market(
        regime,
        cycle,
        usable_credit_monitor,
        config["weights"],
        config["thresholds"],
        risk_monitor=usable_risk_monitor,
        sector_rotation=sector_rotation,
        sector_config=sector_vector_config,
    )
    recovery_evidence = score_recovery_evidence(
        regime,
        cycle,
        usable_credit_monitor,
        config["thresholds"],
        sector_rotation=sector_rotation,
    )
    asset_compare = compare_asset_classes(prices, config["tickers"]["asset_classes"])
    domestic_market_metrics = build_domestic_market_metrics(
        prices,
        acquisition_log=fetch.acquisition_log,
        data_provenance=data_provenance,
    )
    spot_signal = evaluate_spot_signal(
        score,
        regime,
        cycle,
        usable_credit_monitor,
        usable_inflation_monitor,
        config["thresholds"],
        risk_lines=risk_lines,
        sector_rotation=sector_rotation,
        sector_config=sector_vector_config,
        recovery_evidence=recovery_evidence,
        japan_risk=japan_risk,
        japan_risk_config=config.get("japan_risk", {}),
        reliability_policy=reliability,
    )
    alerts = build_alerts(
        regime, spot_signal, usable_credit_monitor, usable_inflation_monitor, risk_lines=risk_lines, japan_risk=japan_risk
    )
    analogues = find_analogues(prices[cycle_ticker], max_results=config["data"]["max_analogue_results"])

    warnings = fetch.warnings + preprocessing_warnings
    if not reliability["decision_allowed"]:
        regime = _guarded_regime(regime, reliability)
        cycle = _guarded_cycle(cycle)
        score = _guarded_score(score)
        risk_lines = _guarded_risk_lines(reliability)
        spot_signal = _guarded_spot_signal(reliability)
        alerts = [_data_quality_alert(reliability)]
        sector_rotation = {"table": [], "chart": {}, "history": [], "integration_signals": {}, "internal_structure": {}}
        asset_compare = []
        analogues = []
        warnings.append(reliability["reason"])
    elif risk_lines.get("strict_missing_indicators"):
        warnings.append(risk_lines["summary"])
    risk_domains = evaluate_risk_domains(
        stress_monitor=usable_risk_monitor,
        credit_monitor=usable_credit_monitor,
        inflation_monitor=usable_inflation_monitor,
        config=config,
        available_series={str(column) for column in prices.columns if prices[column].notna().any()},
    )
    risk_engine_state: dict[str, Any] = {"status": "not_configured", "will_persist": False}
    if reports_dir:
        risk_engine_state_path = default_risk_domain_state_path(reports_dir)
        previous_risk_domain_state = load_risk_domain_state(risk_engine_state_path)
        risk_domains, next_risk_domain_state = apply_risk_domain_persistence(
            risk_domains,
            previous_state=previous_risk_domain_state,
            settings=config.get("risk_engine_v2", {}),
            generated_at=generated_at,
        )
        risk_engine_state = {
            "status": "ready",
            "path": str(risk_engine_state_path),
            "previous_state_loaded": not bool(previous_risk_domain_state.get("load_error")),
            "will_persist": bool(reliability.get("decision_allowed", False)),
            "next_state": next_risk_domain_state,
        }
    risk_engine_comparison = _build_risk_engine_comparison(risk_lines, risk_domains)
    investment_candidates = build_investment_candidates(
        {
            "regime": regime,
            "spot_signal": spot_signal,
            "data_reliability": reliability,
            "alerts": alerts,
            "asset_compare": asset_compare,
            "sector_rotation": sector_rotation,
        }
    )
    multi_asset_candidates = build_multi_asset_candidates(
        {
            "asset_map": config["tickers"].get("asset_classes", {}),
            "availability_map": availability_map,
            "asset_compare": asset_compare,
            "inflation_monitor": usable_inflation_monitor,
            "credit_monitor": usable_credit_monitor,
            "investment_candidates": investment_candidates,
            "data_reliability": reliability,
            "risk_lines": risk_lines,
            "japan_risk": japan_risk,
            "japan_tickers": config["tickers"].get("japan", {}),
            "japan_resident_context": japan_macro_context,
            "acquisition_log": fetch.acquisition_log,
            "domestic_market_metrics": domestic_market_metrics,
        }
    )
    domestic_danger_context = build_domestic_danger_context(
        {
            "multi_asset_candidates": multi_asset_candidates,
            "japan_risk": japan_risk,
            "japan_resident_context": japan_macro_context,
            "acquisition_log": fetch.acquisition_log,
            "domestic_market_metrics": domestic_market_metrics,
        }
    )
    japan_resident_integrated_risk_context = build_japan_resident_integrated_risk_context(
        {
            "risk_lines": risk_lines,
            "risk_line_confidence_audit": risk_line_confidence_audit,
            "domestic_danger_context": domestic_danger_context,
            "japan_risk": japan_risk,
            "japan_resident_context": japan_macro_context,
            "domestic_market_metrics": domestic_market_metrics,
        }
    )
    recovery_candidates = build_recovery_candidates(
        prices=prices,
        asset_map=config["tickers"]["asset_classes"],
        sector_map=config["tickers"]["sector_etfs"],
        availability_map=availability_map,
        regime=regime,
        cycle=cycle,
        reliability=reliability,
        alerts=alerts,
    )
    regime_leading_candidates = build_regime_leading_candidates(
        prices=prices,
        sector_map=config["tickers"]["sector_etfs"],
        region_map=config["tickers"].get("global_equities", {}),
        asset_map=config["tickers"].get("asset_classes", {}),
        sector_rotation=sector_rotation,
        availability_map=availability_map,
        regime=regime,
        reliability=reliability,
        alerts=alerts,
        integration_settings=sector_vector_config,
    )
    decision_attribution = build_decision_attribution(spot_signal, risk_lines, reliability)
    fx_policy_diagnostics = build_fx_policy_diagnostics(spot_signal, japan_risk)
    report = {
        "title": config["app"]["report_title"],
        "generated_at": generated_at,
        "history_alignment": history_alignment or {},
        "data_source": fetch.source,
        "data_provenance": data_provenance,
        "runtime_context": _runtime_context(),
        "fetch_diagnostics": fetch.diagnostics,
        "data_reliability": reliability,
        "reliability_policy": reliability,
        "regime": regime,
        "cycle": cycle,
        "score": score,
        "sector_rotation": sector_rotation,
        "asset_compare": asset_compare,
        "credit_monitor": usable_credit_monitor,
        "inflation_monitor": usable_inflation_monitor,
        "risk_monitor": usable_risk_monitor,
        "oil_context": oil_context,
        "japan_risk": japan_risk,
        "japan_resident_context": japan_macro_context,
        "risk_thresholds": active_threshold_payload.get("threshold_set", {}),
        "risk_threshold_drift": risk_threshold_drift,
        "risk_threshold_review": risk_threshold_review,
        "risk_threshold_maintenance": maintenance_summary or {},
        "threshold_certainty": threshold_certainty,
        "threshold_usage": threshold_usage,
        "threshold_rule_certification": threshold_rule_certification,
        "risk_lines": risk_lines,
        "risk_engine_schema_version": "2.0",
        "risk_engine_mode": str((config.get("risk_engine_v2") or {}).get("mode", "shadow")),
        "risk_domains": risk_domains,
        "risk_engine_state": risk_engine_state,
        "risk_engine_comparison": risk_engine_comparison,
        "risk_line_confidence_audit": risk_line_confidence_audit,
        "hindenburg_omen_context": hindenburg_omen_context,
        "spot_signal": spot_signal,
        "decision_attribution": decision_attribution,
        "action_validation": action_validation,
        "buy_window_diagnostics": buy_window_diagnostics,
        "japan_fx_downgrade_diagnostics": japan_fx_downgrade_diagnostics,
        "buy_candidate_near_miss": buy_candidate_near_miss,
        "fx_policy_replay": fx_policy_replay,
        "fx_soft_cap_historical_replay": fx_soft_cap_historical_replay,
        "fx_conditional_soft_cap_replay": fx_conditional_soft_cap_replay,
        "fx_soft_cap_dd_guard_replay": fx_soft_cap_dd_guard_replay,
        "fx_soft_cap_balanced_guard": fx_soft_cap_balanced_guard,
        "fx_soft_cap_long_range_guard_replay": fx_soft_cap_long_range_guard_replay,
        "regime_aware_fx_policy_replay": regime_aware_fx_policy_replay,
        "risk_engine_v2_replay": risk_engine_v2_replay,
        "risk_engine_v2_reconstructed_replay": risk_engine_v2_reconstructed_replay,
        "risk_engine_v2_holdout_validation": risk_engine_v2_holdout_validation,
        "risk_engine_v2_episode_chronicle": risk_engine_v2_episode_chronicle,
        "fx_policy_diagnostics": fx_policy_diagnostics,
        "fx_soft_cap_watchlist": fx_soft_cap_watchlist,
        "investment_candidates": investment_candidates,
        "multi_asset_candidates": multi_asset_candidates,
        "domestic_market_metrics": domestic_market_metrics,
        "domestic_danger_context": domestic_danger_context,
        "japan_resident_integrated_risk_context": japan_resident_integrated_risk_context,
        "recovery_candidates": recovery_candidates,
        "regime_leading_candidates": regime_leading_candidates,
        "alerts": alerts,
        "analogues": analogues,
        "warnings": warnings,
        "data_availability": fetch.acquisition_log,
    }
    report["buy_decision_card"] = build_buy_decision_card(report)
    report["decision_boundary_experiment"] = build_decision_boundary_experiment(report)
    return report


def _runtime_context() -> dict[str, Any]:
    executable = Path(sys.executable).resolve()
    return {
        "is_frozen": bool(getattr(sys, "frozen", False)),
        "python_executable": str(executable),
        "working_directory": str(Path.cwd().resolve()),
    }


def _build_risk_engine_comparison(risk_lines: dict[str, Any], risk_domains: dict[str, Any]) -> dict[str, Any]:
    return {
        "legacy_stage": risk_lines.get("stage_key", "normal"),
        "legacy_stage_label": risk_lines.get("stage_label", "-"),
        "legacy_composite_score": risk_lines.get("composite_risk_score"),
        "domain_v2_stage": risk_domains.get("stage", "normal"),
        "domain_v2_composite_score": risk_domains.get("composite_domain_score"),
        "domain_v2_independent_stressed_domain_count": risk_domains.get("independent_stressed_domain_count", 0),
        "domain_v2_strict_judgement_available": risk_domains.get("strict_judgement_available", False),
        "mode": risk_domains.get("engine_mode", "shadow"),
        "affects_final_action": False,
        "policy_status": "shadow_only",
    }


def load_action_validation_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    summary_path = Path(reports_dir) / "action_validation_summary.json"
    if not summary_path.exists():
        return {"status": "not_available", "reason": "action validation summary has not been generated"}
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"action validation summary could not be loaded: {exc}"}


def load_buy_window_diagnostics_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    summary_path = Path(reports_dir) / "buy_window_diagnostics.json"
    if not summary_path.exists():
        return {"status": "not_available", "reason": "buy_window diagnostics has not been generated"}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"buy_window diagnostics could not be loaded: {exc}"}
    return {
        "status": payload.get("status"),
        "total_history_count": payload.get("total_history_count", 0),
        "raw_buy_window_count": payload.get("raw_buy_window_count", 0),
        "raw_buy_candidate_count": payload.get("raw_buy_candidate_count", 0),
        "risk_adjusted_buy_candidate_count": payload.get("risk_adjusted_buy_candidate_count", 0),
        "final_buy_window_count": payload.get("final_buy_window_count", 0),
        "final_buy_candidate_count": payload.get("final_buy_candidate_count", 0),
        "raw_buy_window_to_watch_count": payload.get("raw_buy_window_to_watch_count", 0),
        "raw_buy_window_to_wait_count": payload.get("raw_buy_window_to_wait_count", 0),
        "buy_candidate_to_buy_window_transition_count": payload.get("buy_candidate_to_buy_window_transition_count", 0),
        "buy_candidate_to_wait_downgrade_count": payload.get("buy_candidate_to_wait_downgrade_count", 0),
        "buy_candidate_performance": payload.get("buy_candidate_performance", {}),
        "blocker_counts": payload.get("blocker_counts", {}),
        "buy_window_zero_reason_summary": payload.get("buy_window_zero_reason_summary", []),
    }


def build_fx_policy_diagnostics(spot_signal: dict[str, Any], japan_risk: dict[str, Any]) -> dict[str, Any]:
    action_decision = spot_signal.get("action_decision") or {}
    blocker = spot_signal.get("blocker_assessment") or {}
    raw_action = str(
        action_decision.get("market_raw_action")
        or action_decision.get("raw_action")
        or spot_signal.get("legacy_action")
        or spot_signal.get("action")
        or "wait"
    )
    current_final = str(action_decision.get("final_action") or action_decision.get("action") or spot_signal.get("action") or "wait")
    classification = classify_fx_policy(japan_risk, blocker)
    soft_cap = apply_fx_policy_candidate(raw_action, classification, "fx_soft_cap")
    return {
        "current_final_action": current_final,
        "fx_soft_cap_action": soft_cap["final_action"],
        "fx_soft_cap_affects_final_action": False,
        "reason": "FX moderate/headwind would cap buy_window to buy_candidate instead of watch.",
        "policy_status": "diagnostic_only",
        "fx_policy_classification": classification,
        "execution_note": soft_cap.get("execution_note", ""),
    }


def load_japan_fx_downgrade_diagnostics_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "japan_fx_downgrade_diagnostics.json"
    if not path.exists():
        return {"status": "not_available", "reason": "japan FX downgrade diagnostics has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"japan FX downgrade diagnostics could not be loaded: {exc}"}
    return {
        "status": payload.get("status"),
        "raw_buy_window_downgraded_by_fx_count": payload.get("raw_buy_window_downgraded_by_fx_count", 0),
        "raw_buy_candidate_downgraded_by_fx_count": payload.get("raw_buy_candidate_downgraded_by_fx_count", 0),
        "japan_fx_risk_moderate_count": payload.get("japan_fx_risk_moderate_count", 0),
        "japan_fx_risk_high_count": payload.get("japan_fx_risk_high_count", 0),
        "foreign_asset_fx_headwind_count": payload.get("foreign_asset_fx_headwind_count", 0),
        "classification_counts": payload.get("classification_counts", {}),
    }


def load_buy_candidate_near_miss_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "buy_candidate_near_miss.json"
    if not path.exists():
        return {"status": "not_available", "reason": "buy_candidate near-miss diagnostics has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"buy_candidate near-miss diagnostics could not be loaded: {exc}"}
    missing = payload.get("missing_condition_counts") or {}
    top_missing = "-"
    if missing:
        top_missing = sorted(missing.items(), key=lambda item: int(item[1] or 0), reverse=True)[0][0]
    return {
        "status": payload.get("status"),
        "near_miss_count": payload.get("near_miss_count", 0),
        "missing_condition_counts": missing,
        "top_missing_condition": top_missing,
    }


def load_fx_policy_replay_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "fx_policy_replay.json"
    if not path.exists():
        return {"status": "not_available", "reason": "FX policy replay has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"FX policy replay could not be loaded: {exc}"}
    near = payload.get("near_miss_effect") or {}
    return {
        "status": payload.get("status"),
        "policy": payload.get("policy"),
        "converted_to_buy_candidate_by_fx_note_only": near.get("converted_to_buy_candidate_by_fx_note_only", 0),
        "converted_to_buy_candidate_by_fx_soft_cap": near.get("converted_to_buy_candidate_by_fx_soft_cap", 0),
        "still_blocked_count": near.get("still_blocked_count", 0),
    }


def load_fx_soft_cap_watchlist_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "fx_soft_cap_watchlist.json"
    if not path.exists():
        return {"status": "not_available", "reason": "fx_soft_cap watchlist has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"fx_soft_cap watchlist could not be loaded: {exc}"}
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "adoption_decision": payload.get("adoption_decision", "hold"),
        "tracked_case_count": payload.get("tracked_case_count", 0),
        "ready_for_review_count": payload.get("ready_for_review_count", 0),
        "waiting_future_data_count": payload.get("waiting_future_data_count", 0),
        "historical_similarity": payload.get("historical_similarity", {}),
        "conditional_fx_soft_cap": payload.get("conditional_fx_soft_cap", {}),
    }


def load_fx_soft_cap_historical_replay_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "fx_soft_cap_historical_replay.json"
    if not path.exists():
        return {"status": "not_available", "reason": "fx_soft_cap historical replay has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"fx_soft_cap historical replay could not be loaded: {exc}"}
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "adoption_decision": payload.get("adoption_decision", "hold"),
        "total_replay_weeks": payload.get("total_replay_weeks", 0),
        "fx_soft_cap_buy_candidate_count": payload.get("fx_soft_cap_buy_candidate_count", 0),
        "current_watch_to_fx_soft_cap_buy_candidate_count": payload.get("current_watch_to_fx_soft_cap_buy_candidate_count", 0),
        "classification_counts": payload.get("classification_counts", {}),
        "return_summary": payload.get("return_summary", {}),
    }


def load_fx_conditional_soft_cap_replay_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "fx_conditional_soft_cap_replay.json"
    if not path.exists():
        return {"status": "not_available", "reason": "conditional fx_soft_cap replay has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"conditional fx_soft_cap replay could not be loaded: {exc}"}
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "best_candidate": payload.get("best_candidate", "-"),
        "adoption_decision": payload.get("adoption_decision", "hold"),
        "affects_final_action": payload.get("affects_final_action", False),
        "candidates": payload.get("candidates", []),
    }


def load_fx_soft_cap_dd_guard_replay_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "fx_soft_cap_dd_guard_replay.json"
    if not path.exists():
        return {"status": "not_available", "reason": "fx_soft_cap DD guard replay has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"fx_soft_cap DD guard replay could not be loaded: {exc}"}
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "best_guard": payload.get("best_guard", "-"),
        "adoption_decision": payload.get("adoption_decision", "hold"),
        "affects_final_action": payload.get("affects_final_action", False),
        "base_worst_dd_13w": payload.get("base_worst_dd_13w"),
        "best_worst_dd_13w": payload.get("best_worst_dd_13w"),
    }


def load_fx_soft_cap_balanced_guard_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "fx_soft_cap_balanced_guard.json"
    if not path.exists():
        return {"status": "not_available", "reason": "fx_soft_cap balanced guard has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"fx_soft_cap balanced guard could not be loaded: {exc}"}
    balanced = {}
    for row in payload.get("candidates", []):
        if row.get("candidate") == "balanced_dd_guard":
            balanced = row
            break
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "balanced_candidate": payload.get("balanced_candidate", "-"),
        "adoption_decision": payload.get("adoption_decision", "hold"),
        "affects_final_action": payload.get("affects_final_action", False),
        "buy_candidate_count": balanced.get("buy_candidate_count", 0),
        "missed_good_count": balanced.get("missed_candidate_count", 0),
        "correctly_blocked_count": balanced.get("correctly_blocked_count", 0),
        "return_summary": balanced.get("return_summary", {}),
    }


def load_fx_soft_cap_long_range_guard_replay_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "fx_soft_cap_long_range_guard_replay.json"
    if not path.exists():
        return {"status": "not_available", "reason": "fx_soft_cap long-range guard replay has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"fx_soft_cap long-range guard replay could not be loaded: {exc}"}
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "best_candidate": payload.get("best_candidate", "-"),
        "adoption_decision": payload.get("adoption_decision", "hold"),
        "affects_final_action": payload.get("affects_final_action", False),
        "replay_start": payload.get("replay_start"),
        "replay_end": payload.get("replay_end"),
        "usable_weeks": payload.get("usable_weeks", 0),
        "candidates": payload.get("candidates", []),
    }


def load_regime_aware_fx_policy_replay_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "regime_aware_fx_policy_replay.json"
    if not path.exists():
        return {"status": "not_available", "reason": "regime-aware FX policy replay has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"regime-aware FX policy replay could not be loaded: {exc}"}
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "best_candidate": payload.get("best_candidate", "-"),
        "adoption_decision": payload.get("adoption_decision", "hold"),
        "affects_final_action": payload.get("affects_final_action", False),
        "usable_weeks": payload.get("usable_weeks", 0),
        "candidates": payload.get("candidates", []),
    }


def load_risk_engine_v2_replay_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "risk_engine_v2_replay.json"
    if not path.exists():
        return {"status": "not_available", "reason": "risk_engine_v2 replay has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"risk_engine_v2 replay could not be loaded: {exc}"}
    summary = payload.get("summary") or {}
    outcome_summary = summary.get("outcome_summary") or {}
    decision = payload.get("decision") or {}
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "affects_final_action": payload.get("affects_final_action", False),
        "total_cases": summary.get("total_cases", 0),
        "strict_available_cases": summary.get("strict_available_cases", 0),
        "domain_stage_counts": summary.get("domain_stage_counts", {}),
        "confirmed_stage_counts": summary.get("confirmed_stage_counts", {}),
        "legacy_domain_stage_divergence_count": summary.get("legacy_domain_stage_divergence_count", 0),
        "oil_status_counts": summary.get("oil_status_counts", {}),
        "oil_reference_only_count": summary.get("oil_reference_only_count", 0),
        "outcome_status": outcome_summary.get("status"),
        "outcome_usable_cases": outcome_summary.get("usable_cases", 0),
        "promotion_allowed": decision.get("promotion_allowed", False),
        "decision_reason": decision.get("reason", "-"),
    }


def load_risk_engine_v2_reconstructed_replay_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "risk_engine_v2_reconstructed_replay.json"
    if not path.exists():
        return {"status": "not_available", "reason": "risk_engine_v2 reconstructed replay has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"risk_engine_v2 reconstructed replay could not be loaded: {exc}"}
    summary = payload.get("summary") or {}
    outcome_summary = summary.get("outcome_summary") or {}
    decision = payload.get("decision") or {}
    reconstruction = payload.get("reconstruction") or {}
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "affects_final_action": payload.get("affects_final_action", False),
        "total_cases": summary.get("total_cases", 0),
        "strict_available_cases": summary.get("strict_available_cases", 0),
        "confirmed_stage_counts": summary.get("confirmed_stage_counts", {}),
        "legacy_domain_stage_divergence_count": summary.get("legacy_domain_stage_divergence_count", 0),
        "oil_status_counts": summary.get("oil_status_counts", {}),
        "outcome_status": outcome_summary.get("status"),
        "outcome_usable_cases": outcome_summary.get("usable_cases", 0),
        "outcome_case_status_counts": outcome_summary.get("case_status_counts", {}),
        "outcome_buckets": outcome_summary.get("buckets", {}),
        "promotion_allowed": decision.get("promotion_allowed", False),
        "decision_reason": decision.get("reason", "-"),
        "reconstruction": reconstruction,
    }


def load_risk_engine_v2_holdout_validation_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    path = Path(reports_dir) / "risk_engine_v2_holdout_validation.json"
    if not path.exists():
        return {"status": "not_available", "reason": "risk_engine_v2 holdout validation has not been generated"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"risk_engine_v2 holdout validation could not be loaded: {exc}"}
    decision = payload.get("decision") or {}
    holdout = payload.get("holdout") or {}
    gate = payload.get("promotion_gate") or {}
    return {
        "status": payload.get("status"),
        "policy_status": payload.get("policy_status"),
        "affects_final_action": payload.get("affects_final_action", False),
        "validation_level": payload.get("validation_level"),
        "strict_primary_available": payload.get("strict_primary_available", False),
        "holdout_status": holdout.get("status"),
        "split_status": holdout.get("split_status"),
        "evidence_status": holdout.get("evidence_status"),
        "performance_status": holdout.get("performance_status"),
        "holdout_episode_count": holdout.get("episode_count", 0),
        "holdout_case_count": holdout.get("case_count", 0),
        "holdout_reason": holdout.get("reason", "-"),
        "holdout_performance": holdout.get("performance", {}),
        "cadence_status": payload.get("cadence_status"),
        "split_policy": payload.get("split_policy", {}),
        "split_boundaries": payload.get("split_boundaries", {}),
        "splits": payload.get("splits", {}),
        "promotion_allowed": decision.get("promotion_allowed", False),
        "decision_reason": decision.get("reason", "-"),
        "promotion_gate_status": gate.get("status", "-"),
        "promotion_gate_blockers": gate.get("blockers", []),
    }


def load_risk_engine_v2_episode_chronicle_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    reports_path = Path(reports_dir)
    path = reports_path / "risk_engine_v2_episode_chronicle.json"
    if not path.exists():
        return {"status": "not_available", "reason": "市場警戒年代記はまだ生成されていません"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "reason": f"市場警戒年代記を読み込めません: {exc}"}
    if not isinstance(payload, dict):
        return {"status": "invalid", "reason": "市場警戒年代記のルートがJSONオブジェクトではありません"}
    decision = payload.get("decision")
    contract = payload.get("contract")
    page_filename = payload.get("page_filename")
    violations: list[str] = []
    if payload.get("schema_version") != "risk_engine_v2.episode_chronicle.v1":
        violations.append("schema_version")
    if payload.get("implementation_version") != "risk_engine_v2.episode_chronicle.implementation.v3":
        violations.append("implementation_version")
    if payload.get("status") != "ready":
        violations.append("status")
    if payload.get("freshness_status") != "current":
        violations.append("freshness_status")
    if payload.get("policy_status") != "diagnostic_only_not_promoted":
        violations.append("policy_status")
    if payload.get("affects_final_action") is not False:
        violations.append("affects_final_action")
    if payload.get("promotion_allowed") is not False:
        violations.append("promotion_allowed")
    if not isinstance(decision, dict) or decision.get("promotion_allowed") is not False:
        violations.append("decision.promotion_allowed")
    if not isinstance(contract, dict) or contract.get("status") != "pass":
        violations.append("contract.status")
    if not isinstance(page_filename, str) or not page_filename or Path(page_filename).name != page_filename:
        violations.append("page_filename")
    elif not (reports_path / page_filename).exists():
        violations.append("page_file")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        violations.append("summary")
        summary = {}
    if violations:
        return {
            "status": "invalid",
            "reason": "市場警戒年代記の安全契約を確認できません: " + ", ".join(violations),
        }
    return {
        "status": "ready",
        "freshness_status": payload.get("freshness_status"),
        "generated_at": payload.get("generated_at"),
        "generation_id": payload.get("generation_id"),
        "episode_count": summary.get("episode_count", 0),
        "mature_count": summary.get("mature_count", 0),
        "pending_count": summary.get("pending_count", 0),
        "latest_event_id": summary.get("latest_event_id"),
        "latest_event_title": summary.get("latest_event_title"),
        "latest_event_date": summary.get("latest_event_date"),
        "page_filename": page_filename,
        "policy_status": payload.get("policy_status"),
        "affects_final_action": False,
        "promotion_allowed": False,
    }


def load_threshold_replay_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    summary_path = Path(reports_dir) / "threshold_historical_replay_diff.json"
    if not summary_path.exists():
        return {}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    summary = payload.get("summary") or {}
    metrics = summary.get("metrics") or {}
    return {
        "active": {
            "action_counts": summary.get("active_action_counts") or {},
            "metrics": metrics.get("active") or {},
        },
        "proposed": {
            "action_counts": summary.get("proposed_action_counts") or {},
            "metrics": metrics.get("proposed") or {},
            "risk_stage_changed_count": summary.get("risk_stage_changed_count", 0),
            "cases_where_proposed_prevented_bad_buy_window": summary.get("cases_where_proposed_prevented_bad_buy_window", 0),
            "cases_where_proposed_missed_good_buy_window": summary.get("cases_where_proposed_missed_good_buy_window", 0),
            "cases_where_proposed_increased_wait": summary.get("cases_where_proposed_increased_wait", 0),
        },
    }


def load_candidate_v2_summary(reports_dir: str | Path | None) -> dict[str, Any]:
    if not reports_dir:
        return {}
    summary_path = Path(reports_dir) / "threshold_candidate_comparison.json"
    if not summary_path.exists():
        return {}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    candidates = payload.get("candidates") or []
    preferred_labels = {"candidate_v2_combined", "ignore_fallback_extreme", "multi_confirm_extreme"}
    selected = None
    for candidate in candidates:
        if candidate.get("label") in preferred_labels:
            selected = candidate
            if candidate.get("label") == "candidate_v2_combined":
                break
    if not isinstance(selected, dict):
        return {}
    return {
        "action_counts": selected.get("action_counts") or {},
        "metrics": selected.get("metrics") or {},
        "risk_stage_changed_count": selected.get("risk_stage_changed_count_vs_active", 0),
        "cases_where_proposed_prevented_bad_buy_window": selected.get("prevented_bad_buy_window_count_vs_active", 0),
        "cases_where_proposed_missed_good_buy_window": selected.get("missed_good_buy_window_count_vs_active", 0),
        "cases_where_proposed_increased_wait": selected.get("increased_wait_count_vs_active", 0),
    }


def _active_threshold_certainty_summary(
    action_validation: dict[str, Any],
    threshold_replay_summary: dict[str, Any],
) -> dict[str, Any]:
    if threshold_replay_summary.get("active"):
        return threshold_replay_summary["active"]
    return {
        "action_counts": action_validation.get("action_summary") or {},
        "metrics": action_validation.get("action_summary") or {},
    }


def _filter_live_monitor_rows(rows: list[dict[str, Any]], availability_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    live_statuses = {"ok", "proxy_fallback"}
    filtered: list[dict[str, Any]] = []
    for row in rows:
        entry = availability_map.get(row.get("ticker"))
        if entry is None or entry.get("status") in live_statuses:
            filtered.append(row)
    return filtered


def _guarded_regime(regime: dict[str, Any], reliability: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(regime)
    guarded["regime_label"] = "data_unavailable"
    guarded["regime_score"] = None
    guarded["credit_regime_flag"] = "neutral"
    guarded["inflation_regime_flag"] = "neutral"
    guarded["guard_reason"] = reliability["reason"]
    return guarded


def _guarded_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(cycle)
    guarded["phase_label"] = "insufficient_data"
    guarded["phase_angle_deg"] = None
    return guarded


def _guarded_score(score: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(score)
    guarded["raw_total_score"] = score.get("total_score")
    guarded["total_score"] = None
    return guarded


def _guarded_risk_lines(reliability: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage_key": "data_unavailable",
        "stage_label": "判定保留",
        "summary": reliability["reason"],
        "reasons": [reliability["reason"]],
        "composite_risk_score": None,
        "warning_count": 0,
        "danger_count": 0,
        "extreme_count": 0,
        "danger_lines": [],
        "extreme_lines": [],
        "penalty_hint": 0.0,
        "indicators": [],
        "coverage_ratio": 0.0,
        "missing_indicators": [],
    }


def _guarded_spot_signal(reliability: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": "wait",
        "legacy_action": "wait",
        "score": None,
        "adjusted_score": None,
        "legacy_adjusted_score": None,
        "regime_penalty": None,
        "risk_off_relief_applied": False,
        "credit_stress_score": None,
        "credit_summary": "重要系列の live 取得不足により、信用判定は保留しています。",
        "second_leg_risk": "high",
        "recovery_evidence": {
            "score": None,
            "grade": "guarded",
            "summary": "重要系列の live 取得不足により、上昇再開の証拠判定は保留しています。",
        },
        "blocker_assessment": {
            "level": "block",
            "flags": ["data_unavailable"],
            "primary_reasons": ["data_unavailable"],
            "summary": reliability["reason"],
        },
        "action_decision": {
            "market_raw_action": "wait",
            "risk_adjusted_action": "wait",
            "original_action": "wait",
            "final_action": "wait",
            "raw_action": "wait",
            "action": "wait",
            "original_confidence": 0.0,
            "final_confidence": 0.0,
            "raw_confidence": 0.0,
            "confidence": 0.0,
            "cap_level": reliability.get("max_action", "wait"),
            "confidence_cap": 0.0,
            "policy_triggered": True,
            "reliability_cap_applied": True,
            "policy_reasons": reliability.get("blocking_reasons", []) + reliability.get("degrade_reasons", []),
            "cap_reason": reliability.get("blocking_reasons", []) + reliability.get("degrade_reasons", []),
            "max_action": reliability.get("max_action", "wait"),
            "critical_failures": reliability.get("critical_failures", []),
            "live_ratio": reliability.get("live_ratio", 0.0),
            "sample_fallback_count": reliability.get("sample_fallback_count", 0),
            "proxy_fallback_count": reliability.get("proxy_fallback_count", 0),
            "unavailable_count": reliability.get("unavailable_count", 0),
            "mode": "guarded_data_unavailable",
            "reason_path": ["guarded", "block"],
        },
        "action_layers": {
            "market_raw_action": "wait",
            "risk_adjusted_action": "wait",
            "final_action": "wait",
            "layer_reasons": {
                "market_raw_action": ["data_unavailable"],
                "risk_adjusted_action": ["data_unavailable"],
                "final_action": reliability.get("blocking_reasons", []) + reliability.get("degrade_reasons", []),
            },
        },
        "data_guard_applied": True,
        "rationale": [
            "重要系列の live 取得が不足したため、通常の投資判断ロジックは保留しました。",
            reliability["reason"],
            "sample 代替データを使った強気・弱気の判定は行っていません。",
        ],
    }


def _data_quality_alert(reliability: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "data_quality_hold",
        "category": "market",
        "severity": "high",
        "title": "データ不足のため判定保留",
        "message": reliability["reason"],
        "evidence": reliability.get("critical_failures", []),
        "source_flags": [reliability.get("level", "low")],
    }
