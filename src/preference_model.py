"""Educational logistic preference model, grouped by request-and-constraint identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from src.task_library import task_fingerprint

FEATURES = ["compliance", "correctness", "relevance", "clarity", "overall_quality", "failure_fraction"]
FEATURE_LABELS = ["Compliance", "Correctness", "Relevance", "Clarity", "Overall quality", "Failed-constraint fraction"]
PAIR_COLUMNS = ["comparison_id", "task_id", "task_group", "preferred_left", *FEATURES]
MIN_TASK_GROUPS = 8


@dataclass
class PreferenceModelResult:
    """One trained model and its untouched task-group holdout results."""

    model: LogisticRegression
    accuracy: float
    coefficients: pd.DataFrame
    training_count: int
    held_out_count: int
    augmented_training_count: int
    augmented_held_out_count: int
    training_groups: tuple[str, ...]
    held_out_groups: tuple[str, ...]
    training_ids: tuple[str, ...]
    held_out_ids: tuple[str, ...]


def _eligible_comparisons(comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep decisive development comparisons with defined compliance on both sides."""
    eligible = []
    seen = set()
    for comparison in comparisons:
        if comparison["split"] != "development" or comparison["preference"] == "Tie":
            continue
        if comparison["preference"] not in ("Baseline", "Constraint-aware"):
            raise ValueError("A comparison preference must be Baseline, Constraint-aware, or Tie.")
        baseline, improved = comparison["baseline"], comparison["improved"]
        if any(record["task"]["split"] != "development" for record in (baseline, improved)):
            continue
        if baseline["compliance_score"] is None or improved["compliance_score"] is None:
            continue
        if comparison["comparison_id"] in seen:
            raise ValueError("Comparison IDs must be unique.")
        seen.add(comparison["comparison_id"])
        if task_fingerprint(baseline["task"]) != task_fingerprint(improved["task"]):
            raise ValueError("Both responses in a comparison must use the same request and constraints.")
        if baseline["generation_strategy"] != "Baseline" or improved["generation_strategy"] != "Constraint-aware":
            raise ValueError("Comparison responses must have the expected generation strategies.")
        if baseline["generation_metadata"] != improved["generation_metadata"]:
            raise ValueError("Both comparison responses must use identical generation settings.")
        eligible.append(comparison)
    return eligible


def _features(record: dict[str, Any]) -> dict[str, float]:
    """Put comparable rubric and compliance scores on a zero-to-one scale."""
    total, failed = record["total"], record["failed"]
    if not isinstance(total, (int, np.integer)) or isinstance(total, bool) or total < 1:
        raise ValueError("Each response must have at least one constraint.")
    if not isinstance(failed, (int, np.integer)) or isinstance(failed, bool) or not 0 <= failed <= total:
        raise ValueError("Failed-constraint counts must be between zero and the total.")
    compliance = float(record["compliance_score"])
    scores = {key: float(record[key]) for key in FEATURES[1:5]}
    if not np.isfinite(compliance) or not 0 <= compliance <= 100:
        raise ValueError("Defined compliance scores must be between 0 and 100.")
    if any(not np.isfinite(value) or not 1 <= value <= 5 or value % 1 != 0 for value in scores.values()):
        raise ValueError("Quality ratings must be whole numbers from 1 to 5.")
    return {"compliance": compliance / 100, **{key: value / 5 for key, value in scores.items()}, "failure_fraction": failed / total}


def build_preference_pairs(comparisons: list[dict[str, Any]], mirror: bool = False) -> pd.DataFrame:
    """Use baseline-minus-improved features; mirrors reverse both sign and label."""
    rows = []
    for comparison in _eligible_comparisons(comparisons):
        baseline, improved = comparison["baseline"], comparison["improved"]
        a, b = _features(baseline), _features(improved)
        differences = {key: a[key] - b[key] for key in FEATURES}
        metadata = {"comparison_id": comparison["comparison_id"], "task_id": comparison["task_id"],
                    "task_group": task_fingerprint(baseline["task"])}
        outcome = int(comparison["preference"] == "Baseline")
        rows.append({**metadata, "preferred_left": outcome, **differences})
        if mirror:
            rows.append({**metadata, "preferred_left": 1 - outcome, **{key: -value for key, value in differences.items()}})
    return pd.DataFrame(rows, columns=PAIR_COLUMNS)


def training_requirement(comparisons: list[dict[str, Any]]) -> str | None:
    """Report the number of distinct eligible task identities, not row counts."""
    eligible = _eligible_comparisons(comparisons)
    groups = {task_fingerprint(item["baseline"]["task"]) for item in eligible}
    if len(groups) < MIN_TASK_GROUPS:
        return (
            f"Found {len(eligible)} usable development comparisons across {len(groups)} distinct tasks. "
            f"Collect decisive comparisons for at least {MIN_TASK_GROUPS} task identities with defined compliance on both sides. "
            "Ties, undefined compliance, and held-out benchmark judgments are excluded. Repeating or renaming a task does not create a new group."
        )
    return None


def train_preference_model(comparisons: list[dict[str, Any]]) -> PreferenceModelResult:
    """Split task fingerprints before pair expansion or mirroring to avoid leakage."""
    reason = training_requirement(comparisons)
    if reason:
        raise ValueError(reason)
    eligible = _eligible_comparisons(comparisons)
    groups = sorted({task_fingerprint(item["baseline"]["task"]) for item in eligible})
    training_groups, held_out_groups = train_test_split(groups, test_size=0.25, random_state=42)
    training = [item for item in eligible if task_fingerprint(item["baseline"]["task"]) in training_groups]
    held_out = [item for item in eligible if task_fingerprint(item["baseline"]["task"]) in held_out_groups]
    train_pairs = build_preference_pairs(training, mirror=True)
    test_pairs = build_preference_pairs(held_out, mirror=True)
    model = LogisticRegression(fit_intercept=False, max_iter=1000, random_state=42)
    model.fit(train_pairs[FEATURES], train_pairs["preferred_left"])
    return PreferenceModelResult(
        model=model,
        accuracy=float(accuracy_score(test_pairs["preferred_left"], model.predict(test_pairs[FEATURES]))),
        coefficients=pd.DataFrame({"Feature": FEATURE_LABELS, "Coefficient": model.coef_[0]}),
        training_count=len(training), held_out_count=len(held_out),
        augmented_training_count=len(train_pairs), augmented_held_out_count=len(test_pairs),
        training_groups=tuple(training_groups), held_out_groups=tuple(held_out_groups),
        training_ids=tuple(item["comparison_id"] for item in training),
        held_out_ids=tuple(item["comparison_id"] for item in held_out),
    )


def predict_preference(result: PreferenceModelResult, comparison: dict[str, Any]) -> dict[str, Any]:
    """Inspect one eligible saved pair using its existing human ratings."""
    pair = build_preference_pairs([comparison])
    if pair.empty:
        raise ValueError("Choose a decisive development comparison with defined compliance.")
    probability = float(result.model.predict_proba(pair[FEATURES])[0, list(result.model.classes_).index(1)])
    identifier = comparison["comparison_id"]
    membership = "Training comparison" if identifier in result.training_ids else "Held-out task comparison" if identifier in result.held_out_ids else "New comparison"
    return {"probability_baseline": probability, "probability_improved": 1 - probability,
            "preference": "Baseline" if probability >= 0.5 else "Constraint-aware", "membership": membership}
