"""Deterministic constraint checks, kept separate from human judgments.

Counting conventions are intentionally simple and inspectable:
* Words are Unicode letter/digit runs; internal apostrophes and hyphens stay in
  one token ("don't", "well-being"). Underscores and other punctuation separate
  tokens; punctuation alone is not a word. This is not a linguistic tokenizer.
* Sentences end at a run of .?! followed by whitespace or end-of-text, optionally
  with closing quotes/brackets. A final unpunctuated fragment counts as one.
  Decimal points without following whitespace do not split. Abbreviations such
  as "Dr. Smith" can overcount; newline-only lists can undercount.
* Phrases match literally, case-insensitively, with whitespace collapsed. If a
  phrase begins/ends with a word character, that edge must be a whole-word edge.
  Inflections, synonyms, punctuation variants, and semantic equivalence do not
  match automatically. Punctuation-only phrases such as "!" use literal matching.
* Bullets are nonempty lines starting with -, *, +, or • followed by whitespace.
  Indentation is allowed. Numbered lists and unmarked continuation lines are not
  bullets. Nested marked lines count too; marker-like code lines can overcount.

These checks never infer subjective quality. Human review remains authoritative,
including correcting a counting heuristic with a note in the evaluation UI.
"""

from collections.abc import Mapping, Sequence
from numbers import Integral
import re
from typing import Any

CONSTRAINT_TYPES = {
    "maximum_words": "Maximum word count",
    "minimum_words": "Minimum word count",
    "exact_words": "Exact word count",
    "maximum_sentences": "Maximum sentence count",
    "exact_sentences": "Exact sentence count",
    "exact_bullets": "Exact bullet count",
    "required_phrase": "Required phrase",
    "prohibited_phrase": "Prohibited phrase",
    "required_concept": "Required concept",
    "prohibited_concept": "Prohibited concept",
    "tone": "Tone",
    "audience": "Audience",
    "format": "Format / output structure",
    "information_preservation": "Information preservation",
    "no_unsupported_information": "No unsupported information",
    "output_ordering": "Output ordering",
}
NUMERIC_KINDS = frozenset({
    "maximum_words", "minimum_words", "exact_words", "maximum_sentences",
    "exact_sentences", "exact_bullets",
})
AUTOMATIC_KINDS = NUMERIC_KINDS | {"required_phrase", "prohibited_phrase"}
_WORD_PATTERN = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", flags=re.UNICODE)
_SENTENCE_BOUNDARY = re.compile(r"[.!?]+[\"'”’\)\]]*(?:\s+|$)")
_BULLET_PATTERN = re.compile(r"^\s*[-*+•][ \t]+\S.*$", flags=re.MULTILINE)


def _text(value: Any, label: str = "Response") -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    return value


def _positive_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise ValueError("A count constraint must use a positive integer.")
    return int(value)


def _phrase(value: Any) -> str:
    value = _text(value, "Phrase")
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("A phrase constraint must contain a nonempty phrase.")
    return normalized


def validate_constraint(constraint: Mapping[str, Any]) -> dict[str, Any]:
    """Return a clean constraint definition or raise an actionable ValueError."""
    if not isinstance(constraint, Mapping):
        raise ValueError("Each constraint must be an object with an ID, kind, and description.")
    required = {"id", "kind", "description", "value"}
    if set(constraint) != required:
        raise ValueError("Each constraint needs exactly id, kind, description, and value.")
    identifier = _text(constraint["id"], "Constraint ID").strip()
    description = _text(constraint["description"], "Constraint description").strip()
    if not identifier or not description:
        raise ValueError("Every constraint needs a nonempty ID and description.")
    kind = constraint["kind"]
    if not isinstance(kind, str) or kind not in CONSTRAINT_TYPES:
        raise ValueError("Choose a supported constraint type.")
    value = constraint["value"]
    if kind in NUMERIC_KINDS:
        value = _positive_count(value)
    elif kind in {"required_phrase", "prohibited_phrase"}:
        value = _phrase(value)
    elif value is not None:
        raise ValueError("Human-reviewed constraint types must use value=None; describe the requirement in words.")
    return {"id": identifier, "kind": kind, "description": description, "value": value}


def count_words(response: str) -> int:
    """Count letter/digit tokens, retaining internal apostrophes and hyphens."""
    return len(_WORD_PATTERN.findall(_text(response)))


def count_sentences(response: str) -> int:
    """Count punctuation-delimited sentences and a final nonempty fragment."""
    parts = _SENTENCE_BOUNDARY.split(_text(response).strip())
    return sum(bool(_WORD_PATTERN.search(part)) for part in parts)


def check_required_phrase(response: str, phrase: str) -> bool:
    """Check a literal phrase using case folding, whitespace, and word edges."""
    text = " ".join(_text(response).casefold().split())
    phrase = _phrase(phrase).casefold()
    start = r"(?<!\w)" if re.match(r"\w", phrase[0]) else ""
    end = r"(?!\w)" if re.match(r"\w", phrase[-1]) else ""
    return re.search(start + re.escape(phrase) + end, text) is not None


def check_prohibited_phrase(response: str, phrase: str) -> bool:
    """Pass when the prohibited literal phrase is absent."""
    return not check_required_phrase(response, phrase)


def check_bullet_count(response: str, expected: int) -> bool:
    """Check the exact number of nonempty -, *, +, or • bullet-marker lines."""
    return len(_BULLET_PATTERN.findall(_text(response))) == _positive_count(expected)


def check_word_limit(response: str, maximum: int) -> bool:
    """Check an inclusive maximum word count (under N means maximum N-1)."""
    return count_words(response) <= _positive_count(maximum)


def check_sentence_limit(response: str, maximum: int) -> bool:
    """Check an inclusive maximum under the documented sentence convention."""
    return count_sentences(response) <= _positive_count(maximum)


def check_exact_word_count(response: str, expected: int) -> bool:
    """Check an exact word count under the documented tokenizer."""
    return count_words(response) == _positive_count(expected)


def check_constraint(response: str, constraint: Mapping[str, Any]) -> dict[str, str]:
    """Return an automatic Pass/Fail or an explicitly unscored Human review."""
    response = _text(response)
    constraint = validate_constraint(constraint)
    kind, value = constraint["kind"], constraint["value"]
    result = {"constraint_id": constraint["id"], "status": "Human review", "method": "human", "detail": ""}
    if kind not in AUTOMATIC_KINDS:
        result["detail"] = f"Human judgment required: {constraint['description']}"
        return result
    if kind in {"maximum_words", "minimum_words", "exact_words"}:
        count = count_words(response)
        passed = count <= value if kind == "maximum_words" else count >= value if kind == "minimum_words" else count == value
        relation = {"maximum_words": "at most", "minimum_words": "at least", "exact_words": "exactly"}[kind]
        detail = f"Counted {count} words; requires {relation} {value}. Uses the documented word-token convention."
    elif kind in {"maximum_sentences", "exact_sentences"}:
        count = count_sentences(response)
        passed = count <= value if kind == "maximum_sentences" else count == value
        relation = "at most" if kind == "maximum_sentences" else "exactly"
        detail = f"Counted {count} sentences; requires {relation} {value}. Abbreviations and list fragments may need human correction."
    elif kind == "exact_bullets":
        count = len(_BULLET_PATTERN.findall(response))
        passed = count == value
        detail = f"Counted {count} bullet-marker lines; requires exactly {value}. Numbered lists are not counted as bullets."
    else:
        present = check_required_phrase(response, value)
        passed = present if kind == "required_phrase" else not present
        detail = f"Literal phrase {value!r} is {'present' if present else 'absent'} (case-insensitive, normalized whitespace, whole-word edges)."
    result.update(status="Pass" if passed else "Fail", method="automatic", detail=detail)
    return result


def check_constraints(response: str, constraints: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Check every constraint once, rejecting duplicate IDs or malformed lists."""
    _text(response)
    if not isinstance(constraints, Sequence) or isinstance(constraints, (str, bytes)):
        raise ValueError("Constraints must be a list of constraint objects.")
    validated = [validate_constraint(item) for item in constraints]
    identifiers = [item["id"] for item in validated]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Constraint IDs must be unique within a task.")
    return [check_constraint(response, item) for item in validated]
