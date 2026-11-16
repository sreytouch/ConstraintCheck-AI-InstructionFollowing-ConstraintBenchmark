"""Matched development comparisons, including custom tasks."""
import streamlit as st
from src.ui import render_pair, show_task, task_selector

st.title("Side-by-Side Comparison")
st.write("Evaluate both responses, then choose the one that better satisfies the full task. A high compliance score does not replace correctness or relevance.")
custom = st.session_state.get("comparison_custom_task")
source = st.radio("Task source", ["Practice library", "Custom task"] if custom else ["Practice library"], horizontal=True, key="comparison_source")
task = custom if source == "Custom task" else task_selector("compare")
if not custom:
    st.caption("To compare a custom task, create it in Custom Task Builder and choose Use this task in side-by-side comparison.")
with st.container(border=True):
    show_task(task)
render_pair(task, "development_pair")
