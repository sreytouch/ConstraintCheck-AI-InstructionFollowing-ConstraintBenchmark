"""Library coverage, task isolation, and stable identity."""
from copy import deepcopy
import pytest
from src.constraint_checker import CONSTRAINT_TYPES
from src.task_library import DEVELOPMENT_TASKS, HELD_OUT_TASKS, get_task, normalized_request, task_fingerprint, validate_task


def test_library_size_coverage_and_separation():
    assert len(DEVELOPMENT_TASKS) >= 20
    assert len(HELD_OUT_TASKS) >= 10
    tasks = DEVELOPMENT_TASKS + HELD_OUT_TASKS
    assert len({item["id"] for item in tasks}) == len(tasks)
    assert len({normalized_request(item["main_request"]) for item in tasks}) == len(tasks)
    assert {rule["kind"] for task in tasks for rule in task["constraints"]} == set(CONSTRAINT_TYPES)
    for task in tasks: assert validate_task(task) == task
    assert all(3 <= len(task["constraints"]) <= 6 for task in HELD_OUT_TASKS)
    assert "The town tested" in DEVELOPMENT_TASKS[2]["main_request"]


def test_default_retrieval_hides_heldout_and_returns_copy():
    task = get_task(DEVELOPMENT_TASKS[0]["id"])
    task["constraints"][0]["value"] = 999
    assert DEVELOPMENT_TASKS[0]["constraints"][0]["value"] == 3
    with pytest.raises(ValueError): get_task(HELD_OUT_TASKS[0]["id"])
    assert get_task(HELD_OUT_TASKS[0]["id"], held_out=True) == HELD_OUT_TASKS[0]


def test_fingerprint_groups_renamed_and_reordered_duplicates(task):
    original = task_fingerprint(task)
    copy = deepcopy(task)
    copy["id"], copy["name"] = "renamed", "Different label"
    copy["constraints"].reverse()
    copy["main_request"] = "  ASK FOR\nTHE UPDATE. "
    assert task_fingerprint(copy) == original
    copy["constraints"][0]["description"] = "Use an informal tone."
    assert task_fingerprint(copy) != original


@pytest.mark.parametrize("field,value", [("main_request", ""), ("constraints", []), ("split", "test"), ("name", None)])
def test_incomplete_tasks_are_rejected(task, field, value):
    task[field] = value
    with pytest.raises(ValueError): validate_task(task)
