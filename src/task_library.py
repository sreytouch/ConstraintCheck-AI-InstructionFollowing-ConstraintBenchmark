"""Twenty development tasks and ten separate held-out tasks with explicit rules."""

from copy import deepcopy
import hashlib
import json

from src.constraint_checker import validate_constraint


def normalized_request(text: str) -> str:
    return " ".join(text.casefold().split())


def validate_task(task: dict) -> dict:
    """Validate task snapshots without guessing rules from free text."""
    fields = {"id", "name", "category", "main_request", "constraints", "split"}
    if not isinstance(task, dict) or set(task) != fields:
        raise ValueError("A task needs id, name, category, main_request, constraints, and split.")
    result = {}
    for field in ("id", "name", "category", "main_request"):
        if not isinstance(task[field], str) or not task[field].strip():
            raise ValueError(f"Enter a nonempty {field.replace('_', ' ')}.")
        result[field] = task[field].strip()
        if len(result[field]) > (20000 if field == "main_request" else 200):
            raise ValueError(f"The {field.replace('_', ' ')} is too long.")
    if task["split"] not in ("development", "held_out"):
        raise ValueError("Task split must be development or held_out.")
    if not isinstance(task["constraints"], list) or not 1 <= len(task["constraints"]) <= 20:
        raise ValueError("Provide between 1 and 20 constraints.")
    constraints = [validate_constraint(item) for item in task["constraints"]]
    if len({item["id"] for item in constraints}) != len(constraints):
        raise ValueError("Constraint IDs must be unique within a task.")
    if any(len(item["description"]) > 2000 for item in constraints):
        raise ValueError("Keep each constraint description under 2000 characters.")
    result.update(constraints=constraints, split=task["split"])
    return result


def task_fingerprint(task: dict) -> str:
    """Group equivalent task definitions even if renamed, relabeled, or reordered."""
    task = validate_task(task)
    constraints = [{"kind": item["kind"], "description": normalized_request(item["description"]), "value": normalized_request(item["value"]) if isinstance(item["value"], str) else item["value"]} for item in task["constraints"]]
    constraints.sort(key=lambda item: json.dumps(item, sort_keys=True))
    value = {"main_request": normalized_request(task["main_request"]), "constraints": constraints}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _task(number: int, name: str, category: str, request: str, rules: list[tuple], held_out: bool = False) -> dict:
    return validate_task({
        "id": f"{'heldout-v1' if held_out else 'practice'}-{number:02d}", "name": name,
        "category": category, "main_request": request, "split": "held_out" if held_out else "development",
        "constraints": [{"id": f"c{index}", "kind": rule[0], "description": rule[1], "value": rule[2] if len(rule) == 3 else None} for index, rule in enumerate(rules, 1)],
    })


DEVELOPMENT_TASKS = [
    _task(1, "Gravity for a child", "Education", "Explain gravity to a 7-year-old.", [
        ("maximum_sentences", "Use at most 3 sentences.", 3), ("prohibited_concept", "Avoid mathematical formulas."),
        ("required_concept", "Include one everyday example."), ("prohibited_phrase", "Do not use the phrase spacetime.", "spacetime"),
        ("audience", "Use language suitable for a 7-year-old.")]),
    _task(2, "Professional reminder", "Workplace", "Write a professional reminder email asking a colleague to send the project summary.", [
        ("maximum_words", "Use at most 100 words.", 100), ("tone", "Use a polite tone."),
        ("required_phrase", "Mention Friday as the deadline.", "Friday"), ("prohibited_concept", "Do not apologize."),
        ("required_concept", "Include a clear call to action to send the summary."), ("format", "Use an email structure.")]),
    _task(3, "Faithful summary", "Summarization", "Summarize this paragraph: The town tested evening bus service for six weeks. Ridership was highest on Fridays, while weekday demand remained modest. The council concluded that Friday evening service should continue, but other evenings need more study.", [
        ("exact_sentences", "Use exactly 2 sentences.", 2), ("maximum_words", "Use at most 60 words.", 60),
        ("information_preservation", "Preserve the conclusion: continue Friday service; study other evenings."), ("no_unsupported_information", "Do not introduce new facts.")]),
    _task(4, "Machine learning explained", "Education", "Explain machine learning.", [
        ("audience", "Write for a high-school student."), ("maximum_words", "Use at most 120 words.", 120),
        ("required_concept", "Include one analogy."), ("prohibited_phrase", "Avoid the term neural network.", "neural network"),
        ("prohibited_phrase", "Avoid the term gradient descent.", "gradient descent")]),
    _task(5, "Non-accusatory rewrite", "Writing", "Rewrite: You failed to send the document.", [
        ("tone", "Use a professional tone."), ("tone", "Be non-accusatory."),
        ("information_preservation", "Preserve the meaning that the document has not been sent."), ("maximum_words", "Use under 25 words (at most 24).", 24)]),
    _task(6, "Three study tips", "Education", "Give three study tips.", [
        ("exact_bullets", "Use exactly 3 bullet points marked with a dash, asterisk, plus, or bullet symbol.", 3),
        ("format", "Keep each bullet under 20 words."), ("prohibited_concept", "Use no motivational clichés."),
        ("required_concept", "Include one tip about scheduling.")]),
    _task(7, "Reusable bottle description", "Product writing", "Write a product description for a reusable water bottle.", [
        ("maximum_words", "Use at most 70 words.", 70), ("required_phrase", "Mention stainless steel.", "stainless steel"),
        ("prohibited_concept", "Do not claim health benefits."), ("prohibited_phrase", "Use no exclamation marks.", "!"), ("tone", "Use a professional tone.")]),
    _task(8, "Exercise overview", "Education", "Explain why exercise is useful in general terms.", [
        ("prohibited_concept", "Do not provide medical advice."), ("maximum_words", "Use at most 80 words.", 80),
        ("required_concept", "Mention both physical activity and mood."), ("prohibited_concept", "Include no numerical claims.")]),
    _task(9, "Ten-word invitation", "Writing", "Invite classmates to a weekend board-game afternoon without specifying an exact time or venue.", [
        ("exact_words", "Use exactly 10 words.", 10), ("tone", "Use a welcoming tone."), ("no_unsupported_information", "Do not invent a time or venue.")]),
    _task(10, "Recycling explanation", "Education", "Explain how to prepare paper for recycling.", [
        ("minimum_words", "Use at least 40 words.", 40), ("maximum_words", "Use at most 70 words.", 70),
        ("required_concept", "Mention keeping paper dry."), ("audience", "Use simple language for a general audience.")]),
    _task(11, "JSON schedule", "Structured output", "Create a JSON object describing a workshop titled Sketching with duration_minutes 45 and location Room 4.", [
        ("format", "Return only a valid JSON object, without Markdown fences or commentary."),
        ("information_preservation", "Use the exact supplied title, duration, and location."),
        ("format", "Use exactly the keys title, duration_minutes, and location."), ("no_unsupported_information", "Do not add other facts.")]),
    _task(12, "Ordered troubleshooting", "Instructions", "Explain how to handle a printer that has stopped printing.", [
        ("exact_bullets", "Use exactly 3 bullet points.", 3), ("output_ordering", "Discuss checking power first, paper second, and the print queue third."),
        ("maximum_words", "Use at most 60 words.", 60), ("prohibited_concept", "Do not recommend opening electrical components.")]),
    _task(13, "Library notice", "Public information", "Announce that the library will close at 4 pm on Monday for staff training and reopen Tuesday morning.", [
        ("exact_sentences", "Use exactly 2 sentences.", 2), ("required_phrase", "Include the phrase staff training.", "staff training"),
        ("information_preservation", "Preserve both the closure time/day and reopening day."), ("tone", "Use a courteous tone.")]),
    _task(14, "Respectful refusal", "Workplace", "Decline a request to attend a meeting because you have a prior commitment.", [
        ("maximum_words", "Use at most 35 words.", 35), ("prohibited_phrase", "Do not use the word sorry.", "sorry"),
        ("tone", "Remain respectful."), ("no_unsupported_information", "Do not invent details about the prior commitment.")]),
    _task(15, "Two-column comparison", "Structured output", "Compare taking notes on paper with taking notes digitally.", [
        ("format", "Use a Markdown table with exactly two columns named Paper and Digital."),
        ("format", "Include exactly two body rows after the header and separator."), ("tone", "Present both options neutrally."),
        ("maximum_words", "Use at most 60 words.", 60)]),
    _task(16, "Preserve uncertainty", "Writing", "Rewrite clearly: The parcel may arrive Wednesday, but weather could delay it.", [
        ("information_preservation", "Preserve uncertainty and the possibility of weather delays."),
        ("required_phrase", "Include Wednesday.", "Wednesday"), ("maximum_sentences", "Use at most 1 sentence.", 1),
        ("no_unsupported_information", "Do not promise a delivery date.")]),
    _task(17, "Audience and ending", "Education", "Explain evaporation to a 9-year-old.", [
        ("audience", "Use language suitable for a 9-year-old."), ("required_concept", "Include a wet-clothes example."),
        ("format", "End with a question."), ("maximum_words", "Use at most 65 words.", 65)]),
    _task(18, "Meeting update", "Workplace", "Write an update using only these facts: the design is approved, testing starts next week, and the release date is undecided.", [
        ("required_phrase", "Include the phrase next week.", "next week"), ("no_unsupported_information", "Use only the supplied facts."),
        ("information_preservation", "Retain the undecided release date."), ("output_ordering", "Mention design approval before testing, and release timing last.")]),
    _task(19, "Concise headline", "Writing", "Write a headline for a community garden opening this spring.", [
        ("exact_words", "Use exactly 7 words.", 7), ("required_phrase", "Include community garden.", "community garden"),
        ("prohibited_phrase", "Do not use amazing.", "amazing"), ("tone", "Use a factual tone.")]),
    _task(20, "Checklist for a walk", "Instructions", "Create a short checklist for preparing for a neighborhood walk.", [
        ("exact_bullets", "Use exactly 4 bullet points.", 4), ("required_concept", "Include checking the weather."),
        ("maximum_words", "Use at most 45 words.", 45), ("prohibited_concept", "Do not make medical recommendations.")]),
]

HELD_OUT_TASKS = [
    _task(1, "Museum photography notice", "Public information", "Tell museum visitors that photography without flash is allowed, but flash photography is prohibited.", [
        ("maximum_words", "Use at most 35 words.", 35), ("information_preservation", "Preserve the distinction between flash and non-flash photography."),
        ("tone", "Use a friendly tone."), ("prohibited_phrase", "Do not use the word banned.", "banned")], True),
    _task(2, "Maintenance announcement", "Workplace", "Announce that the dashboard will be read-only from 14:00 to 14:30 UTC for a reporting update.", [
        ("maximum_words", "Use under 40 words (at most 39).", 39), ("required_phrase", "Include UTC.", "UTC"),
        ("information_preservation", "Keep both times and explain read-only access, not complete unavailability."), ("no_unsupported_information", "Do not invent additional service impacts.")], True),
    _task(3, "Tentative venue", "Writing", "Rewrite: The event might take place in Hall B if the booking is confirmed.", [
        ("exact_sentences", "Use exactly 1 sentence.", 1), ("required_phrase", "Include Hall B.", "Hall B"),
        ("information_preservation", "Preserve both uncertainty and the booking condition."), ("maximum_words", "Use at most 20 words.", 20)], True),
    _task(4, "Composting for beginners", "Education", "Explain composting to someone who has never gardened.", [
        ("audience", "Use beginner-friendly language."), ("exact_bullets", "Use exactly 3 bullet points.", 3),
        ("required_concept", "Mention fruit or vegetable scraps."), ("prohibited_phrase", "Do not use microorganisms.", "microorganisms"),
        ("maximum_words", "Use at most 70 words.", 70)], True),
    _task(5, "Volunteer confirmation", "Structured output", "Return information for a volunteer shift: Saturday, start 10 am, role registration.", [
        ("format", "Return only a valid JSON object without Markdown fences."), ("format", "Use exactly the string-valued keys day, start, and role."),
        ("information_preservation", "Preserve all three supplied values."), ("no_unsupported_information", "Do not add a location or other facts.")], True),
    _task(6, "Repair queue update", "Workplace", "Tell a customer that their repair is being assessed and that an estimate will be sent after assessment.", [
        ("tone", "Use an empathetic professional tone."), ("maximum_words", "Use at most 55 words.", 55),
        ("output_ordering", "Mention assessment before the estimate."), ("no_unsupported_information", "Do not promise a price, repair outcome, or date."),
        ("prohibited_phrase", "Do not use guaranteed.", "guaranteed")], True),
    _task(7, "Twelve-word announcement", "Writing", "Announce a free public poetry reading without inventing a place or date.", [
        ("exact_words", "Use exactly 12 words.", 12), ("required_phrase", "Include poetry reading.", "poetry reading"),
        ("required_concept", "State that attendance is free."), ("no_unsupported_information", "Do not invent a place or date.")], True),
    _task(8, "Coral explanation", "Education", "Explain what a coral reef is to a middle-school student.", [
        ("minimum_words", "Use at least 35 words.", 35), ("maximum_words", "Use at most 60 words.", 60),
        ("audience", "Write for a middle-school student."), ("required_concept", "Mention that reefs provide a home for sea life."),
        ("prohibited_phrase", "Avoid the word ecosystem.", "ecosystem")], True),
    _task(9, "Survey conclusion", "Summarization", "Summarize: A neighborhood survey received 120 replies. Most respondents preferred Saturday cleanup sessions. Organizers decided to try Saturday mornings for one month before choosing a permanent schedule.", [
        ("exact_sentences", "Use exactly 2 sentences.", 2), ("maximum_words", "Use at most 45 words.", 45),
        ("information_preservation", "Preserve the temporary one-month trial and undecided permanent schedule."), ("no_unsupported_information", "Do not add facts or imply all residents agreed.")], True),
    _task(10, "Audio setup sequence", "Instructions", "Give basic steps for preparing a microphone for a video call.", [
        ("exact_bullets", "Use exactly 3 bullet points.", 3), ("output_ordering", "Connect the microphone first, select it in settings second, and test it third."),
        ("maximum_words", "Use at most 50 words.", 50), ("tone", "Use a calm, direct tone."),
        ("prohibited_concept", "Do not suggest changing hardware internals.")], True),
]


def get_task(task_id: str, held_out: bool = False) -> dict:
    """Regular retrieval never exposes the held-out library by default."""
    for task in HELD_OUT_TASKS if held_out else DEVELOPMENT_TASKS:
        if task["id"] == task_id:
            return deepcopy(task)
    raise ValueError("Task not found in the selected task library.")
