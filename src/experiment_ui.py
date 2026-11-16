"""A single explanation and chart for matched held-out results."""
import matplotlib.pyplot as plt
import streamlit as st
from src.experiments import experiment_summary


def show_experiment_results(records: list[dict]) -> None:
    st.caption(f"{len(records)} / 10 eligible matched tasks completed. Both strategies are judged on the same task set.")
    if not records:
        st.info("Save both evaluations and a preference on the Held-Out Benchmark page to start this experiment.")
        return
    frame = experiment_summary(records)
    st.dataframe(frame, hide_index=True, width="stretch")
    for column, row in zip(st.columns(2), frame.to_dict("records")):
        column.metric(f"{row['Strategy']} full-compliance rate", f"{row['Full-compliance rate']:.0%}")
    fig, ax = plt.subplots(figsize=(7, 3))
    values = frame["Average compliance (%)"]
    valid = values.notna()
    ax.bar(frame.loc[valid, "Strategy"], values[valid], color=["#64748B", "#2563EB"][:int(valid.sum())])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Average compliance (%)")
    ax.set_title("Completed matched tasks · Defined compliance only")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)
    for column, preference in zip(st.columns(3), ("Baseline", "Constraint-aware", "Tie")):
        count = sum(item["preference"] == preference for item in records)
        column.metric(f"{preference} preference rate", f"{count / len(records):.0%}")
    st.caption("Full compliance means every requirement passed; N/A prevents a full pass. Average compliance excludes all-N/A responses and reports coverage. Acceptance and preference rates include every completed pair, including ties. Small subjective samples do not establish general superiority.")
