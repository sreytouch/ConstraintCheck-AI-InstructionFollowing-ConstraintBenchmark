"""Explain and review the fixed prompt experiment using matched held-out tasks."""
import streamlit as st
from src.experiment_ui import show_experiment_results
from src.experiments import eligible_held_out
from src.generation import BASELINE_INSTRUCTIONS, IMPROVED_INSTRUCTIONS, generation_metadata
from src.ui import load_comparisons, load_evaluations, settings_or_stop

st.title("Improvement Experiment")
st.write("Evaluate → identify a weakness → make a targeted change → evaluate again on new tasks.")
st.info("The constraint-aware strategy is a fixed prompt that asks the model to check every requirement. It is not trained from your feedback and is not guaranteed to improve performance.")
for column, title, instructions in zip(st.columns(2), ("Baseline Prompting", "Constraint-Aware Prompting"), (BASELINE_INSTRUCTIONS, IMPROVED_INSTRUCTIONS)):
    with column.container(border=True):
        st.markdown(f"**{title}**")
        st.text(instructions)
st.write("Explore weaknesses using Benchmark, Failure Analysis, and development comparisons. Freeze the prompt and model settings, then judge the ten separate tasks in Held-Out Benchmark. Comparing both strategies on the same tasks avoids differences caused only by task selection.")
st.page_link("pages/8_Held_Out_Test.py", label="Run the held-out experiment", icon="🧪")
records = load_comparisons("held_out")
current = generation_metadata(settings_or_stop())["protocol_id"]
protocols = sorted({current, *(record["protocol_id"] for record in records)})
protocol = st.selectbox("Result protocol", protocols, index=protocols.index(current))
cohort = [record for record in records if record["protocol_id"] == protocol]
if cohort:
    st.json(cohort[0]["baseline"]["generation_metadata"])
eligible = eligible_held_out(cohort, load_evaluations("development"), protocol)
show_experiment_results(eligible)
st.caption("A protocol fingerprints the fixed prompts, model, temperature setting, and token budget. Different protocols are not pooled. Reusing these tasks to tune another strategy invalidates their unseen status even when the protocol changes. Request-text reuse recorded in development is detected; outside exposure and paraphrases are not.")
