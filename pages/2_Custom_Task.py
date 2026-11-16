"""Typed custom constraints keep automatic checks aligned with the actual prompt."""
import streamlit as st
from src.constraint_checker import CONSTRAINT_TYPES, NUMERIC_KINDS
from src.task_library import task_fingerprint, validate_task
from src.ui import render_single


def remember(key):
    st.session_state.setdefault("custom_inputs", {})[key] = st.session_state[key]


def input_value(key, default):
    st.session_state.setdefault(key, st.session_state.get("custom_inputs", {}).get(key, default))


def compare_task(task):
    st.session_state["comparison_custom_task"] = task
    st.session_state["comparison_source"] = "Custom task"
    st.session_state["navigate_to"] = "pages/3_Compare_Strategies.py"


st.title("Custom Task Builder")
st.write("Describe a request, then add clear requirements. Count and phrase rules are generated from typed values so the prompt and automatic checker agree.")
for key, default in (("custom_name", "My custom task"), ("custom_request", ""), ("custom_count", 5)):
    input_value(key, default)
name = st.text_input("Task name", key="custom_name", max_chars=150, on_change=remember, args=("custom_name",))
request = st.text_area("Main request", key="custom_request", height=130, max_chars=20000, on_change=remember, args=("custom_request",))
count = st.number_input("Number of constraints", min_value=1, max_value=10, key="custom_count", step=1, on_change=remember, args=("custom_count",))
rules = []
for index in range(int(count)):
    prefix = f"custom_rule_{index}"
    input_value(f"{prefix}_kind", "maximum_words" if index == 0 else "tone")
    with st.expander(f"Constraint {index + 1}", expanded=True):
        kind = st.selectbox("Constraint type", list(CONSTRAINT_TYPES), format_func=CONSTRAINT_TYPES.get, key=f"{prefix}_kind", on_change=remember, args=(f"{prefix}_kind",))
        if kind in NUMERIC_KINDS:
            input_value(f"{prefix}_{kind}", 80 if "words" in kind else 3)
            value = int(st.number_input("Count", min_value=1, max_value=10000, step=1, key=f"{prefix}_{kind}", on_change=remember, args=(f"{prefix}_{kind}",)))
            unit = "words" if "words" in kind else "sentences" if "sentences" in kind else "bullet points"
            operator = "at most" if kind.startswith("maximum") else "at least" if kind.startswith("minimum") else "exactly"
            description = f"Use {operator} {value} {unit}."
            st.caption(description + " For 'under N', choose a maximum of N minus one.")
        elif kind in ("required_phrase", "prohibited_phrase"):
            input_value(f"{prefix}_phrase", "")
            value = st.text_input("Exact phrase or symbol", key=f"{prefix}_phrase", on_change=remember, args=(f"{prefix}_phrase",)).strip()
            description = f"{'Include' if kind == 'required_phrase' else 'Do not use'} the literal phrase or symbol: {value}"
            st.caption("Phrase matching ignores case and repeated whitespace, but does not infer synonyms.")
        else:
            input_value(f"{prefix}_description", "")
            description = st.text_input("Requirement", key=f"{prefix}_description", max_chars=2000, placeholder="For example: Use a calm, professional tone.", on_change=remember, args=(f"{prefix}_description",))
            value = None
        rules.append({"id": f"c{index + 1}", "kind": kind, "description": description, "value": value})
try:
    task = validate_task({"id": "custom-draft", "name": name, "category": "Custom", "main_request": request, "constraints": rules, "split": "development"})
    task["id"] = "custom-" + task_fingerprint(task)[:16]
except ValueError as error:
    st.info(f"Complete your task before generation: {error}")
    st.stop()
st.caption("Custom tasks are development data. Reusing a held-out request here makes it ineligible for clean test results.")
render_single(task, "custom_response")
st.button("Use this task in side-by-side comparison", on_click=compare_task, args=(task,))
