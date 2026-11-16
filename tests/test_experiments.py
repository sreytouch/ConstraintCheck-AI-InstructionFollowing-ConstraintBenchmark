"""Only matched, eligible results from a single protocol enter test summaries."""
from copy import deepcopy
from src.experiments import development_requests, eligible_held_out, experiment_summary
from src.task_library import HELD_OUT_TASKS


def test_contamination_wrong_protocol_and_old_task_snapshots_excluded(comparison_factory, evaluation_factory):
    pair = comparison_factory(HELD_OUT_TASKS[0])
    protocol = pair["protocol_id"]
    assert eligible_held_out([pair], [], protocol) == [pair]
    assert eligible_held_out([pair], [], "different") == []
    development_task = deepcopy(HELD_OUT_TASKS[0])
    development_task["split"] = "development"
    development_task["main_request"] = development_task["main_request"].upper()
    used = evaluation_factory(supplied_task=development_task)
    assert eligible_held_out([pair], [used], protocol) == []
    old = deepcopy(pair)
    old["baseline"]["task"]["constraints"][0]["value"] = 99
    assert eligible_held_out([old], [], protocol) == []


def test_matched_metrics_report_coverage_acceptance_and_fullpass(comparison_factory):
    pair = comparison_factory(HELD_OUT_TASKS[0])
    frame = experiment_summary([pair]).set_index("Strategy")
    assert frame.loc["Baseline", "Responses"] == frame.loc["Constraint-aware", "Responses"] == 1
    assert frame.loc["Baseline", "Full-compliance rate"] == 0
    assert frame.loc["Constraint-aware", "Full-compliance rate"] == 1
    assert frame.loc["Constraint-aware", "Average quality"] == 5
    assert experiment_summary([])["Responses"].sum() == 0
