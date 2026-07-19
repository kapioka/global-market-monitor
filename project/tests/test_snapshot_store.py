from __future__ import annotations

import logging

import pandas as pd

from project.data_fetcher import FetchResult
from project.snapshot_store import load_latest_fetch_snapshot, save_fetch_snapshot


def test_load_latest_fetch_snapshot_records_cache_provenance(tmp_path) -> None:
    prices = pd.DataFrame({"SPY": [100.0, 101.0]}, index=pd.to_datetime(["2026-06-19", "2026-06-20"]))
    fetch = FetchResult(
        prices=prices,
        warnings=[],
        source="mixed",
        acquisition_log=[{"requested_ticker": "SPY", "used_ticker": "SPY", "status": "ok"}],
        diagnostics={"summary": {"source": "mixed"}},
    )

    save_fetch_snapshot(fetch, tmp_path, "2026-06-20T21:07:09", logging.getLogger("test"))
    loaded = load_latest_fetch_snapshot(tmp_path)

    assert loaded is not None
    summary = loaded.diagnostics["summary"]
    assert summary["snapshot_observed_at"] == "2026-06-20T21:07:09"
    assert summary["snapshot_metadata_path"].endswith("market_snapshot_2026-06-20_210709.json")
    assert summary["snapshot_prices_path"].endswith("market_snapshot_2026-06-20_210709.csv")
