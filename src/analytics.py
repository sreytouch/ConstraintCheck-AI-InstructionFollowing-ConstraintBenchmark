"""Human-judgment summaries with explicit treatment of Not Applicable ratings."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.constraint_checker import CONSTRAINT_TYPES

FRAME_COLUMNS = [
    "evaluation_id", "timestamp", "task_id", "task_name", "category", "split", "model",
    "protocol_id", "generation_strategy", "compliance_score", "passed", "failed",
    "not_applicable", "applicable", "total", "full_pass", "correctness", "relevance",
    "clarity", "overall_quality", "accepted", "response", "rationale",
]
CONSTRAINT_COLUMNS = ["evaluation_id", "task_name", "kind", "description", "status", "notes", "response"]
FAILURE_COLUMNS = ["evaluation_id", "task_name", "failure_mode", "description", "response", "notes"]
FAILURE_MODES = {
    "maximum_words": "Word-count violation", "minimum_words": "Word-count violation",
    "exact_words": "Word-count violation", "maximum_sentences": "Formatting violation",
    "exact_sentences": "Formatting violation", "exact_bullets": "Formatting violation",
    "format": "Formatting violation", "output_ordering": "Formatting violation",
    "required_phrase": "Required-content omission", "required_concept": "Required-content omission",
    "prohibited_phrase": "Prohibited-content inclusion", "prohibited_concept": "Prohibited-content inclusion",
    "tone": "Tone failure", "audience": "Audience mismatch",
    "information_preservation": "Meaning changed", "no_unsupported_information": "Unsupported information",
}


def evaluation_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten metadata and aggregate scores, retaining undefined compliance."""
    rows = []
    for record in records:
        row = {key: record.get(key) for key in FRAME_COLUMNS}
        row.update({"task_id": record["task"]["id"], "task_name": record["task"]["name"],
                    "category": record["task"]["category"], "split": record["task"]["split"],
                    "model": record["generation_metadata"]["model"],
                    "protocol_id": record["generation_metadata"]["protocol_id"]})
        rows.append(row)
    return pd.DataFrame(rows, columns=FRAME_COLUMNS)


def constraint_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Create one row for each final human judgment, independently of automation."""
    rows = []
    for record in records:
        constraints = {item["id"]: item for item in record["task"]["constraints"]}
        for judgment in record["human_results"]:
            constraint = constraints[judgment["constraint_id"]]
            rows.append({"evaluation_id": record["evaluation_id"], "task_name": record["task"]["name"],
                         "kind": constraint["kind"], "description": constraint["description"],
                         "status": judgment["status"], "notes": judgment["notes"], "response": record["response"]})
    return pd.DataFrame(rows, columns=CONSTRAINT_COLUMNS)


def _mean_or_none(values: pd.Series) -> float | None:
    """No applicable ratings means undefined, rather than perfect compliance."""
    valid = pd.to_numeric(values, errors="coerce").dropna()
    return float(valid.mean()) if not valid.empty else None


def summary_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Macro-average defined per-response compliance and show its coverage."""
    frame = evaluation_frame(records)
    checks = constraint_frame(records)
    failures = checks.loc[checks["status"].eq("Fail"), "kind"].value_counts()
    most_violated = [] if failures.empty else list(failures.loc[failures.eq(failures.max())].index)
    return {
        "total": len(frame),
        "average_compliance": _mean_or_none(frame["compliance_score"]),
        "defined_compliance_count": int(frame["compliance_score"].notna().sum()),
        "acceptance_rate": float(frame["accepted"].mean()) if not frame.empty else 0.0,
        "baseline_compliance": _mean_or_none(frame.loc[frame["generation_strategy"].eq("Baseline"), "compliance_score"]),
        "improved_compliance": _mean_or_none(frame.loc[frame["generation_strategy"].eq("Constraint-aware"), "compliance_score"]),
        "average_failed": float(frame["failed"].mean()) if not frame.empty else 0.0,
        "most_violated_type": ", ".join(CONSTRAINT_TYPES.get(kind, kind) for kind in most_violated) or "No recorded failures",
        "not_applicable_count": int(checks["status"].eq("Not Applicable").sum()),
        "full_pass_count": int(frame["full_pass"].sum()) if not frame.empty else 0,
    }


def constraint_difficulty(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Exclude N/A ratings from the pass-rate denominator, but show their count."""
    checks = constraint_frame(records)
    rows = []
    for kind, group in checks.groupby("kind", sort=True):
        passed = int(group["status"].eq("Pass").sum())
        failed = int(group["status"].eq("Fail").sum())
        applicable = passed + failed
        rows.append({"kind": kind, "evaluated": applicable, "passed": passed, "failed": failed,
                     "not_applicable": int(group["status"].eq("Not Applicable").sum()),
                     "pass_rate": passed / applicable if applicable else float("nan")})
    return pd.DataFrame(rows, columns=["kind", "evaluated", "passed", "failed", "not_applicable", "pass_rate"]).sort_values(
        ["pass_rate", "kind"], na_position="last", ignore_index=True
    )


def failure_examples(records: list[dict[str, Any]]) -> pd.DataFrame:
    """List failed constraints plus one clearly overlapping partial-following row."""
    checks = constraint_frame(records)
    rows = []
    for _, row in checks.loc[checks["status"].eq("Fail")].iterrows():
        rows.append({"evaluation_id": row["evaluation_id"], "task_name": row["task_name"],
                     "failure_mode": FAILURE_MODES.get(row["kind"], "Formatting violation"),
                     "description": row["description"], "response": row["response"], "notes": row["notes"]})
    for record in records:
        statuses = {item["status"] for item in record["human_results"]}
        if {"Pass", "Fail"}.issubset(statuses):
            rows.append({"evaluation_id": record["evaluation_id"], "task_name": record["task"]["name"],
                         "failure_mode": "Partial instruction following",
                         "description": "Some requirements passed and others failed in the same response.",
                         "response": record["response"],
                         "notes": "Summary of this response; overlaps its individual failed-constraint examples."})
    return pd.DataFrame(rows, columns=FAILURE_COLUMNS)
