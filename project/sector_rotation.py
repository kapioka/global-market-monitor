from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from project.sector_labeling import classify_sector_candidate
from project.sector_structure_summary import summarize_sector_structure
from project.sector_vector_analysis import calculate_sector_vectors


SECTOR_LABELS = {
    "XLK": "情報技術",
    "XLF": "金融",
    "XLE": "エネルギー",
    "XLV": "ヘルスケア",
    "XLY": "一般消費財",
    "XLP": "生活必需品",
    "XLI": "資本財",
    "XLB": "素材",
    "XLU": "公益事業",
    "XLRE": "不動産",
}

INTERNAL_STRUCTURE_SIGNAL_MAP = {
    "Defensive Rotation": "defensive_leadership",
    "Cyclical Recovery": "cyclical_improving",
    "Narrow Leadership": "narrow_leadership",
    "Broad Improvement": "broad_improvement",
    "Peakout Risk": "peakout_warning",
}


def analyze_sector_rotation(
    prices: pd.DataFrame,
    sector_map: dict[str, str],
    vector_config: Mapping[str, float] | None = None,
) -> dict[str, object]:
    sectors = [ticker for ticker in sector_map.values() if ticker in prices.columns]
    if not sectors:
        return {
            "leaders": [],
            "laggards": [],
            "table": [],
            "history": [],
            "vector_analysis": {},
            "candidate_map": {},
            "internal_structure": {"structure_label": "Noisy / Unclear", "reason": "有効なセクターデータがありません。", "dispersion_score": 0.0, "counts": {}},
            "integration_signals": _default_integration_signals(),
            "next_candidates": [],
            "peakout_sectors": [],
            "market_structure_comment": "有効なセクターデータがないため、内部構造コメントは保留です。",
        }

    rel_history = prices[sectors].pct_change(12).dropna(how="all")
    rel = rel_history.iloc[-1].dropna().sort_values(ascending=False)
    leaders = rel.head(3)
    laggards = rel.tail(3)
    count = len(rel)

    table = []
    for rank, (ticker, value) in enumerate(rel.items(), start=1):
        table.append(
            {
                "ticker": ticker,
                "sector_name_ja": SECTOR_LABELS.get(ticker, ticker),
                "return_12w": round(float(value), 4),
                "rank": rank,
                "rotation_phase": _rotation_phase(rank, count),
                "rotation_phase_ja": _rotation_phase_ja(rank, count),
            }
        )

    history = _build_history_rows(rel_history)
    vector_analysis = calculate_sector_vectors(pd.DataFrame(history), config=vector_config) if history else {}
    candidate_map = _build_candidate_map(table, vector_analysis, vector_config)
    internal_structure = summarize_sector_structure(candidate_map, config=vector_config)
    integration_signals = _integration_signals(internal_structure)
    next_candidates = _candidate_rows(candidate_map, label="有望")
    peakout_sectors = _candidate_rows(candidate_map, label="失速警戒")
    market_structure_comment = str(internal_structure.get("reason", "内部構造コメントはまだ十分ではありません。"))

    return {
        "leaders": leaders.index.tolist(),
        "laggards": laggards.index.tolist(),
        "table": table,
        "history": history,
        "vector_analysis": vector_analysis,
        "candidate_map": candidate_map,
        "internal_structure": internal_structure,
        "integration_signals": integration_signals,
        "next_candidates": next_candidates,
        "peakout_sectors": peakout_sectors,
        "market_structure_comment": market_structure_comment,
    }


def _build_history_rows(rel_history: pd.DataFrame) -> list[dict[str, object]]:
    if rel_history.empty:
        return []
    history_window = rel_history.tail(3)
    if len(history_window) < 3:
        return []

    x_labels = ["x_2w_ago", "x_1w_ago", "x_current"]
    y_labels = ["y_2w_ago", "y_1w_ago", "y_current"]
    ranked_frames = [_rank_frame(history_window.iloc[index].dropna()) for index in range(3)]
    sectors = [ticker for ticker in history_window.columns if history_window[ticker].notna().all()]
    history_rows: list[dict[str, object]] = []
    for ticker in sectors:
        row: dict[str, object] = {"sector": ticker, "ticker": ticker}
        lengths: list[float] = []
        for index, frame in enumerate(ranked_frames):
            metrics = frame.get(ticker)
            if not metrics:
                break
            row[x_labels[index]] = round(float(metrics["x"]), 6)
            row[y_labels[index]] = round(float(metrics["y"]), 6)
            lengths.append(float(metrics["length"]))
        else:
            positives = [value for value in lengths if value > 0]
            row["avg_length_12w"] = round(sum(positives) / len(positives), 6) if positives else 1.0
            history_rows.append(row)
    return history_rows


def _rank_frame(series: pd.Series) -> dict[str, dict[str, float]]:
    sorted_series = series.sort_values(ascending=False)
    count = len(sorted_series)
    min_value = float(sorted_series.min()) if count else 0.0
    max_value = float(sorted_series.max()) if count else 0.0
    span = max(max_value - min_value, 0.0001)
    result: dict[str, dict[str, float]] = {}
    for rank, (ticker, value) in enumerate(sorted_series.items(), start=1):
        rank_ratio = 0.5 if count <= 1 else (count - rank) / (count - 1)
        x = (rank_ratio * 2.0) - 1.0
        y = ((float(value) - min_value) / span) * 2.0 - 1.0
        result[str(ticker)] = {"x": x, "y": y, "length": (x * x + y * y) ** 0.5}
    return result


def _build_candidate_map(
    table: list[dict[str, object]],
    vector_analysis: dict[str, dict[str, Any]],
    vector_config: Mapping[str, float] | None,
) -> dict[str, dict[str, object]]:
    by_ticker = {str(row.get("ticker")): row for row in table}
    candidate_map: dict[str, dict[str, object]] = {}
    for ticker, analysis in vector_analysis.items():
        table_row = by_ticker.get(ticker, {})
        consistency = dict(analysis.get("consistency", {}))
        consistency["acceleration_state"] = str(analysis.get("acceleration", {}).get("state", "stable"))
        candidate_label = classify_sector_candidate(
            current_quadrant=str(analysis.get("current_quadrant", "center")),
            vec1=analysis.get("vectors", {}).get("previous", {}),
            vec2=analysis.get("vectors", {}).get("current", {}),
            normalized_length=float(analysis.get("normalized_length", 0.0) or 0.0),
            consistency=consistency,
            radius=float(analysis.get("radius", 0.0) or 0.0),
            config=vector_config,
        )
        candidate_map[ticker] = {
            "ticker": ticker,
            "sector_name_ja": str(table_row.get("sector_name_ja", SECTOR_LABELS.get(ticker, ticker))),
            "rank": int(table_row.get("rank", 999) or 999),
            "candidate_label": candidate_label,
            "normalized_length": round(float(analysis.get("normalized_length", 0.0) or 0.0), 4),
            "consistency_score": round(float(analysis.get("consistency", {}).get("consistency_score", 0.0) or 0.0), 4),
            "current_quadrant": str(analysis.get("current_quadrant", "center")),
            "current_direction": str(analysis.get("vectors", {}).get("current", {}).get("direction", "flat")),
            "acceleration_state": str(analysis.get("acceleration", {}).get("state", "stable")),
        }
    return candidate_map


def _integration_signals(internal_structure: Mapping[str, Any]) -> dict[str, bool]:
    structure_label = str(internal_structure.get("structure_label", "Noisy / Unclear"))
    signals = _default_integration_signals()
    mapped = INTERNAL_STRUCTURE_SIGNAL_MAP.get(structure_label)
    if mapped:
        signals[mapped] = True
    dominance_strength = str(internal_structure.get("dominance_strength") or "").strip().lower()
    if bool(internal_structure.get("single_sector_dominance", False)) and not signals.get("broad_improvement"):
        signals["single_sector_dominance_warning"] = True
        signals["dominance_strength"] = dominance_strength or "medium"
    if bool(internal_structure.get("energy_dominance", False)) and not signals.get("broad_improvement"):
        signals["energy_dominance_warning"] = True
        signals["dominance_strength"] = dominance_strength or signals.get("dominance_strength") or "medium"
    return signals


def _candidate_rows(candidate_map: Mapping[str, Mapping[str, object]], label: str) -> list[dict[str, object]]:
    rows = [dict(payload) for payload in candidate_map.values() if str(payload.get("candidate_label")) == label]
    return sorted(rows, key=lambda row: float(row.get("normalized_length", 0.0) or 0.0), reverse=True)[:3]


def _default_integration_signals() -> dict[str, Any]:
    return {
        "defensive_leadership": False,
        "cyclical_improving": False,
        "narrow_leadership": False,
        "broad_improvement": False,
        "peakout_warning": False,
        "energy_dominance_warning": False,
        "single_sector_dominance_warning": False,
        "dominance_strength": None,
    }


def _rotation_phase(rank: int, count: int) -> str:
    quarter = max(1, count // 4)
    if rank <= quarter:
        return "leading"
    if rank <= quarter * 2:
        return "improving"
    if rank <= quarter * 3:
        return "weakening"
    return "lagging"


def _rotation_phase_ja(rank: int, count: int) -> str:
    phase = _rotation_phase(rank, count)
    labels = {
        "leading": "先導",
        "improving": "改善",
        "weakening": "鈍化",
        "lagging": "出遅れ",
    }
    return labels[phase]
