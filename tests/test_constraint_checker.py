"""Boundary cases for transparent deterministic checks, not subjective scoring."""
import pytest
from src.constraint_checker import (
    AUTOMATIC_KINDS, CONSTRAINT_TYPES, check_bullet_count, check_constraint, check_constraints,
    check_exact_word_count, check_prohibited_phrase, check_required_phrase, check_sentence_limit,
    check_word_limit, count_sentences, count_words, validate_constraint,
)


@pytest.mark.parametrize("text,count", [("", 0), ("  ", 0), ("Hello, world!", 2), ("Don't re-use old_text.", 4), ("café naïve 中文", 3), ("!? --", 0), ("one\ntwo\tthree", 3)])
def test_word_count(text, count):
    assert count_words(text) == count


@pytest.mark.parametrize("text,count", [("", 0), ("One. Two! Three?", 3), ("One... Two?!", 2), ('"Hello!" Next fragment', 2), ("Value 3.5 works.", 1), ("Dr. Smith speaks.", 2), ("One\nline", 1)])
def test_sentence_count_conventions(text, count):
    assert count_sentences(text) == count


@pytest.mark.parametrize("text,phrase,present", [("Please send FRIDAY update", "Friday", True), ("concatenate", "cat", False), ("A stainless\nsteel bottle", "stainless steel", True), ("No excuses!", "!", True), ("No excuse", "!", False), ("cat-like", "cat", True)])
def test_phrase_matching(text, phrase, present):
    assert check_required_phrase(text, phrase) is present
    assert check_prohibited_phrase(text, phrase) is not present


def test_count_boundaries_and_bullet_convention():
    assert check_word_limit("one two", 2)
    assert not check_word_limit("one two three", 2)
    assert check_exact_word_count("one two", 2)
    assert not check_exact_word_count("one", 2)
    assert check_sentence_limit("One. Two.", 2)
    assert not check_sentence_limit("One. Two.", 1)
    assert check_bullet_count("- first\n  * second\n+ third\n• fourth\n continuation", 4)
    assert not check_bullet_count("1. first\n2. second", 2)


@pytest.mark.parametrize("kind,value,text,expected", [
    ("maximum_words", 2, "one two three", "Fail"), ("minimum_words", 2, "one two", "Pass"),
    ("exact_words", 2, "one", "Fail"), ("maximum_sentences", 1, "One. Two.", "Fail"),
    ("exact_sentences", 2, "One. Two.", "Pass"), ("exact_bullets", 2, "- A\n- B", "Pass"),
    ("required_phrase", "Friday", "Friday works.", "Pass"), ("prohibited_phrase", "Friday", "Friday works.", "Fail"),
])
def test_automatic_result_has_evidence(kind, value, text, expected):
    result = check_constraint(text, {"id": "c1", "kind": kind, "description": "Test rule", "value": value})
    assert result["status"] == expected
    assert result["method"] == "automatic"
    assert result["detail"]


@pytest.mark.parametrize("kind", sorted(set(CONSTRAINT_TYPES) - AUTOMATIC_KINDS))
def test_subjective_checks_require_humans(kind):
    assert check_constraint("Any response", {"id": "c1", "kind": kind, "description": "Review this requirement", "value": None})["status"] == "Human review"


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "3"])
def test_numeric_values_are_positive_integers(value):
    with pytest.raises(ValueError):
        validate_constraint({"id": "c1", "kind": "maximum_words", "description": "Limit", "value": value})


def test_bad_constraints_are_rejected(task):
    with pytest.raises(ValueError): check_required_phrase("text", " ")
    with pytest.raises(ValueError): check_constraints("response", [task["constraints"][0]] * 2)
    with pytest.raises(ValueError): check_constraints("response", "not a list")
