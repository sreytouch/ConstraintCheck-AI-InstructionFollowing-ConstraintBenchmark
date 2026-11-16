"""Task groups, reversed pairs, and benchmark separation prevent easy leakage."""
from copy import deepcopy
import numpy as np
import pytest
from src.preference_model import FEATURES, build_preference_pairs, train_preference_model, training_requirement
from src.task_library import DEVELOPMENT_TASKS, HELD_OUT_TASKS


def test_pair_features_and_mirrors(comparison_factory):
    pair = comparison_factory()
    rows = build_preference_pairs([pair], mirror=True)
    assert len(rows) == 2
    assert list(rows["preferred_left"]) == [0, 1]
    np.testing.assert_allclose(rows.iloc[0][FEATURES].astype(float), -rows.iloc[1][FEATURES].astype(float))


def test_ties_undefined_and_heldout_are_excluded(comparison_factory):
    tied = comparison_factory(preference="Tie")
    heldout = comparison_factory(HELD_OUT_TASKS[0])
    undefined = comparison_factory()
    undefined["baseline"]["compliance_score"] = None
    assert build_preference_pairs([tied, heldout, undefined]).empty


def test_repeated_task_names_do_not_create_new_training_groups(comparison_factory, task):
    pairs = []
    for index in range(8):
        renamed = deepcopy(task)
        renamed["name"], renamed["id"] = str(index), str(index)
        pairs.append(comparison_factory(renamed))
    assert "1 distinct tasks" in training_requirement(pairs)
    with pytest.raises(ValueError): train_preference_model(pairs)


def test_training_and_test_groups_and_mirrors_stay_separate(comparison_factory):
    pairs = [comparison_factory(task) for task in DEVELOPMENT_TASKS[:8]]
    pairs += [comparison_factory(DEVELOPMENT_TASKS[0])]
    result = train_preference_model(pairs)
    assert set(result.training_groups).isdisjoint(result.held_out_groups)
    assert set(result.training_ids).isdisjoint(result.held_out_ids)
    assert result.training_count + result.held_out_count == 9
    assert result.augmented_training_count == result.training_count*2
    assert 0 <= result.accuracy <= 1
    assert len(result.coefficients) == 6
    assert result.model.fit_intercept is False
    duplicate_ids = {pairs[0]["comparison_id"], pairs[-1]["comparison_id"]}
    assert duplicate_ids <= set(result.training_ids) or duplicate_ids <= set(result.held_out_ids)


def test_duplicate_comparison_id_is_rejected(comparison_factory):
    pair = comparison_factory()
    with pytest.raises(ValueError): build_preference_pairs([pair, pair])
