from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

HORIZONS = {"4w": 4, "13w": 13, "26w": 26}


def build_fx_soft_cap_historical_replay(features: pd.DataFrame) -> dict[str, Any]:
    clean = features.copy()
    clean.index = pd.to_datetime(clean.index).tz_localize(None)
    clean = clean.sort_index()
    cases: list[dict[str, Any]] = []
    for position, (stamp, row) in enumerate(clean.iterrows()):
        signal = _signal_for_row(row)
        if signal["current_final_action"] != "watch" or signal["fx_soft_cap_action"] != "buy_candidate":
            continue
        metrics = _forward_metrics(clean, position)
        cases.append(_case_row(stamp, row, signal, metrics))

    summary = _summary(cases, len(clean))
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "adoption_decision": _adoption_decision(summary),
        "total_replay_weeks": len(clean),
        "current_final_action_counts": summary["current_final_action_counts"],
        "fx_soft_cap_action_counts": summary["fx_soft_cap_action_counts"],
        "current_watch_to_fx_soft_cap_buy_candidate_count": summary["current_watch_to_fx_soft_cap_buy_candidate_count"],
        "current_watch_to_fx_soft_cap_buy_window_count": 0,
        "fx_soft_cap_buy_candidate_count": summary["fx_soft_cap_buy_candidate_count"],
        "fx_soft_cap_buy_window_count": 0,
        "classification_counts": summary["classification_counts"],
        "return_summary": summary["return_summary"],
        "cases": cases,
    }


def write_fx_soft_cap_historical_replay(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_soft_cap_historical_replay.json"
    markdown_path = reports_path / "fx_soft_cap_historical_replay.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_soft_cap_historical_replay_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_soft_cap_historical_replay_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# fx_soft_cap historical replay",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- adoption_decision: {payload.get('adoption_decision')}",
        f"- total replay weeks: {payload.get('total_replay_weeks', 0)}",
        f"- current watch -> fx_soft_cap buy_candidate: {payload.get('current_watch_to_fx_soft_cap_buy_candidate_count', 0)}",
        f"- fx_soft_cap buy_candidate count: {payload.get('fx_soft_cap_buy_candidate_count', 0)}",
        f"- classification counts: {payload.get('classification_counts', {})}",
        "",
        "## return summary",
    ]
    for horizon, row in (payload.get("return_summary") or {}).items():
        lines.append(
            "- {h}: count={count} / mean={mean} / excess={excess} / worst_dd={dd}".format(
                h=horizon,
                count=row.get("count", 0),
                mean=_fmt(row.get("mean_return")),
                excess=_fmt(row.get("mean_excess_return")),
                dd=_fmt(row.get("worst_max_drawdown")),
            )
        )
    lines.append("")
    lines.append("## cases")
    for case in payload.get("cases", [])[:20]:
        lines.append(
            "- {date}: current={current} / soft={soft} / class={classification} / fx={fx} / 13w={ret} / dd={dd}".format(
                date=case.get("date", "-"),
                current=case.get("current_final_action", "-"),
                soft=case.get("fx_soft_cap_action", "-"),
                classification=case.get("classification", "-"),
                fx=", ".join(case.get("fx_flags", [])) or "-",
                ret=_fmt(case.get("forward_returns", {}).get("13w")),
                dd=_fmt(case.get("max_drawdowns", {}).get("13w")),
            )
        )
    if not payload.get("cases"):
        lines.append("- no historical fx_soft_cap cases")
    return "\n".join(lines) + "\n"


def run_fx_soft_cap_historical_replay(
    features_path: str | Path = "project/cache/historical_features.csv",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    path = Path(features_path)
    if not path.exists():
        return {"status": "missing_features", "features_path": str(path)}
    payload = build_fx_soft_cap_historical_replay(_read_table(path))
    json_path, markdown_path = write_fx_soft_cap_historical_replay(payload, reports_dir)
    return {
        "status": payload["status"],
        "total_replay_weeks": payload["total_replay_weeks"],
        "fx_soft_cap_buy_candidate_count": payload["fx_soft_cap_buy_candidate_count"],
        "adoption_decision": payload["adoption_decision"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _signal_for_row(row: pd.Series) -> dict[str, Any]:
    acwi_13w = _number(row.get("acwi_return_13w"))
    acwi_4w = _number(row.get("acwi_return_4w"))
    drawdown = _number(row.get("acwi_drawdown_13w"))
    usdjpy_4w = _number(row.get("usdjpy_change_4w"))
    usdjpy_13w = _number(row.get("usdjpy_change_13w"))
    vix = _number(row.get("vix_level"))

    market_candidate = (
        acwi_13w is not None
        and acwi_4w is not None
        and drawdown is not None
        and acwi_13w >= 0.03
        and acwi_4w >= -0.02
        and drawdown > -0.10
        and (vix is None or vix < 35)
    )
    fx_flags = _fx_flags(usdjpy_4w, usdjpy_13w)
    if market_candidate and fx_flags:
        return {
            "market_raw_action": "buy_candidate",
            "current_final_action": "watch",
            "fx_soft_cap_action": "buy_candidate",
            "fx_flags": fx_flags,
        }
    if market_candidate:
        return {
            "market_raw_action": "buy_candidate",
            "current_final_action": "buy_candidate",
            "fx_soft_cap_action": "buy_candidate",
            "fx_flags": [],
        }
    return {"market_raw_action": "watch", "current_final_action": "watch", "fx_soft_cap_action": "watch", "fx_flags": fx_flags}


def _fx_flags(usdjpy_4w: float | None, usdjpy_13w: float | None) -> list[str]:
    flags: list[str] = []
    if usdjpy_4w is not None and abs(usdjpy_4w) >= 0.02:
        flags.append("japan_fx_risk_caution")
    if usdjpy_13w is not None and abs(usdjpy_13w) >= 0.04:
        flags.append("japan_fx_risk_moderate")
    if usdjpy_4w is not None and usdjpy_4w <= -0.02:
        flags.append("foreign_asset_fx_headwind")
    return flags


def _forward_metrics(features: pd.DataFrame, position: int) -> dict[str, dict[str, float | None]]:
    forward_returns: dict[str, float | None] = {}
    benchmark_returns: dict[str, float | None] = {}
    excess_returns: dict[str, float | None] = {}
    max_drawdowns: dict[str, float | None] = {}
    for horizon, offset in HORIZONS.items():
        target = position + offset
        if target >= len(features):
            forward_returns[horizon] = None
            benchmark_returns[horizon] = None
            excess_returns[horizon] = None
            max_drawdowns[horizon] = None
            continue
        current = _number(features.iloc[position].get("price_acwi"))
        future = _number(features.iloc[target].get("price_acwi"))
        benchmark_current = _number(features.iloc[position].get("price_spy"))
        benchmark_future = _number(features.iloc[target].get("price_spy"))
        forward = _return(current, future)
        benchmark = _return(benchmark_current, benchmark_future)
        forward_returns[horizon] = forward
        benchmark_returns[horizon] = benchmark
        excess_returns[horizon] = round(forward - benchmark, 6) if forward is not None and benchmark is not None else None
        max_drawdowns[horizon] = _max_drawdown(features["price_acwi"].iloc[position : target + 1])
    return {
        "forward_returns": forward_returns,
        "benchmark_returns": benchmark_returns,
        "excess_returns": excess_returns,
        "max_drawdowns": max_drawdowns,
    }


def _case_row(stamp: pd.Timestamp, row: pd.Series, signal: dict[str, Any], metrics: dict[str, dict[str, float | None]]) -> dict[str, Any]:
    return {
        "date": stamp.date().isoformat(),
        "market_raw_action": signal["market_raw_action"],
        "current_final_action": signal["current_final_action"],
        "fx_soft_cap_action": signal["fx_soft_cap_action"],
        "fx_flags": signal["fx_flags"],
        "risk_stage": "normal",
        "reliability_level": "historical_price_replay",
        "score_band": _score_band(row),
        "feature_snapshot": _feature_snapshot(row),
        "forward_returns": metrics["forward_returns"],
        "benchmark_returns": metrics["benchmark_returns"],
        "excess_returns": metrics["excess_returns"],
        "max_drawdowns": metrics["max_drawdowns"],
        "classification": _classify(metrics),
    }


def _feature_snapshot(row: pd.Series) -> dict[str, float | None]:
    keys = [
        "acwi_return_4w",
        "acwi_return_13w",
        "spy_return_4w",
        "spy_return_13w",
        "acwi_spy_relative_13w",
        "hyg_lqd_ratio_return_4w",
        "usdjpy_change_4w",
        "usdjpy_change_13w",
        "vix_level",
        "vix_change_4w",
        "tnx_change_4w",
        "oil_family_return_4w",
        "gold_return_4w",
        "acwi_drawdown_13w",
    ]
    return {key: _number(row.get(key)) for key in keys}


def _score_band(row: pd.Series) -> str:
    acwi_13w = _number(row.get("acwi_return_13w")) or 0.0
    if acwi_13w >= 0.08:
        return "strong"
    if acwi_13w >= 0.03:
        return "candidate"
    return "watch"


def _classify(metrics: dict[str, dict[str, float | None]]) -> str:
    returns = metrics.get("forward_returns", {})
    excess = metrics.get("excess_returns", {})
    drawdowns = metrics.get("max_drawdowns", {})
    return_4w = returns.get("4w")
    return_13w = returns.get("13w")
    return_26w = returns.get("26w")
    excess_13w = excess.get("13w")
    dd_4w = drawdowns.get("4w")
    dd_13w = drawdowns.get("13w")
    if return_13w is None and return_26w is None:
        if return_4w is not None and return_4w > 0.02 and (dd_4w is None or dd_4w > -0.04):
            return "promising_candidate"
        return "inconclusive"
    if (return_13w is not None and return_13w <= -0.03) or (dd_13w is not None and dd_13w <= -0.08):
        return "correctly_blocked"
    if return_13w is not None and return_13w >= 0.03 and (excess_13w is None or excess_13w >= 0.0) and (dd_13w is None or dd_13w > -0.05):
        return "overblocked_by_current"
    return "promising_candidate"


def _summary(cases: list[dict[str, Any]], total_weeks: int) -> dict[str, Any]:
    classifications = Counter(str(case.get("classification", "inconclusive")) for case in cases)
    return {
        "total_replay_weeks": total_weeks,
        "current_final_action_counts": dict(Counter(str(case.get("current_final_action", "watch")) for case in cases)),
        "fx_soft_cap_action_counts": dict(Counter(str(case.get("fx_soft_cap_action", "watch")) for case in cases)),
        "current_watch_to_fx_soft_cap_buy_candidate_count": sum(
            1 for case in cases if case.get("current_final_action") == "watch" and case.get("fx_soft_cap_action") == "buy_candidate"
        ),
        "fx_soft_cap_buy_candidate_count": sum(1 for case in cases if case.get("fx_soft_cap_action") == "buy_candidate"),
        "classification_counts": dict(classifications),
        "return_summary": _return_summary(cases),
    }


def _return_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for horizon in HORIZONS:
        returns = [float(value) for case in cases if (value := (case.get("forward_returns") or {}).get(horizon)) is not None]
        excess = [float(value) for case in cases if (value := (case.get("excess_returns") or {}).get(horizon)) is not None]
        drawdowns = [float(value) for case in cases if (value := (case.get("max_drawdowns") or {}).get(horizon)) is not None]
        result[horizon] = {
            "count": len(returns),
            "mean_return": round(sum(returns) / len(returns), 6) if returns else None,
            "mean_excess_return": round(sum(excess) / len(excess), 6) if excess else None,
            "worst_max_drawdown": min(drawdowns) if drawdowns else None,
        }
    return result


def _adoption_decision(summary: dict[str, Any]) -> str:
    counts = summary.get("classification_counts", {})
    return_13w = (summary.get("return_summary") or {}).get("13w", {})
    if int(return_13w.get("count") or 0) < 20:
        return "hold"
    correctly_blocked = int(counts.get("correctly_blocked", 0) or 0)
    overblocked = int(counts.get("overblocked_by_current", 0) or 0)
    mean_return = float(return_13w.get("mean_return") or 0.0)
    mean_excess = float(return_13w.get("mean_excess_return") or 0.0)
    worst_drawdown = float(return_13w.get("worst_max_drawdown") or 0.0)
    if correctly_blocked > overblocked * 2 and (mean_return < 0.0 or mean_excess < -0.01):
        return "reject"
    if mean_excess < 0.0 or worst_drawdown <= -0.10:
        return "hold"
    if overblocked <= correctly_blocked:
        return "hold"
    if mean_return < 0.03:
        return "hold"
    if worst_drawdown <= -0.08:
        return "hold"
    if overblocked < correctly_blocked * 2:
        return "hold"
    if mean_excess < 0.0:
        return "reject"
    return "adopt_candidate"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _return(current: float | None, future: float | None) -> float | None:
    if current is None or current == 0.0 or future is None:
        return None
    return round((future / current) - 1.0, 6)


def _max_drawdown(series: pd.Series) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    peak = float(clean.iloc[0])
    max_dd = 0.0
    for value in clean:
        peak = max(peak, float(value))
        if peak:
            max_dd = min(max_dd, (float(value) / peak) - 1.0)
    return round(max_dd, 6)


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
        return frame.set_index("date")
    frame.index = pd.to_datetime(frame.index)
    return frame


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay fx_soft_cap diagnostic policy on historical features.")
    parser.add_argument("--features", default="project/cache/historical_features.csv")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_fx_soft_cap_historical_replay(args.features, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
