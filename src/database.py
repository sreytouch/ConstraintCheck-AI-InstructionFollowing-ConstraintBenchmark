"""SQLite snapshot storage with atomic paired saves and immutable judgments."""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from src.evaluation import validate_comparison, validate_evaluation


class DataIntegrityError(ValueError):
    """A saved record is malformed or conflicts with an existing immutable record."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluations (
 evaluation_id TEXT PRIMARY KEY NOT NULL,
 timestamp TEXT NOT NULL,
 task_id TEXT NOT NULL,
 split TEXT NOT NULL CHECK(split IN ('development','held_out')),
 protocol_id TEXT NOT NULL,
 payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comparisons (
 comparison_id TEXT PRIMARY KEY NOT NULL,
 timestamp TEXT NOT NULL,
 task_id TEXT NOT NULL,
 split TEXT NOT NULL CHECK(split IN ('development','held_out')),
 protocol_id TEXT NOT NULL,
 baseline_id TEXT NOT NULL UNIQUE REFERENCES evaluations(evaluation_id),
 improved_id TEXT NOT NULL UNIQUE REFERENCES evaluations(evaluation_id),
 payload TEXT NOT NULL,
 CHECK(baseline_id != improved_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_held_out_judgment
 ON comparisons(task_id, protocol_id) WHERE split='held_out';
CREATE INDEX IF NOT EXISTS evaluation_split ON evaluations(split);
"""


@contextmanager
def _connect(path=None):
    if path is None:
        from src.config import get_settings
        path = get_settings().db_path
    if str(path) == ":memory:":
        raise ValueError("Use a file database so feedback persists between connections.")
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.executescript(SCHEMA)
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(path=None) -> None:
    with _connect(path):
        return


def _payload(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _insert_evaluation(connection, record: dict) -> None:
    connection.execute("INSERT INTO evaluations VALUES (?, ?, ?, ?, ?, ?)", (
        record["evaluation_id"], record["timestamp"], record["task"]["id"], record["task"]["split"],
        record["generation_metadata"]["protocol_id"], _payload(record)))


def save_evaluation(record: dict, path=None) -> bool:
    record = validate_evaluation(record)
    with _connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM evaluations WHERE evaluation_id=?", (record["evaluation_id"],)).fetchone():
            return False
        _insert_evaluation(connection, record)
    return True


def save_comparison(record: dict, path=None) -> bool:
    """Insert both evaluations and their preference in one transaction, or nothing."""
    record = validate_comparison(record)
    with _connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        duplicate = connection.execute("SELECT 1 FROM comparisons WHERE comparison_id=? OR (split='held_out' AND ?='held_out' AND task_id=? AND protocol_id=?)", (record["comparison_id"], record["split"], record["task_id"], record["protocol_id"])).fetchone()
        if duplicate:
            return False
        for name in ("baseline", "improved"):
            evaluation = record[name]
            existing = connection.execute("SELECT payload FROM evaluations WHERE evaluation_id=?", (evaluation["evaluation_id"],)).fetchone()
            if existing:
                if existing["payload"] != _payload(evaluation):
                    raise DataIntegrityError("An evaluation ID already has a different saved judgment. Generate a new pair.")
            else:
                _insert_evaluation(connection, evaluation)
        connection.execute("INSERT INTO comparisons VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
            record["comparison_id"], record["timestamp"], record["task_id"], record["split"], record["protocol_id"],
            record["baseline"]["evaluation_id"], record["improved"]["evaluation_id"], _payload(record)))
    return True


def _read(table: str, path=None, split=None) -> list[dict]:
    if split not in (None, "development", "held_out"):
        raise ValueError("Choose development, held_out, or no split filter.")
    condition = " WHERE split=?" if split else ""
    with _connect(path) as connection:
        rows = connection.execute(f"SELECT * FROM {table}{condition} ORDER BY timestamp DESC, rowid DESC", (split,) if split else ()).fetchall()
        records = []
        try:
            for row in rows:
                record = json.loads(row["payload"])
                record = validate_evaluation(record) if table == "evaluations" else validate_comparison(record)
                expected = (record["task"]["id"], record["task"]["split"], record["generation_metadata"]["protocol_id"]) if table == "evaluations" else (record["task_id"], record["split"], record["protocol_id"])
                id_field = "evaluation_id" if table == "evaluations" else "comparison_id"
                if (row["task_id"], row["split"], row["protocol_id"]) != expected or row[id_field] != record[id_field] or row["timestamp"] != record["timestamp"]:
                    raise ValueError("Mismatched indexed metadata")
                if table == "comparisons":
                    for arm in ("baseline", "improved"):
                        if row[f"{arm}_id"] != record[arm]["evaluation_id"]:
                            raise ValueError("Mismatched evaluation reference")
                        component = connection.execute("SELECT payload FROM evaluations WHERE evaluation_id=?", (row[f"{arm}_id"],)).fetchone()
                        if component is None or json.loads(component["payload"]) != record[arm]:
                            raise ValueError("Mismatched evaluation snapshot")
                records.append(record)
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            raise DataIntegrityError("A saved record is malformed or inconsistent. Restore a valid database backup.") from error
        return records


def get_evaluations(path=None, split=None) -> list[dict]:
    return _read("evaluations", path, split)


def get_comparisons(path=None, split=None) -> list[dict]:
    return _read("comparisons", path, split)
