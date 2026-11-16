"""Separate, fixed tasks with one durable judgment per task and protocol."""
import streamlit as st
from src.experiment_ui import show_experiment_results
from src.experiments import development_requests, eligible_held_out
from src.generation import generation_metadata
from src.task_library import HELD_OUT_TASKS, normalized_request
from src.ui import load_comparisons, load_evaluations, render_pair, settings_or_stop, show_response, show_task

st.title("Held-Out Benchmark")
st.info("Freeze your strategy before opening these tasks. If a task influences prompt design, it is no longer unseen evidence. For another iteration, design fresh tasks and version the protocol.")
settings = settings_or_stop()
protocol = generation_metadata(settings)["protocol_id"]
development = load_evaluations("development")
comparisons = load_comparisons("held_out")
eligible = eligible_held_out(comparisons, development, protocol)
st.caption(f"Current generation protocol: {protocol}. Model and sampling changes create a separate result cohort.")
show_experiment_results(eligible)
cohort = [record for record in comparisons if record["protocol_id"] == protocol]
if len(cohort) != len(eligible):
    st.warning("Some saved results are excluded because the task was reused in development or no longer matches the fixed task library.")
lookup = {task["id"]: task for task in HELD_OUT_TASKS}
selected = st.selectbox("Held-out task", list(lookup), format_func=lambda value: lookup[value]["name"])
task = lookup[selected]
with st.container(border=True):
    show_task(task)
existing = next((item for item in cohort if item["task_id"] == selected), None)
if existing:
    st.success(f"A judgment is already saved for this task and protocol: {existing['preference']}.")
    for column, arm in zip(st.columns(2), ("baseline", "improved")):
        with column:
            show_response(existing[arm])
    st.text(existing["rationale"])
elif normalized_request(task["main_request"]) in development_requests(development):
    st.warning("This request already appears in development evaluations. Choose another task; it cannot count as unseen.")
else:
    render_pair(task, f"held_{selected}_{protocol}", held_out=True)
st.caption("One response pair per task is retained in the session; the first saved judgment per task/protocol is immutable. Restarting an unsaved session can regenerate a pair, so this is an educational tool, not a tamper-proof benchmark. Labels are visible and may bias judgments.")
