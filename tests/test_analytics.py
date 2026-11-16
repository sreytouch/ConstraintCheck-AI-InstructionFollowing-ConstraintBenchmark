"""Metrics use human judgments and transparent N/A denominators."""
import math
import pytest
from src.analytics import constraint_difficulty, constraint_frame, evaluation_frame, failure_examples, summary_metrics


def test_empty_analytics():
    assert summary_metrics([])["total"] == 0
    assert summary_metrics([])["average_compliance"] is None
    assert evaluation_frame([]).empty
    assert constraint_difficulty([]).empty
    assert failure_examples([]).empty


def test_summary_difficulty_and_failure_examples(evaluation_factory):
    records = [evaluation_factory(statuses=("Pass", "Fail", "Not Applicable"), accepted=False), evaluation_factory("Constraint-aware")]
    summary = summary_metrics(records)
    assert summary["average_compliance"] == 75
    assert summary["acceptance_rate"] == .5
    assert summary["average_failed"] == .5
    assert summary["baseline_compliance"] == 50
    assert summary["improved_compliance"] == 100
    assert summary["most_violated_type"] == "Required phrase"
    difficulty = constraint_difficulty(records).set_index("kind")
    assert difficulty.loc["required_phrase", "pass_rate"] == .5
    assert difficulty.loc["tone", "evaluated"] == 1
    assert difficulty.loc["tone", "not_applicable"] == 1
    assert set(failure_examples(records)["failure_mode"]) == {"Required-content omission", "Partial instruction following"}
    assert len(constraint_frame(records)) == 6


def test_all_na_has_no_compliance_or_pass_rate(evaluation_factory):
    record = evaluation_factory(statuses=("Not Applicable",)*3)
    assert summary_metrics([record])["average_compliance"] is None
    assert summary_metrics([record])["full_pass_count"] == 0
    assert constraint_difficulty([record])["pass_rate"].isna().all()
