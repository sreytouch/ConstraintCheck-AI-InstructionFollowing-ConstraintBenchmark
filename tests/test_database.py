"""Durable round trips, immutable held-out judgments, and atomicity."""
from copy import deepcopy
import json
import sqlite3
from uuid import uuid4
import pytest
from src.database import DataIntegrityError, get_comparisons, get_evaluations, init_db, save_comparison, save_evaluation
from src.task_library import HELD_OUT_TASKS


def test_init_and_evaluation_round_trip(tmp_path, evaluation_factory):
    path = tmp_path / "nested" / "test.db"
    init_db(path)
    init_db(path)
    assert get_evaluations(path) == []
    record = evaluation_factory()
    assert save_evaluation(record, path)
    assert not save_evaluation(record, path)
    assert get_evaluations(path) == [record]
    assert get_evaluations(path, "held_out") == []


def test_comparison_saves_three_records_atomically(tmp_path, comparison_factory):
    path = tmp_path / "test.db"
    record = comparison_factory()
    assert save_comparison(record, path)
    assert not save_comparison(record, path)
    assert get_comparisons(path) == [record]
    assert len(get_evaluations(path)) == 2


def test_heldout_first_vote_is_retained_per_protocol(tmp_path, comparison_factory):
    path = tmp_path / "test.db"
    first = comparison_factory(HELD_OUT_TASKS[0])
    assert save_comparison(first, path)
    assert not save_comparison(comparison_factory(HELD_OUT_TASKS[0], "Baseline"), path)
    assert get_comparisons(path, "held_out") == [first]
    assert len(get_evaluations(path, "held_out")) == 2
    assert get_evaluations(path, "development") == []


def test_conflicting_component_rolls_back_the_entire_pair(tmp_path, comparison_factory):
    path = tmp_path / "test.db"
    pair = comparison_factory()
    conflicting = deepcopy(pair["improved"])
    conflicting["rationale"] = "An older saved judgment."
    save_evaluation(conflicting, path)
    with pytest.raises(DataIntegrityError): save_comparison(pair, path)
    assert get_evaluations(path) == [conflicting]
    assert get_comparisons(path) == []


def test_database_error_does_not_leave_half_a_comparison(tmp_path, comparison_factory):
    path = tmp_path / "test.db"
    init_db(path)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER fail_comparison BEFORE INSERT ON comparisons BEGIN SELECT RAISE(ABORT, 'test failure'); END;")
    with pytest.raises(sqlite3.IntegrityError): save_comparison(comparison_factory(), path)
    assert get_evaluations(path) == []
    assert get_comparisons(path) == []


@pytest.mark.parametrize("corrupt", ["not json", "{}"])
def test_malformed_saved_records_have_a_domain_error(tmp_path, evaluation_factory, corrupt):
    path = tmp_path / "test.db"
    save_evaluation(evaluation_factory(), path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE evaluations SET payload=?", (corrupt,))
    with pytest.raises(DataIntegrityError): get_evaluations(path)


def test_indexed_metadata_and_component_tampering_are_detected(tmp_path, comparison_factory):
    path = tmp_path / "test.db"
    pair = comparison_factory()
    save_comparison(pair, path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE evaluations SET task_id='tampered'")
    with pytest.raises(DataIntegrityError): get_evaluations(path)
