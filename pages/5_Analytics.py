"""Development-data dashboard with explicit coverage and sampling limitations."""

import pandas as pd
import streamlit as st
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from src.analytics import constraint_difficulty, constraint_frame, evaluation_frame, summary_metrics
from src.constraint_checker import CONSTRAINT_TYPES
from src.ui import load_evaluations

st.title("Analytics")
st.write("Track instruction following across saved human judgments. This dashboard uses development evaluations; the held-out benchmark is reported separately.")
records = load_evaluations()
if records:
    filters = st.columns(2)
    models = sorted({item['generation_metadata']['model'] for item in records})
    selected_model = filters[0].selectbox("Model", ["All models", *models])
    if selected_model != "All models":
        records = [item for item in records if item['generation_metadata']['model'] == selected_model]
    protocols = sorted({item['generation_metadata']['protocol_id'] for item in records})
    protocol = filters[1].selectbox("Generation protocol", ["All protocols", *protocols])
    if protocol != "All protocols":
        records = [item for item in records if item['generation_metadata']['protocol_id'] == protocol]
metrics = summary_metrics(records)
columns = st.columns(3)
columns[0].metric("Evaluations", metrics['total'])
columns[1].metric("Average compliance", "Undefined" if metrics['average_compliance'] is None else f"{metrics['average_compliance']:.1f}%")
columns[2].metric("Acceptance rate", f"{metrics['acceptance_rate']:.1%}")
if not records:
    st.info("Save evaluations on Benchmark, Custom Task Builder, or Side-by-Side Comparison to populate the dashboard.")
    st.stop()
columns = st.columns(3)
for column, label, key in ((columns[0], "Baseline compliance", "baseline_compliance"), (columns[1], "Constraint-aware compliance", "improved_compliance")):
    column.metric(label, "Undefined" if metrics[key] is None else f"{metrics[key]:.1f}%")
columns[2].metric("Failed constraints per response", f"{metrics['average_failed']:.2f}")
st.write(f"**Most frequently violated type:** {metrics['most_violated_type']}")
st.caption(f"Compliance averages use {metrics['defined_compliance_count']} of {metrics['total']} responses. {metrics['not_applicable_count']} checks were marked Not Applicable; all-N/A responses have undefined compliance. Full pass requires every constraint to pass: {metrics['full_pass_count']} responses.")
st.info("Strategy averages can reflect different tasks, models, settings, or evaluators. They are descriptive, not a controlled improvement claim. Use matched held-out comparisons for the improvement experiment.")
frame = evaluation_frame(records)
checks = constraint_frame(records)
left, right = st.columns(2)
with left:
    st.subheader("Compliance by strategy")
    values = frame.groupby('generation_strategy')['compliance_score'].mean().dropna()
    if values.empty:
        st.info("No applicable compliance ratings to chart yet.")
    else:
        fig = Figure(figsize=(5.5, 3.8)); ax = fig.subplots()
        ax.bar(values.index, values.values, color=['#3468C0', '#238979'][:len(values)])
        ax.set_ylim(0, 100); ax.set_ylabel('Mean compliance (%)')
        fig.tight_layout(); st.pyplot(fig, width='stretch')
with right:
    st.subheader("Most common constraint violations")
    failed = checks.loc[checks['status'].eq('Fail'), 'kind'].value_counts()
    if failed.empty:
        st.info("No failed constraints in these evaluations.")
    else:
        fig = Figure(figsize=(6, max(3.8, len(failed) * 0.35))); ax = fig.subplots()
        ax.barh([CONSTRAINT_TYPES.get(kind, kind) for kind in failed.index], failed.values, color='#B97555')
        ax.invert_yaxis(); ax.set_xlabel('Failed human judgments'); ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        fig.tight_layout(); st.pyplot(fig, width='stretch')
left, right = st.columns(2)
with left:
    st.subheader("Acceptance rate")
    accepted = frame.groupby('generation_strategy')['accepted'].mean() * 100
    fig = Figure(figsize=(5.5, 3.8)); ax = fig.subplots()
    ax.bar(accepted.index, accepted.values, color='#3468C0'); ax.set_ylim(0, 100); ax.set_ylabel('Accepted responses (%)')
    fig.tight_layout(); st.pyplot(fig, width='stretch')
with right:
    st.subheader("Performance by constraint type")
    difficulty = constraint_difficulty(records).dropna(subset=['pass_rate'])
    if difficulty.empty:
        st.info("Rate at least one constraint Pass or Fail to see type-level performance.")
    else:
        fig = Figure(figsize=(6, max(3.8, len(difficulty) * 0.35))); ax = fig.subplots()
        ax.barh([CONSTRAINT_TYPES.get(kind, kind) for kind in difficulty['kind']], difficulty['pass_rate'] * 100, color='#238979')
        ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xlabel('Pass rate among applicable checks (%)')
        fig.tight_layout(); st.pyplot(fig, width='stretch')
st.subheader("Compliance over time")
trend = frame[['timestamp', 'generation_strategy', 'compliance_score']].dropna(subset=['compliance_score']).copy()
trend['timestamp'] = pd.to_datetime(trend['timestamp'], utc=True, errors='coerce')
trend = trend.dropna(subset=['timestamp']).sort_values('timestamp')
if trend['timestamp'].nunique() < 2:
    st.info("Save applicable evaluations at two different times to see a trend.")
else:
    fig = Figure(figsize=(10, 3.5)); ax = fig.subplots()
    for strategy, group in trend.groupby('generation_strategy'):
        grouped = group.groupby('timestamp')['compliance_score'].mean()
        ax.plot(grouped.index, grouped.values, marker='o', markersize=4, label=strategy)
    ax.set_ylim(0, 100); ax.set_ylabel('Compliance (%)'); ax.set_xlabel('Evaluation time (UTC)'); ax.legend()
    fig.autofmt_xdate(); fig.tight_layout(); st.pyplot(fig, width='stretch')
    st.caption("Equal timestamps are averaged. Changes in task mix can change the trend even if model behavior is unchanged.")
