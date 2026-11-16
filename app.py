"""ConstraintCheck's Streamlit entry point and guided home page."""

import streamlit as st

st.set_page_config(page_title="ConstraintCheck · AI Constraint Following Benchmark", page_icon="✅", layout="wide")


def home():
    st.caption("CONSTRAINTCHECK · HUMAN FEEDBACK · AI EVALUATION")
    st.title("AI Constraint Following Benchmark")
    st.subheader("Good answers follow every requirement.")
    st.write("A response can sound good and still fail if it ignores explicit requirements. Test length, wording, structure, tone, and meaning separately, then identify exactly where a response fell short.")
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.code("Prompt\n  ↓\nRequirements\n  ↓\nModel response\n  ↓\nConstraint checks\n  ↓\nHuman evaluation\n  ↓\nFailure analysis\n  ↓\nImprove strategy → Test on new tasks", language=None)
        st.page_link("pages/1_Benchmark.py", label="Start with a benchmark task", icon="✅")
    with right.container(border=True):
        st.markdown("**Check what can be counted**")
        st.write("Word limits, sentence counts, bullet counts, and literal phrases have transparent automatic checks. Their counting rules can still need human correction.")
        st.markdown("**Judge what needs understanding**")
        st.write("People assess tone, audience, correctness, information preservation, and every requirement's final Pass / Fail / Not Applicable decision.")
        st.markdown("**Test the change fairly**")
        st.write("Compare baseline and constraint-aware prompting on the same task and settings. Judge both on a separate ten-task test after freezing your approach.")
    for column, title, body in zip(st.columns(3), ["20 practice tasks", "16 constraint types", "10 held-out tasks"], ["Use the library or build your own task. Save feedback and export the full evidence.", "Inspect which requirements fail most often. Compare compliance with quality and acceptance.", "Keep unseen tasks separate from prompt design. Track matched results within a fixed protocol."]):
        with column.container(border=True):
            st.markdown(f"**{title}**")
            st.write(body)
    st.info("Educational benchmark: the toy preference model learns from human rating differences. No language-model weights are updated, and no production RLHF or PPO training occurs.")
    st.caption("Python and SQLite run locally. Only generation calls send task content to OpenAI. No synthetic judgments are preloaded.")


navigation = st.navigation([
    st.Page(home, title="Home", icon="🏠", default=True),
    st.Page("pages/1_Benchmark.py", title="Benchmark", icon="✅"),
    st.Page("pages/2_Custom_Task.py", title="Custom Task Builder", icon="✍️"),
    st.Page("pages/3_Compare_Strategies.py", title="Side-by-Side Comparison", icon="⚖️"),
    st.Page("pages/4_Dataset.py", title="Dataset", icon="🗂️"),
    st.Page("pages/5_Analytics.py", title="Analytics", icon="📊"),
    st.Page("pages/6_Failure_Analysis.py", title="Failure Analysis", icon="🔎"),
    st.Page("pages/7_Constraint_Difficulty.py", title="Constraint Difficulty", icon="🧩"),
    st.Page("pages/12_Improvement_Experiment.py", title="Improvement Experiment", icon="🔬"),
    st.Page("pages/8_Held_Out_Test.py", title="Held-Out Benchmark", icon="🧪"),
    st.Page("pages/9_Preference_Model.py", title="Preference Model", icon="📈"),
    st.Page("pages/10_Reward_Hacking.py", title="Reward Hacking", icon="🎯"),
    st.Page("pages/11_Concepts.py", title="Concepts", icon="📖"),
])
with st.sidebar:
    st.caption("Local educational benchmark · Human judgments first")
destination = st.session_state.pop("navigate_to", None)
if destination:
    st.switch_page(destination)
navigation.run()
