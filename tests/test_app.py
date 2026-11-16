"""Exercise Streamlit workflows using mocked generation and temporary SQLite files."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import pytest
from streamlit.testing.v1 import AppTest
from src.database import get_comparisons, get_evaluations, save_comparison, save_evaluation
from src.generation import generation_metadata
from src.config import get_settings
from src.openai_client import GenerationError
from src.task_library import DEVELOPMENT_TASKS, HELD_OUT_TASKS

ROOT = Path(__file__).resolve().parents[1]
PAGES = [path.stem for path in sorted((ROOT / "pages").glob("*.py"))]


@pytest.fixture
def generation(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setattr("src.ui.generate_response", lambda *args: "Gravity pulls things toward Earth. A dropped ball falls down.")
    monkeypatch.setattr("src.ui.generate_pair", lambda *args: {"Baseline": "A baseline answer.", "Constraint-aware": "A requirement-aware answer."})


def page(name):
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    app.switch_page(f"pages/{name}.py").run()
    assert not app.exception
    return app


def element(items, label):
    return next(item for item in items if item.label == label)


def click(app, label):
    element(app.button, label).click().run()
    assert not app.exception


def review(app, draft):
    for rule in draft["task"]["constraints"]:
        app.radio(key=f"{draft['id']}_status_{rule['id']}").set_value("Pass")
        app.text_input(key=f"{draft['id']}_notes_{rule['id']}").set_value("Reviewed for this synthetic test.")
    app.radio(key=f"{draft['id']}_accepted").set_value("Yes")
    app.text_area(key=f"{draft['id']}_rationale").set_value("It satisfies the requested task.")
    app.run()
    assert not app.exception


@pytest.mark.parametrize("name", PAGES)
def test_all_pages_render_without_key_or_saved_data(name):
    app = page(name)
    for button in app.button:
        if button.label.startswith("Generate"):
            assert button.disabled


def test_single_evaluation_save_draft_navigation_and_dataset(generation):
    app = page("1_Benchmark")
    click(app, "Generate response")
    draft = app.session_state["benchmark_response"]["draft"]
    click(app, "Save evaluation")
    assert app.error
    assert get_evaluations() == []
    review(app, draft)
    app.switch_page("pages/11_Concepts.py").run()
    app.switch_page("pages/1_Benchmark.py").run()
    assert app.radio(key=f"{draft['id']}_status_c1").value == "Pass"
    assert app.text_area(key=f"{draft['id']}_rationale").value == "It satisfies the requested task."
    click(app, "Save evaluation")
    assert len(get_evaluations()) == 1
    assert element(app.button, "Save evaluation").disabled
    app.switch_page("pages/4_Dataset.py").run()
    assert not app.exception
    assert len(app.get("download_button")) == 1
    assert len(app.dataframe[0].value) == 1
    element(app.selectbox, "Acceptance").select("Rejected").run()
    assert app.dataframe[0].value.empty


def test_stale_task_blocks_save_and_failed_generation_keeps_old_draft(generation, monkeypatch):
    app = page("1_Benchmark")
    click(app, "Generate response")
    original = app.session_state["benchmark_response"]["draft"]["id"]
    app.selectbox(key="benchmark_task").select(DEVELOPMENT_TASKS[1]["id"]).run()
    assert element(app.button, "Save evaluation").disabled

    def fail(*args): raise GenerationError("Please try again later.")
    monkeypatch.setattr("src.ui.generate_response", fail)
    click(app, "Generate response")
    assert app.error
    assert app.session_state["benchmark_response"]["draft"]["id"] == original


def test_custom_builder_generates_consistent_constraints_and_preserves_draft(generation):
    app = page("2_Custom_Task")
    app.text_area(key="custom_request").set_value("Explain the water cycle.")
    app.number_input(key="custom_count").set_value(2).run()
    app.text_input(key="custom_rule_1_description").set_value("Use a friendly tone.").run()
    click(app, "Generate response")
    task = app.session_state["custom_response"]["draft"]["task"]
    assert task["constraints"][0]["value"] == 80
    assert task["constraints"][0]["description"] == "Use at most 80 words."
    app.switch_page("pages/11_Concepts.py").run()
    app.switch_page("pages/2_Custom_Task.py").run()
    assert app.text_input(key="custom_rule_1_description").value == "Use a friendly tone."
    assert app.text_area(key="custom_request").value == "Explain the water cycle."
    click(app, "Use this task in side-by-side comparison")
    assert element(app.radio, "Task source").value == "Custom task"
    # AppTest's next interaction needs its selected page synchronized after st.switch_page.
    app.switch_page("pages/3_Compare_Strategies.py")
    click(app, "Generate both strategies")
    assert app.session_state["development_pair"]["task"] == task


def test_comparison_saves_both_evaluations_and_preference(generation):
    app = page("3_Compare_Strategies")
    click(app, "Generate both strategies")
    current = app.session_state["development_pair"]
    click(app, "Save comparison and both evaluations")
    assert app.error
    assert get_evaluations() == []
    for draft in current["drafts"].values(): review(app, draft)
    app.radio(key=f"{current['id']}_preference").set_value("Constraint-aware").run()
    app.text_area(key=f"{current['id']}_rationale").set_value("Clearer response with all requirements.").run()
    click(app, "Save comparison and both evaluations")
    assert len(get_comparisons()) == 1
    assert len(get_evaluations()) == 2
    assert get_comparisons()[0]["preference"] == "Constraint-aware"


def test_heldout_pair_can_only_be_saved_once(generation):
    app = page("8_Held_Out_Test")
    click(app, "Generate both strategies")
    assert element(app.button, "Generate both strategies").disabled
    protocol = generation_metadata(get_settings())["protocol_id"]
    state_key = f"held_{HELD_OUT_TASKS[0]['id']}_{protocol}"
    current = app.session_state[state_key]
    for draft in current["drafts"].values(): review(app, draft)
    app.radio(key=f"{current['id']}_preference").set_value("Tie").run()
    app.text_area(key=f"{current['id']}_rationale").set_value("Both satisfy the task equally.").run()
    click(app, "Save comparison and both evaluations")
    assert len(get_comparisons(split="held_out")) == 1
    assert get_comparisons(split="development") == []
    reopened = page("8_Held_Out_Test")
    assert not reopened.button
    assert any("already saved" in item.value for item in reopened.success)
    assert any(item.value == "100%" for item in reopened.metric)


def test_recorded_development_reuse_blocks_heldout(generation, evaluation_factory):
    reused = deepcopy(HELD_OUT_TASKS[0])
    reused["split"] = "development"
    save_evaluation(evaluation_factory(supplied_task=reused))
    app = page("8_Held_Out_Test")
    assert not app.button
    assert any("already appears in development" in item.value for item in app.warning)


def test_populated_analytics_model_and_experiment_pages(comparison_factory):
    for task in DEVELOPMENT_TASKS[:8]: save_comparison(comparison_factory(task))
    save_comparison(comparison_factory(HELD_OUT_TASKS[0]))
    for name in ("5_Analytics", "6_Failure_Analysis", "7_Constraint_Difficulty", "9_Preference_Model", "12_Improvement_Experiment"):
        app = page(name)
        assert not app.exception
        assert app.dataframe or app.metric


def test_zero_reward_weights_are_handled():
    app = page("10_Reward_Hacking")
    for slider in app.slider: slider.set_value(0)
    app.run()
    assert not app.exception
    assert any("nonzero" in item.value for item in app.info)


def test_bad_database_is_a_friendly_message(tmp_path, monkeypatch):
    path = tmp_path / "invalid.db"
    path.write_text("not a database")
    monkeypatch.setenv("CONSTRAINTCHECK_DB_PATH", str(path))
    app = page("4_Dataset")
    assert app.error
