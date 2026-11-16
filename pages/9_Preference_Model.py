"""Toy preference learning with independent task groups kept out of fitting."""

import streamlit as st

from src.preference_model import build_preference_pairs, predict_preference, train_preference_model, training_requirement
from src.ui import load_comparisons, show_response

st.title('Preference model demo')
st.info('This is an educational preference-model approximation, not a production RLHF reward model. It does not train or change the language model.')
st.write('Logistic regression learns from differences in human compliance and quality scores. It requires scored answers; it cannot judge new response text on its own.')
comparisons = load_comparisons()
if comparisons:
    protocols = sorted({item['protocol_id'] for item in comparisons})
    selected_protocol = st.selectbox('Generation protocol', ['All development protocols', *protocols])
    if selected_protocol != 'All development protocols':
        comparisons = [item for item in comparisons if item['protocol_id'] == selected_protocol]
with st.expander('How the training and test sets are made', expanded=True):
    st.markdown(
        '1. Exclude ties, held-out benchmark judgments, and pairs with undefined compliance.\n'
        '2. Group comparisons by a fingerprint of the **request and constraints**, so repeated or renamed tasks stay together.\n'
        '3. Reserve about 25% of task groups for testing before creating training rows.\n'
        '4. Use baseline-minus-constraint-aware score differences; reverse each pair to supply the opposite label.\n'
        '5. Fit on training groups and calculate accuracy on untouched groups.'
    )
    st.caption('Mirrored rows are not extra human judgments. This internal model holdout is separate from the app’s fixed held-out benchmark, which is never used for preference-model fitting.')
try:
    reason = training_requirement(comparisons)
    if reason:
        st.warning(reason); st.stop()
    result = train_preference_model(comparisons)
except ValueError as error:
    st.error(str(error)); st.stop()
columns = st.columns(4)
columns[0].metric('Training comparisons', result.training_count)
columns[1].metric('Training task groups', len(result.training_groups))
columns[2].metric('Test task groups', len(result.held_out_groups))
columns[3].metric('Held-out pair accuracy', f'{result.accuracy:.1%}')
st.caption(f'{result.training_count} original training comparisons become {result.augmented_training_count} mirrored rows; {result.held_out_count} test comparisons become {result.augmented_held_out_count} rows. Always picking either position scores 50% on mirrored rows. This is a small educational estimate, not a robust benchmark.')
st.caption('The model stays fitted only on training groups. Similar tasks can still share patterns across groups; grouping prevents exact task-identity leakage, not every form of dataset similarity.')
st.subheader('Coefficients')
st.dataframe(result.coefficients, hide_index=True, width='stretch')
st.write('All features are scaled to a zero-to-one range before taking differences: compliance ÷ 100, ratings ÷ 5, and failed constraints ÷ total constraints. A positive coefficient favors a larger feature value on the candidate being considered; a negative coefficient goes the other way. For failure fraction, a negative weight usually aligns with preferring fewer failures.')
st.caption('Correlated ratings make individual coefficients hard to interpret. These are associations, not causal importance. No intercept is fitted, so swapping response order reverses estimated preference. N/A exclusions can make compliance and failure fraction measure different things.')
valid_ids = set(build_preference_pairs(comparisons)['comparison_id'])
lookup = {item['comparison_id']: item for item in comparisons if item['comparison_id'] in valid_ids}
st.subheader('Inspect a saved prediction')
selected = st.selectbox('Comparison', list(lookup), format_func=lambda key: f"{lookup[key]['task_name']} · {lookup[key]['timestamp'][:16]} · {key[:8]}")
item = lookup[selected]
prediction = predict_preference(result, item)
st.write(f"**{prediction['membership']}** · Human preference: **{item['preference']}**")
if abs(prediction['probability_baseline'] - 0.5) < 1e-9:
    st.write('The model estimates 50% for each strategy: no preference advantage.')
else:
    st.write(f"Predicted preference: **{prediction['preference']}**")
columns = st.columns(2)
columns[0].metric('Estimated P(Baseline preferred)', f"{prediction['probability_baseline']:.1%}")
columns[1].metric('Estimated P(Constraint-aware preferred)', f"{prediction['probability_improved']:.1%}")
st.caption('Probabilities are uncalibrated model estimates, not certainty that an answer is correct. A training comparison is not an independent test.')
with st.expander('Inspect the scored responses'):
    left, right = st.columns(2)
    with left:
        st.subheader('Baseline'); show_response(item['baseline'])
    with right:
        st.subheader('Constraint-aware'); show_response(item['improved'])
    st.write('**Preference rationale**'); st.text(item['rationale'])
