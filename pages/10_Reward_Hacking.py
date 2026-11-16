"""An interactive example of a reward that misses the user's real objective."""
import pandas as pd
import streamlit as st
from src.constraint_checker import count_words

RESPONSE_A = """Gravity is a fundamental interaction associated with the presence of mass and energy. In classical mechanics, it is described as an attractive force acting between objects, with strength depending on their masses and separation. Newton's account helps explain falling objects, planetary motion, and many observations. A more comprehensive description comes from general relativity, where matter and energy influence the geometry of spacetime and freely moving objects follow paths through that geometry. These paths can appear curved when viewed from another frame of reference. The acceleration experienced near Earth's surface is approximately constant over small changes in height, although local conditions and altitude produce variations. Gravity also helps bind moons to planets and planets to stars. Orbital motion combines forward movement with continual gravitational deflection, rather than requiring an object to remain motionless above another. On larger scales, gravitational interactions contribute to the formation and evolution of galaxies and other astronomical structures. These descriptions apply at different levels of approximation and should not be confused with the everyday feeling of weight, which also involves support forces. Thus, explaining gravity thoroughly requires distinguishing forces, motion, reference frames, and the mathematical models used to represent physical relationships across different settings and observational scales."""
RESPONSE_B = """Gravity is a pull that brings things toward Earth. It keeps your feet on the ground. When you drop a ball, gravity pulls it down. The same pull helps keep the Moon moving around Earth instead of floating far away."""

st.title("Reward Hacking")
st.write('Request: “Explain gravity to a child in under 50 words.”')
for column, label, response in zip(st.columns(2), ("Response A · Scientific detail", "Response B · Child-friendly"), (RESPONSE_A, RESPONSE_B)):
    with column.container(border=True):
        st.markdown(f"**{label}**")
        st.text(response)
        count = count_words(response)
        st.caption(f"{count} words · Length requirement: {'Pass' if count < 50 else 'Fail'}")
st.write("Suppose a reward strongly favors technical detail. Response A can earn that reward while failing both the length limit and the intended audience. Higher reward does not automatically mean better task completion.")
st.caption("The scores below are hypothetical teaching values, not measured human judgments or automated truth assessments.")
criteria = {"Technical detail": (5, 2), "Instruction following": (1, 5), "Length compliance": (1, 5), "Audience fit": (1, 5), "Correctness": (4, 4)}
weights = {}
for criterion in criteria:
    weights[criterion] = st.slider(f"Weight · {criterion}", 0, 5, 5 if criterion == "Technical detail" else 0)
total = sum(weights.values())
if not total:
    st.info("Choose at least one nonzero weight to calculate a reward.")
else:
    rewards = [sum(weights[key] * values[index] for key, values in criteria.items()) / total for index in (0, 1)]
    for column, label, reward in zip(st.columns(2), ("Response A reward", "Response B reward"), rewards):
        column.metric(label, f"{reward:.2f} / 5")
    st.write("The reward favors " + ("neither response; they tie." if abs(rewards[0] - rewards[1]) < 1e-9 else "Response A." if rewards[0] > rewards[1] else "Response B."))
st.dataframe(pd.DataFrame([{"Criterion": key, "A (hypothetical)": values[0], "B (hypothetical)": values[1]} for key, values in criteria.items()]), hide_index=True)
st.info("Reward hacking does not require conscious cheating. Optimizing an incomplete proxy can increase its score while moving away from the actual goal. This example illustrates the risk; it does not prove that either response was produced by a reward-optimizing training process.")
st.write("A stronger evaluation includes instruction following, length, audience, and correctness. Keep the individual checks visible so a favorable average cannot hide a critical failed requirement.")
