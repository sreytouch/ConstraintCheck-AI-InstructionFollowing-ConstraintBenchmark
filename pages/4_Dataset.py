"""Filter complete evaluation snapshots and export every field."""
import streamlit as st
from src.analytics import evaluation_frame
from src.constraint_checker import CONSTRAINT_TYPES
from src.evaluation import export_csv
from src.ui import load_comparisons, load_evaluations, show_response, show_task

st.title("Dataset")
split_label = st.radio("Data split", ["Development", "Held-out"], horizontal=True)
split = "development" if split_label == "Development" else "held_out"
kind = st.radio("Record type", ["Evaluations", "Comparisons"], horizontal=True)
records = load_evaluations(split) if kind == "Evaluations" else load_comparisons(split)
if not records:
    st.info("No saved records in this collection yet. Generate responses and save your judgments first.")
    st.stop()
if kind == "Comparisons":
    preference = st.selectbox("Preferred strategy", ["All", "Baseline", "Constraint-aware", "Tie"])
    filtered = [record for record in records if preference == "All" or record["preference"] == preference]
    st.dataframe([{key: record[key] for key in ("comparison_id", "timestamp", "task_name", "protocol_id", "preference", "rationale")} for record in filtered], hide_index=True, width="stretch")
else:
    task_name = st.selectbox("Task", ["All", *sorted({item["task"]["name"] for item in records})])
    strategy = st.selectbox("Strategy", ["All", "Baseline", "Constraint-aware"])
    model = st.selectbox("Model", ["All", *sorted({item["generation_metadata"]["model"] for item in records})])
    acceptance = st.selectbox("Acceptance", ["All", "Accepted", "Rejected"])
    score_range = st.slider("Compliance score range", 0, 100, (0, 100))
    include_undefined = st.checkbox("Include undefined compliance (all N/A)", value=True)
    violation = st.selectbox("Violated constraint type", ["All", *CONSTRAINT_TYPES], format_func=lambda value: CONSTRAINT_TYPES.get(value, value))
    filtered = []
    for item in records:
        failed_ids = {row["constraint_id"] for row in item["human_results"] if row["status"] == "Fail"}
        kinds = {rule["kind"] for rule in item["task"]["constraints"] if rule["id"] in failed_ids}
        score = item["compliance_score"]
        if task_name != "All" and item["task"]["name"] != task_name: continue
        if strategy != "All" and item["generation_strategy"] != strategy: continue
        if model != "All" and item["generation_metadata"]["model"] != model: continue
        if acceptance != "All" and item["accepted"] != (acceptance == "Accepted"): continue
        if score is None and not include_undefined: continue
        if score is not None and not score_range[0] <= score <= score_range[1]: continue
        if violation != "All" and violation not in kinds: continue
        filtered.append(item)
    st.dataframe(evaluation_frame(filtered), hide_index=True, width="stretch")
st.caption(f"{len(filtered)} / {len(records)} records · UTC timestamps")
st.download_button("Download CSV", export_csv(filtered), file_name=f"{split}_{kind.lower()}.csv", mime="text/csv", disabled=not filtered)
st.caption("Exports include every stored field. Nested task, check, and comparison snapshots are JSON cells. Formula-like text is escaped for spreadsheets; stored data is unchanged.")
if not filtered:
    st.info("No records match these filters.")
    st.stop()
identifier = "evaluation_id" if kind == "Evaluations" else "comparison_id"
lookup = {item[identifier]: item for item in filtered}
selected = st.selectbox("Inspect record", list(lookup), format_func=lambda value: f"{lookup[value]['timestamp'][:19]} · {value[:8]}")
record = lookup[selected]
if kind == "Evaluations":
    show_task(record["task"])
    show_response(record)
else:
    show_task(record["baseline"]["task"])
    for column, arm in zip(st.columns(2), ("baseline", "improved")):
        with column:
            show_response(record[arm])
    st.write(f"Preferred: {record['preference']}")
    st.text(record["rationale"])
