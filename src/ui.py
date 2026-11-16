"""Shared Streamlit controls; judgments stay attached to their generated task."""

import sqlite3
from uuid import uuid4

import pandas as pd
import streamlit as st

from src.config import ConfigurationError, Settings, get_settings
from src.constraint_checker import CONSTRAINT_TYPES, check_constraints
from src.database import DataIntegrityError, get_comparisons, get_evaluations, save_comparison, save_evaluation
from src.evaluation import QUALITY_CRITERIA, calculate_compliance, make_comparison, make_evaluation
from src.generation import BASELINE, IMPROVED, STRATEGIES, generation_metadata
from src.openai_client import GenerationError, generate_pair, generate_response
from src.task_library import DEVELOPMENT_TASKS


def settings_or_stop() -> Settings:
    try:
        return get_settings()
    except ConfigurationError as error:
        st.error(str(error))
        st.stop()


def load_evaluations(split: str | None = "development") -> list[dict]:
    try:
        return get_evaluations(settings_or_stop().db_path, split=split)
    except (sqlite3.Error, OSError, DataIntegrityError):
        st.error("Could not read evaluations. Check the database path and permissions. If the file was edited outside the app, restore a valid backup.")
        st.stop()


def load_comparisons(split: str | None = "development") -> list[dict]:
    try:
        return get_comparisons(settings_or_stop().db_path, split=split)
    except (sqlite3.Error, OSError, DataIntegrityError):
        st.error("Could not read comparisons. Check database permissions or restore a valid database backup.")
        st.stop()


def show_task(task: dict) -> None:
    st.markdown(f"**{task['name']}**")
    st.text(task["main_request"])
    for index, constraint in enumerate(task["constraints"], 1):
        st.text(f"{index}. {constraint['description']}")


def task_selector(key: str) -> dict:
    categories = sorted({task["category"] for task in DEVELOPMENT_TASKS})
    category = st.selectbox("Task category", ["All", *categories], key=f"{key}_category")
    tasks = [task for task in DEVELOPMENT_TASKS if category == "All" or task["category"] == category]
    selected = st.selectbox("Evaluation task", [task["id"] for task in tasks], format_func=lambda value: next(task["name"] for task in tasks if task["id"] == value), key=f"{key}_task")
    return next(task for task in tasks if task["id"] == selected)


def generation_ready(settings: Settings) -> bool:
    st.caption(f"Model: {settings.model} · Protocol: {generation_metadata(settings)['protocol_id']}")
    st.caption("Generation sends the request and constraints to OpenAI and may incur API charges. Set OPENAI_MODEL in .env to collect results for another model.")
    if not settings.api_key:
        st.info("To generate responses, copy .env.example to .env and set OPENAI_API_KEY. You can explore the learning pages and saved data without a key.")
    return bool(settings.api_key)


def _draft(task: dict, response: str, strategy: str, metadata: dict) -> dict:
    return {
        "id": str(uuid4()), "task": task, "response": response, "strategy": strategy,
        "metadata": metadata, "feedback": {},
    }


def _remember(feedback: dict, field: str, widget_key: str) -> None:
    feedback[field] = st.session_state[widget_key]


def _review(draft: dict, disabled: bool = False) -> None:
    """Automatic evidence and human decisions are separate, explicit controls."""
    feedback = draft["feedback"]
    automatic = check_constraints(draft["response"], draft["task"]["constraints"])
    st.markdown("**Automatic checks**")
    st.dataframe(pd.DataFrame([{
        "Requirement": constraint["description"],
        "Check": result["status"] if result["method"] == "automatic" else "Human review required",
        "Method": "Automatically Checked" if result["method"] == "automatic" else "Human only",
        "Details": result["detail"],
    } for constraint, result in zip(draft["task"]["constraints"], automatic)]), hide_index=True, width="stretch")
    st.caption("Word, sentence, bullet, and phrase checks use documented counting conventions. They do not judge meaning, truth, tone, or audience.")
    st.markdown("**Human judgments**")
    st.caption("Review every requirement. Your decisions determine compliance. Add a note if you override an automatic result, including choosing Not Applicable. N/A is excluded from compliance but prevents a full pass.")
    choices = ["Pass", "Fail", "Not Applicable"]
    for constraint, result in zip(draft["task"]["constraints"], automatic):
        field = f"status_{constraint['id']}"
        key = f"{draft['id']}_{field}"
        value = feedback.get(field)
        st.radio(constraint["description"], choices, index=choices.index(value) if value in choices else None, key=key, horizontal=True, disabled=disabled, on_change=_remember, args=(feedback, field, key))
        if result["method"] == "automatic":
            st.caption(f"Automatically Checked: {result['status']} · {result['detail']}")
        note_field = f"notes_{constraint['id']}"
        note_key = f"{draft['id']}_{note_field}"
        st.text_input(f"Notes · {constraint['id']}", value=feedback.get(note_field, ""), key=note_key, disabled=disabled, on_change=_remember, args=(feedback, note_field, note_key))
    results = _human_results(draft)
    if all(item["status"] in choices for item in results):
        score = calculate_compliance(results)
        value = f"{score['compliance_score']:.1f}%" if score["compliance_score"] is not None else "Not defined"
        st.metric("Constraint compliance", value)
        st.caption(f"{score['passed']} passed / {score['applicable']} applicable · {score['not_applicable']} N/A · Full pass: {'Yes' if score['full_pass'] else 'No'}")
    else:
        st.info("Complete every constraint judgment to calculate compliance.")
    st.markdown("**Response quality**")
    for criterion, description in QUALITY_CRITERIA.items():
        field = f"quality_{criterion}"
        key = f"{draft['id']}_{field}"
        st.slider(criterion.replace("_", " ").title(), 1, 5, feedback.get(field, 3), help=description, key=key, disabled=disabled, on_change=_remember, args=(feedback, field, key))
    accepted_key = f"{draft['id']}_accepted"
    accepted = feedback.get("accepted")
    st.radio("Would you accept this response?", ["Yes", "No"], index=["Yes", "No"].index(accepted) if accepted else None, key=accepted_key, horizontal=True, disabled=disabled, on_change=_remember, args=(feedback, "accepted", accepted_key))
    rationale_key = f"{draft['id']}_rationale"
    st.text_area("Evaluation rationale", value=feedback.get("rationale", ""), key=rationale_key, max_chars=5000, disabled=disabled, on_change=_remember, args=(feedback, "rationale", rationale_key))


def _human_results(draft: dict) -> list[dict]:
    return [{"constraint_id": constraint["id"], "status": draft["feedback"].get(f"status_{constraint['id']}"), "notes": draft["feedback"].get(f"notes_{constraint['id']}", "")} for constraint in draft["task"]["constraints"]]


def _record(draft: dict) -> dict:
    accepted = draft["feedback"].get("accepted")
    return make_evaluation(
        task=draft["task"], response=draft["response"], generation_strategy=draft["strategy"],
        human_results=_human_results(draft), quality_scores={key: draft["feedback"].get(f"quality_{key}", 3) for key in QUALITY_CRITERIA},
        accepted=(accepted == "Yes") if accepted is not None else None,
        rationale=draft["feedback"].get("rationale", ""), generation_metadata=draft["metadata"], evaluation_id=draft["id"],
    )


def render_single(task: dict, state_key: str) -> None:
    settings = settings_or_stop()
    strategy = st.radio("Generation strategy", STRATEGIES, horizontal=True, key=f"{state_key}_strategy")
    ready = generation_ready(settings)
    if st.button("Generate response", type="primary", disabled=not ready, key=f"{state_key}_generate"):
        try:
            with st.spinner("Generating a response…"):
                response = generate_response(task, strategy, settings)
            st.session_state[state_key] = {"draft": _draft(task, response, strategy, generation_metadata(settings)), "saved": False}
        except GenerationError as error:
            st.error(str(error))
    current = st.session_state.get(state_key)
    if not current:
        st.info("Generate a response to inspect its checks and record your judgment.")
        return
    draft = current["draft"]
    stale = draft["task"] != task or draft["strategy"] != strategy or draft["metadata"] != generation_metadata(settings)
    if stale:
        st.warning("The selected task, strategy, or settings changed. Restore them or generate a fresh response before saving.")
    with st.expander("Task and settings used for this response"):
        show_task(draft["task"])
        st.json(draft["metadata"])
    st.subheader("Model response")
    with st.container(border=True):
        st.text(draft["response"])
    _review(draft, current["saved"])
    if st.button("Save evaluation", type="primary", disabled=current["saved"] or stale, key=f"{state_key}_save"):
        try:
            inserted = save_evaluation(_record(draft), settings.db_path)
            current["saved"] = True
            current["existing"] = not inserted
            st.rerun()
        except (ValueError, DataIntegrityError) as error:
            st.error(str(error))
        except (sqlite3.Error, OSError):
            st.error("Could not save this evaluation. Check database permissions; your draft is retained.")
    if current["saved"]:
        st.success("Evaluation saved." if not current.get("existing") else "This evaluation was already saved. The existing judgment was retained.")


def render_pair(task: dict, state_key: str, held_out: bool = False) -> None:
    settings = settings_or_stop()
    metadata = generation_metadata(settings)
    current = st.session_state.get(state_key)
    ready = generation_ready(settings)
    st.caption("Both strategies receive the same request, constraints, model, sampling settings, and token budget in two independent calls. Identical responses are a valid tie.")
    if st.button("Generate both strategies", key=f"{state_key}_generate", type="primary", disabled=not ready or (held_out and current is not None)):
        try:
            with st.spinner("Generating both strategies…"):
                responses = generate_pair(task, settings)
            current = {"id": str(uuid4()), "saved": False, "feedback": {}, "task": task, "metadata": metadata,
                       "drafts": {strategy: _draft(task, responses[strategy], strategy, metadata) for strategy in STRATEGIES}}
            st.session_state[state_key] = current
            st.rerun()
        except GenerationError as error:
            st.error(str(error))
    if not current:
        return
    stale = current["task"] != task or current["metadata"] != metadata
    if stale:
        st.warning("The task or settings changed. Restore them or generate a new pair before saving.")
    for strategy, column in zip(STRATEGIES, st.columns(2, gap="large")):
        with column:
            st.subheader(strategy)
            with st.container(border=True):
                st.text(current["drafts"][strategy]["response"])
            with st.expander(f"Evaluate {strategy}", expanded=True):
                _review(current["drafts"][strategy], current["saved"])
    choices = [BASELINE, IMPROVED, "Tie"]
    feedback = current["feedback"]
    preference_key = f"{current['id']}_preference"
    value = feedback.get("preference")
    st.radio("Which response is better?", choices, index=choices.index(value) if value else None, horizontal=True, key=preference_key, disabled=current["saved"], on_change=_remember, args=(feedback, "preference", preference_key))
    reason_key = f"{current['id']}_rationale"
    st.text_area("Comparison rationale", value=feedback.get("rationale", ""), key=reason_key, max_chars=5000, disabled=current["saved"], on_change=_remember, args=(feedback, "rationale", reason_key))
    if st.button("Save comparison and both evaluations", type="primary", key=f"{state_key}_save", disabled=current["saved"] or stale):
        try:
            comparison = make_comparison(_record(current["drafts"][BASELINE]), _record(current["drafts"][IMPROVED]), feedback.get("preference"), feedback.get("rationale", ""), comparison_id=current["id"])
            inserted = save_comparison(comparison, settings.db_path)
            current["saved"] = True
            current["existing"] = not inserted
            st.rerun()
        except (ValueError, DataIntegrityError) as error:
            st.error(str(error))
        except (sqlite3.Error, OSError):
            st.error("Could not save the comparison. Nothing from this pair was partially saved. Check database permissions; your draft is retained.")
    if current["saved"]:
        st.success("Comparison and both evaluations saved." if not current.get("existing") else "A judgment already exists for this pair or held-out task/protocol. The existing saved vote was retained.")


def show_response(record: dict) -> None:
    """Read-only record inspection used by the dataset and completed tests."""
    st.markdown(f"**{record['generation_strategy']}**")
    st.text(record["response"])
    results = {row["constraint_id"]: row for row in record["human_results"]}
    automatic = {row["constraint_id"]: row for row in record["automatic_results"]}
    st.dataframe(pd.DataFrame([{
        "Requirement": constraint["description"], "Type": CONSTRAINT_TYPES[constraint["kind"]],
        "Automatic": automatic[constraint["id"]]["status"],
        "Human": results[constraint["id"]]["status"], "Notes": results[constraint["id"]]["notes"],
    } for constraint in record["task"]["constraints"]]), hide_index=True, width="stretch")
    score = record["compliance_score"]
    st.write(f"Compliance: {score:.1f}%" if score is not None else "Compliance: undefined (all constraints marked N/A)")
    st.write(f"Full pass: {'Yes' if record['full_pass'] else 'No'} · Accepted: {'Yes' if record['accepted'] else 'No'}")
    st.dataframe(pd.DataFrame([{"Criterion": key.replace('_', ' ').title(), "Score": record[key]} for key in QUALITY_CRITERIA]), hide_index=True)
    st.markdown("**Rationale**")
    st.text(record["rationale"])
    st.caption(f"{record['timestamp']} · {record['generation_metadata']['model']} · {record['generation_metadata']['protocol_id']}")
