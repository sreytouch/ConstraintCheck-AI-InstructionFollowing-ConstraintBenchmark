"""Offline fixtures with isolated databases and explicit synthetic judgments."""
from copy import deepcopy
from unittest.mock import Mock
import pytest
from src.config import Settings
from src.evaluation import QUALITY_CRITERIA, make_comparison, make_evaluation
from src.generation import generation_metadata


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("CONSTRAINTCHECK_DB_PATH", str(tmp_path / "feedback.db"))
    monkeypatch.setattr("src.openai_client.OpenAI", Mock(side_effect=AssertionError("Live API calls are forbidden in tests")))


@pytest.fixture
def task():
    return {"id": "test-task", "name": "Reminder", "category": "Workplace", "main_request": "Ask for the update.", "split": "development", "constraints": [
        {"id": "c1", "kind": "maximum_words", "description": "Use at most 8 words.", "value": 8},
        {"id": "c2", "kind": "required_phrase", "description": "Include Friday.", "value": "Friday"},
        {"id": "c3", "kind": "tone", "description": "Use a polite tone.", "value": None},
    ]}


@pytest.fixture
def evaluation_factory(task):
    def create(strategy="Baseline", statuses=("Pass", "Pass", "Pass"), score=4, supplied_task=None, **kwargs):
        snapshot = deepcopy(supplied_task or task)
        human = [{"constraint_id": item["id"], "status": statuses[index] if index < len(statuses) else "Pass", "notes": "Reviewed deliberately; override if needed."} for index, item in enumerate(snapshot["constraints"])]
        arguments = dict(task=snapshot, response="Please send the Friday update.", generation_strategy=strategy, human_results=human,
                         quality_scores=dict.fromkeys(QUALITY_CRITERIA, score), accepted=True, rationale="Clear and respectful.", generation_metadata=generation_metadata(Settings()))
        arguments.update(kwargs)
        return make_evaluation(**arguments)
    return create


@pytest.fixture
def comparison_factory(evaluation_factory):
    def create(supplied_task=None, preference="Constraint-aware"):
        baseline = evaluation_factory(statuses=("Pass", "Fail", "Pass"), score=3, supplied_task=supplied_task)
        improved = evaluation_factory("Constraint-aware", score=5, supplied_task=supplied_task)
        return make_comparison(baseline, improved, preference, "It follows more requirements.")
    return create
