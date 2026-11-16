"""Compliance and preference records require complete, coherent judgments."""
from copy import deepcopy
import csv
import io
import json
import pytest
from src.evaluation import calculate_compliance, export_csv, make_comparison, validate_evaluation


@pytest.mark.parametrize("statuses,score,full", [(["Pass"]*4+["Fail"], 80, False), (["Pass", "Not Applicable"], 100, False), (["Not Applicable"], None, False), (["Pass", "Pass"], 100, True), (["Fail"], 0, False), ([], None, False)])
def test_compliance_denominator(statuses, score, full):
    results = [{"constraint_id": f"c{i}", "status": status, "notes": ""} for i, status in enumerate(statuses)]
    actual = calculate_compliance(results)
    assert actual["compliance_score"] == score
    assert actual["full_pass"] is full
    assert actual["total"] == len(statuses)


def test_record_retains_automatic_human_disagreement(evaluation_factory):
    record = evaluation_factory(statuses=("Pass", "Fail", "Pass"))
    assert record["automatic_results"][1]["status"] == "Pass"
    assert record["human_results"][1]["status"] == "Fail"
    assert record["compliance_score"] == pytest.approx(200/3)
    assert validate_evaluation(record) == record


@pytest.mark.parametrize("kwargs", [
    {"accepted": None}, {"rationale": ""}, {"score": True}, {"score": 6},
    {"statuses": (None, "Pass", "Pass")}, {"statuses": ("Unknown", "Pass", "Pass")},
    {"quality_scores": {"clarity": 3}}, {"generation_strategy": "Other"},
])
def test_incomplete_or_invalid_ratings_rejected(evaluation_factory, kwargs):
    with pytest.raises(ValueError): evaluation_factory(**kwargs)


def test_override_needs_note_and_each_constraint_once(evaluation_factory):
    record = evaluation_factory(statuses=("Pass", "Fail", "Pass"))
    human = deepcopy(record["human_results"])
    human[1]["notes"] = ""
    with pytest.raises(ValueError, match="note"): evaluation_factory(human_results=human)
    with pytest.raises(ValueError): evaluation_factory(human_results=human[:1])
    with pytest.raises(ValueError): evaluation_factory(human_results=[human[0]]*3)


@pytest.mark.parametrize("field,value", [("compliance_score", 0), ("full_pass", False), ("failed", 3), ("automatic_results", []), ("timestamp", "not-a-date")])
def test_saved_derived_values_are_verified(evaluation_factory, field, value):
    record = evaluation_factory()
    record[field] = value
    with pytest.raises(ValueError): validate_evaluation(record)


def test_comparisons_require_identical_task_and_settings(evaluation_factory):
    a, b = evaluation_factory(), evaluation_factory("Constraint-aware")
    b["generation_metadata"]["model"] = "different-model"
    with pytest.raises(ValueError): make_comparison(a, b, "Baseline", "Reason")
    b = evaluation_factory("Constraint-aware")
    b["task"]["main_request"] += " Also ask why."
    with pytest.raises(ValueError): make_comparison(a, b, "Baseline", "Reason")
    with pytest.raises(ValueError): make_comparison(a, evaluation_factory("Constraint-aware"), None, "Reason")


def test_csv_round_trips_snapshots_and_neutralizes_formulas(evaluation_factory):
    record = evaluation_factory(rationale="=HYPERLINK(unsafe)")
    rows = list(csv.DictReader(io.StringIO(export_csv([record]).decode())))
    assert rows[0]["rationale"].startswith("'=")
    assert json.loads(rows[0]["task"]) == record["task"]
    assert record["rationale"].startswith("=")
    assert "evaluation_id" in export_csv([]).decode()
