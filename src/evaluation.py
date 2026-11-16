"""Validated human judgments, separate automatic evidence, and safe exports."""

import csv
from datetime import datetime, timezone
import io
import json
import math
from uuid import UUID, uuid4

from src.constraint_checker import check_constraints
from src.generation import STRATEGIES
from src.task_library import validate_task

QUALITY_CRITERIA = {
    "correctness": "Is the response factually and logically correct?",
    "relevance": "Does it answer the main request?",
    "clarity": "Is it easy to understand?",
    "overall_quality": "How successful is the response overall, considering the whole task?",
}
STATUSES = ("Pass", "Fail", "Not Applicable")
EVALUATION_FIELDS = ["evaluation_id", "timestamp", "task", "response", "generation_strategy", "automatic_results", "human_results", "compliance_score", "passed", "failed", "not_applicable", "applicable", "total", "full_pass", *QUALITY_CRITERIA, "accepted", "rationale", "generation_metadata"]
COMPARISON_FIELDS = ["comparison_id", "timestamp", "task_id", "task_name", "main_request", "split", "protocol_id", "preference", "rationale", "baseline", "improved"]


class ValidationError(ValueError):
    """Feedback is incomplete or inconsistent with its task."""


def _text(value, name: str, required: bool = True) -> str:
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValidationError(f"Enter {name}.")
    return value.strip()


def _identifier(value: str | None) -> str:
    if value is None:
        return str(uuid4())
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError("Record IDs must be valid UUIDs.") from error


def _timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError
        return value
    except (TypeError, ValueError) as error:
        raise ValidationError("Record timestamps must be valid UTC timestamps.") from error


def _human_results(results: list[dict]) -> list[dict]:
    if not isinstance(results, list):
        raise ValidationError("Provide a judgment for every constraint.")
    clean = []
    for result in results:
        if not isinstance(result, dict) or set(result) != {"constraint_id", "status", "notes"}:
            raise ValidationError("Each judgment needs constraint_id, status, and notes.")
        if result["status"] not in STATUSES:
            raise ValidationError("Choose Pass, Fail, or Not Applicable for every constraint.")
        clean.append({"constraint_id": _text(result["constraint_id"], "a constraint ID"), "status": result["status"], "notes": _text(result["notes"], "notes", False)})
    if len({item["constraint_id"] for item in clean}) != len(clean):
        raise ValidationError("Judge each constraint exactly once.")
    return clean


def calculate_compliance(human_results: list[dict]) -> dict:
    """N/A has no denominator weight and can never produce a full-pass result."""
    results = _human_results(human_results)
    passed = sum(item["status"] == "Pass" for item in results)
    failed = sum(item["status"] == "Fail" for item in results)
    na = sum(item["status"] == "Not Applicable" for item in results)
    applicable = passed + failed
    return {"passed": passed, "failed": failed, "not_applicable": na, "applicable": applicable,
            "total": len(results), "compliance_score": 100 * passed / applicable if applicable else None,
            "full_pass": bool(results) and passed == len(results)}


def _metadata(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {"model", "temperature", "max_output_tokens", "protocol_id"}:
        raise ValidationError("Generation metadata must include model, temperature, token budget, and protocol ID.")
    model = _text(value["model"], "the generation model")
    protocol = _text(value["protocol_id"], "the protocol ID")
    temperature = value["temperature"]
    if temperature is not None and (isinstance(temperature, bool) or not isinstance(temperature, (float, int)) or not math.isfinite(temperature) or not 0 <= temperature <= 2):
        raise ValidationError("Temperature must be absent or between zero and two.")
    budget = value["max_output_tokens"]
    if isinstance(budget, bool) or not isinstance(budget, int) or not 64 <= budget <= 16384:
        raise ValidationError("The output budget must be a whole number from 64 to 16384.")
    return {"model": model, "temperature": temperature, "max_output_tokens": budget, "protocol_id": protocol}


def make_evaluation(task: dict, response: str, generation_strategy: str, human_results: list[dict], quality_scores: dict, accepted: bool, rationale: str, generation_metadata: dict, evaluation_id: str | None = None) -> dict:
    """Build a complete record only after every judgment is explicitly supplied."""
    task = validate_task(task)
    response = _text(response, "a model response")
    if generation_strategy not in STRATEGIES:
        raise ValidationError("Choose a supported generation strategy.")
    human = _human_results(human_results)
    expected = [item["id"] for item in task["constraints"]]
    if set(expected) != {item["constraint_id"] for item in human}:
        raise ValidationError("Judge every task constraint exactly once; do not add unknown constraints.")
    lookup = {item["constraint_id"]: item for item in human}
    human = [lookup[identifier] for identifier in expected]
    automatic = check_constraints(response, task["constraints"])
    for auto, judgment in zip(automatic, human):
        if auto["method"] == "automatic" and auto["status"] != judgment["status"] and not judgment["notes"]:
            raise ValidationError(f"Add a note explaining the automatic-check override for {judgment['constraint_id']}.")
    if not isinstance(quality_scores, dict) or set(quality_scores) != set(QUALITY_CRITERIA):
        raise ValidationError("Provide all four quality ratings.")
    for value in quality_scores.values():
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise ValidationError("Quality ratings must be whole numbers from 1 to 5.")
    if not isinstance(accepted, bool):
        raise ValidationError("Choose Yes or No for response acceptance.")
    return {
        "evaluation_id": _identifier(evaluation_id), "timestamp": datetime.now(timezone.utc).isoformat(),
        "task": task, "response": response, "generation_strategy": generation_strategy,
        "automatic_results": automatic, "human_results": human, **calculate_compliance(human),
        **quality_scores, "accepted": accepted, "rationale": _text(rationale, "an evaluation rationale"),
        "generation_metadata": _metadata(generation_metadata),
    }


def validate_evaluation(record: dict) -> dict:
    """Recompute derived values and check snapshots before writes and after reads."""
    if not isinstance(record, dict) or set(record) != set(EVALUATION_FIELDS):
        raise ValidationError("Evaluation record fields are incomplete or unexpected.")
    expected = make_evaluation(record["task"], record["response"], record["generation_strategy"], record["human_results"], {key: record[key] for key in QUALITY_CRITERIA}, record["accepted"], record["rationale"], record["generation_metadata"], record["evaluation_id"])
    expected["timestamp"] = _timestamp(record["timestamp"])
    if expected != record:
        raise ValidationError("Evaluation record contains inconsistent scores, automatic checks, or task details.")
    return expected


def make_comparison(baseline: dict, improved: dict, preference: str, rationale: str, comparison_id: str | None = None) -> dict:
    baseline, improved = validate_evaluation(baseline), validate_evaluation(improved)
    if baseline["evaluation_id"] == improved["evaluation_id"]:
        raise ValidationError("The two responses need different evaluation IDs.")
    if baseline["task"] != improved["task"] or baseline["generation_metadata"] != improved["generation_metadata"]:
        raise ValidationError("Compare responses generated for the exact same task and settings.")
    if baseline["generation_strategy"] != "Baseline" or improved["generation_strategy"] != "Constraint-aware":
        raise ValidationError("Compare one Baseline and one Constraint-aware response.")
    if preference not in (*STRATEGIES, "Tie"):
        raise ValidationError("Choose which response is better, or choose Tie.")
    task = baseline["task"]
    return {"comparison_id": _identifier(comparison_id), "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": task["id"], "task_name": task["name"], "main_request": task["main_request"], "split": task["split"],
            "protocol_id": baseline["generation_metadata"]["protocol_id"], "preference": preference,
            "rationale": _text(rationale, "a comparison rationale"), "baseline": baseline, "improved": improved}


def validate_comparison(record: dict) -> dict:
    if not isinstance(record, dict) or set(record) != set(COMPARISON_FIELDS):
        raise ValidationError("Comparison record fields are incomplete or unexpected.")
    expected = make_comparison(record["baseline"], record["improved"], record["preference"], record["rationale"], record["comparison_id"])
    expected["timestamp"] = _timestamp(record["timestamp"])
    if expected != record:
        raise ValidationError("Comparison metadata is inconsistent with its evaluations.")
    return expected


def export_csv(records: list[dict]) -> bytes:
    """Preserve nested snapshots as JSON; neutralize spreadsheet-formula text."""
    output = io.StringIO(newline="")
    fields = list(dict.fromkeys(key for record in records for key in record)) if records else EVALUATION_FIELDS
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for record in records:
        row = {}
        for key, value in record.items():
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False, allow_nan=False)
            elif isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
                value = "'" + value
            row[key] = value
        writer.writerow(row)
    return output.getvalue().encode("utf-8")
