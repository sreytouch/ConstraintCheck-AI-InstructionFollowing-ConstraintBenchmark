"""Compare human-rated difficulty while displaying sample sizes and N/A coverage."""

import streamlit as st
from matplotlib.figure import Figure

from src.analytics import constraint_difficulty
from src.constraint_checker import CONSTRAINT_TYPES
from src.ui import load_evaluations

st.title("Constraint difficulty")
st.write("Find requirements that need more attention. This view ranks constraint types by their pass rate in saved development evaluations.")
difficulty = constraint_difficulty(load_evaluations())
if difficulty.empty:
    st.info("Save an evaluation first. Each human constraint judgment will contribute to this table.")
    st.stop()
display = difficulty.copy()
display['kind'] = display['kind'].map(lambda kind: CONSTRAINT_TYPES.get(kind, kind))
display['pass_rate'] = display['pass_rate'] * 100
display = display.rename(columns={'kind': 'Constraint type', 'evaluated': 'Applicable checks', 'passed': 'Passed', 'failed': 'Failed', 'not_applicable': 'Not Applicable', 'pass_rate': 'Pass rate (%)'})
st.dataframe(display, hide_index=True, width='stretch')
st.caption("Applicable checks = Pass + Fail. Not Applicable is excluded from that denominator and shown separately. A type with only N/A ratings has an undefined rate and appears last.")
valid = difficulty.dropna(subset=['pass_rate'])
if not valid.empty:
    fig = Figure(figsize=(9, max(3.5, len(valid) * 0.4))); ax = fig.subplots()
    ax.barh([CONSTRAINT_TYPES.get(kind, kind) for kind in valid['kind']], valid['pass_rate'] * 100, color='#3468C0')
    ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xlabel('Human pass rate (%)')
    fig.tight_layout(); st.pyplot(fig, width='stretch')
st.info("Low pass rates suggest where to investigate, not an intrinsic difficulty ranking. Small samples, task wording, model choice, and evaluator judgment all affect results. Inspect failure examples before changing a strategy.")
