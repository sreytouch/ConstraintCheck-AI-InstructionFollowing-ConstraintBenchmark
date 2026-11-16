"""Matched held-out summaries with protocol and recorded-contamination checks."""

import pandas as pd

from src.task_library import HELD_OUT_TASKS, normalized_request


def development_requests(evaluations: list[dict]) -> set[str]:
    return {normalized_request(item["task"]["main_request"]) for item in evaluations if item["task"]["split"] == "development"}


def eligible_held_out(comparisons: list[dict], development: list[dict], protocol_id: str) -> list[dict]:
    tasks = {task["id"]: task for task in HELD_OUT_TASKS}
    used = development_requests(development)
    eligible, seen = [], set()
    for record in comparisons:
        task = tasks.get(record["task_id"])
        if record["split"] != "held_out" or record["protocol_id"] != protocol_id or task is None:
            continue
        if normalized_request(task["main_request"]) in used or record["baseline"]["task"] != task or record["improved"]["task"] != task:
            continue
        if task["id"] not in seen:
            eligible.append(record)
            seen.add(task["id"])
    return eligible


def experiment_summary(comparisons: list[dict]) -> pd.DataFrame:
    """Macro compliance excludes undefined scores; all pairs count in other rates."""
    rows = []
    for arm, strategy in (("baseline", "Baseline"), ("improved", "Constraint-aware")):
        records = [item[arm] for item in comparisons]
        scores = [item["compliance_score"] for item in records if item["compliance_score"] is not None]
        count = len(records)
        rows.append({"Strategy": strategy, "Responses": count,
                     "Average compliance (%)": sum(scores) / len(scores) if scores else None,
                     "Defined compliance": len(scores), "Full-pass responses": sum(item["full_pass"] for item in records),
                     "Full-compliance rate": sum(item["full_pass"] for item in records) / count if count else None,
                     "Acceptance rate": sum(item["accepted"] for item in records) / count if count else None,
                     "Average quality": sum(item["overall_quality"] for item in records) / count if count else None,
                     "N/A judgments": sum(item["not_applicable"] for item in records)})
    return pd.DataFrame(rows)
