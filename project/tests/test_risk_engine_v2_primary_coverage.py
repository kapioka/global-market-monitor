from __future__ import annotations

import pandas as pd

from project.risk_engine_v2_evidence_policy import build_evidence_policy
from project.risk_engine_v2_primary_coverage import evaluate_case_primary_coverage, summarize_primary_coverage


def _prices() -> pd.DataFrame:
    index = pd.date_range("2022-01-07", periods=140, freq="W-FRI")
    frame = pd.DataFrame(index=index)
    for ticker in ["FRED:DFII10", "FRED:T10YIE", "FRED:T10Y2Y", "FRED:T10Y3M", "FRED:NFCI"]:
        frame[ticker] = [1.0 + row * 0.01 for row in range(len(index))]
    credit_index = index[index >= pd.Timestamp("2023-06-23")]
    frame.loc[credit_index, "FRED:BAMLH0A0HYM2"] = [4.0 + row * 0.01 for row in range(len(credit_index))]
    frame.loc[credit_index, "FRED:BAMLC0A0CM"] = [1.5 + row * 0.01 for row in range(len(credit_index))]
    return frame


def test_future_official_rows_do_not_make_early_case_primary_strict() -> None:
    coverage = evaluate_case_primary_coverage(_prices(), pd.Timestamp("2023-04-07"), policy=build_evidence_policy())

    assert coverage["primary_strict_available"] is False
    assert coverage["coverage_status"] == "primary_partial"
    assert "credit" in coverage["missing_primary_groups"]
    assert "FRED:BAMLH0A0HYM2" in coverage["primary_missing_series"]
    assert "FRED:BAMLC0A0CM" in coverage["primary_missing_series"]


def test_later_case_with_all_required_history_becomes_primary_strict() -> None:
    coverage = evaluate_case_primary_coverage(_prices(), pd.Timestamp("2024-08-02"), policy=build_evidence_policy())

    assert coverage["primary_strict_available"] is True
    assert coverage["primary_domain_coverage"] == 1.0
    assert coverage["satisfied_primary_groups"] == ["credit", "rates", "usd_funding"]


def test_any_of_curve_group_passes_with_one_approved_curve_series() -> None:
    prices = _prices().drop(columns=["FRED:T10Y3M"])

    coverage = evaluate_case_primary_coverage(prices, pd.Timestamp("2024-08-02"), policy=build_evidence_policy())

    assert coverage["primary_strict_available"] is True
    assert "rates" in coverage["satisfied_primary_groups"]


def test_missing_all_of_series_fails_domain_group() -> None:
    prices = _prices().drop(columns=["FRED:BAMLC0A0CM"])

    coverage = evaluate_case_primary_coverage(prices, pd.Timestamp("2024-08-02"), policy=build_evidence_policy())

    assert coverage["primary_strict_available"] is False
    assert "credit" in coverage["missing_primary_groups"]


def test_stale_and_insufficient_history_fail_strict_coverage() -> None:
    prices = _prices().iloc[:20]

    coverage = evaluate_case_primary_coverage(prices, pd.Timestamp("2025-01-03"), policy=build_evidence_policy())

    assert coverage["primary_strict_available"] is False
    assert coverage["primary_stale_series"]
    assert coverage["primary_history_insufficient_series"]


def test_summary_counts_reconcile_with_case_flags() -> None:
    early = {"primary_coverage": evaluate_case_primary_coverage(_prices(), pd.Timestamp("2023-04-07"), policy=build_evidence_policy())}
    late = {"primary_coverage": evaluate_case_primary_coverage(_prices(), pd.Timestamp("2024-08-02"), policy=build_evidence_policy())}

    summary = summarize_primary_coverage([early, late])

    assert summary["primary_strict_available_cases"] == 1
    assert summary["primary_partial_cases"] == 1
    assert summary["first_primary_strict_date"] == "2024-08-02"
    assert summary["minimum_primary_domain_coverage"] < 1.0
