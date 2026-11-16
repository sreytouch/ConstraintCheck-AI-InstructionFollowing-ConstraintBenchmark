"""Practice-library generation and human evaluation."""
import streamlit as st
from src.ui import render_single, show_task, task_selector

st.title("Benchmark")
st.write("Select a practice task, generate one response, and judge each requirement independently.")
task = task_selector("benchmark")
with st.container(border=True):
    show_task(task)
render_single(task, "benchmark_response")
