"""Plain-language concepts connected to the actual benchmark workflow."""
import streamlit as st

st.title("Concepts")
st.write("Use these terms to explain what the benchmark measures and what it does not.")
concepts = {
    "Prompts": "The text sent to a model. Here it combines the main request, every constraint, and the selected strategy's instructions.",
    "Requests": "The main thing the user wants done, such as explaining gravity. Passing length rules alone does not mean the request was answered.",
    "Constraints": "Conditions on an acceptable answer: a word limit, required phrase, tone, audience, or output order. Each becomes an individual judgment in this app.",
    "Instruction following": "Satisfying the whole request and its requirements. A correct answer can still fail when it ignores format, audience, or a restriction.",
    "Evaluation rubric": "A shared set of judging rules. This benchmark combines Pass/Fail/N/A constraint judgments with 1–5 correctness, relevance, clarity, and overall quality ratings.",
    "Human feedback": "People's assessments of a response. Your judgments remain separate from automatic checker output, with notes explaining overrides.",
    "Preference data": "Comparisons saying which of two responses is better, with ties and reasons. The app stores each preference alongside both full evaluations.",
    "Reward signal": "A numerical proxy for desired behavior. Compliance can be a signal, but it can miss correctness and the importance of particular constraints.",
    "Reward model": "A learned predictor of human judgments. This app's logistic classifier uses differences in existing human ratings; it does not read responses or automatically judge new text.",
    "Reward hacking": "Improving a proxy score without improving the real task. The interactive example rewards technical detail even when a child-friendly length-limited answer was requested.",
    "Held-out evaluation": "Testing on examples not used to design or tune the strategy. The ten separate tasks are excluded from development analytics and preference-model training; exposure and reuse can still compromise them.",
    "Hill climbing": "Repeatedly making a small change and keeping it when a metric improves. Reusing the same test examples for every change can overfit that test.",
    "Iterative improvement": "Collect feedback, inspect failures, make a targeted change, and evaluate again. Here the example change is a fixed constraint-aware prompt, not automatic training.",
    "RLHF": "Reinforcement learning from human feedback: preferences can help train a reward model that guides optimization of model behavior. This project demonstrates feedback and evaluation concepts but runs no PPO or language-model weight updates.",
}
for title, explanation in concepts.items():
    with st.expander(title, expanded=True):
        st.write(explanation)
st.info("Compliance is passed / applicable constraints. N/A is excluded from this denominator; all-N/A gives no defined score. A full pass requires every constraint to pass. Report coverage and quality alongside compliance to avoid misleading conclusions.")
