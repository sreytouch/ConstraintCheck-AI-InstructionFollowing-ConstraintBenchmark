"""Inspect exactly which human-rated constraints failed."""

import streamlit as st
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from src.analytics import failure_examples
from src.ui import load_evaluations

st.title("Failure analysis")
st.write("Turn a low score into a specific diagnosis. Examples below use final human judgments from development evaluations.")
failures = failure_examples(load_evaluations())
if failures.empty:
    st.info("No failed constraints are saved yet. Evaluate a response and mark violated requirements Fail to explore them here.")
    st.stop()
counts = failures.groupby('failure_mode')['evaluation_id'].nunique().sort_values(ascending=False)
most_common = ', '.join(counts.loc[counts.eq(counts.max())].index)
st.write(f"**Most common failure mode:** {most_common}")
st.caption("Counts are distinct responses per failure mode. One response can appear in several modes. Partial instruction following is an overlapping summary for mixed Pass/Fail responses, not an additional failed constraint.")
fig = Figure(figsize=(9, max(3.8, len(counts) * 0.4))); ax = fig.subplots()
ax.barh(counts.index, counts.values, color='#B97555'); ax.invert_yaxis()
ax.set_xlabel('Responses with this failure mode'); ax.xaxis.set_major_locator(MaxNLocator(integer=True))
fig.tight_layout(); st.pyplot(fig, width='stretch')
mode = st.selectbox('Failure mode', ['All modes', *list(counts.index)])
filtered = failures if mode == 'All modes' else failures.loc[failures['failure_mode'].eq(mode)]
st.dataframe(filtered[['task_name', 'failure_mode', 'description', 'notes']], hide_index=True, width='stretch')
indices = list(filtered.index)
selected = st.selectbox('Inspect an example', indices, format_func=lambda index: f"{filtered.loc[index, 'task_name']} · {filtered.loc[index, 'failure_mode']} · {str(filtered.loc[index, 'evaluation_id'])[:8]} · item {index + 1}")
row = filtered.loc[selected]
st.write('**Violated requirement or summary**'); st.text(row['description'])
st.write('**Response**'); st.text(row['response'])
st.write('**Evaluator notes**'); st.text(row['notes'] or 'No additional notes.')
