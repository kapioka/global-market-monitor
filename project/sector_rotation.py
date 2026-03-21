from __future__ import annotations

import pandas as pd


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


def analyze_sector_rotation(prices: pd.DataFrame, sector_map: dict[str, str]) -> dict[str, object]:
    sectors = [ticker for ticker in sector_map.values() if ticker in prices.columns]
    if not sectors:
        return {"leaders": [], "laggards": [], "table": []}

    rel = prices[sectors].pct_change(12).iloc[-1].sort_values(ascending=False)
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
    return {
        "leaders": leaders.index.tolist(),
        "laggards": laggards.index.tolist(),
        "table": table,
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
