"""Frozen prompting strategies and reproducible generation-setting fingerprints."""

import hashlib
import json

from src.config import Settings

PROTOCOL_VERSION = "constraintcheck-v1"
BASELINE = "Baseline"
IMPROVED = "Constraint-aware"
STRATEGIES = (BASELINE, IMPROVED)
BASELINE_INSTRUCTIONS = "Answer the user's request. Return only the requested response."
IMPROVED_INSTRUCTIONS = (
    "Satisfy every requirement in the user's request. Before answering, identify "
    "each explicit requirement, draft your answer, check the draft against every "
    "requirement, and revise any violation. Preserve supplied information and "
    "respect restrictions on length, wording, tone, audience, order, and format. "
    "Do not invent facts or commitments. Return only the final answer; do not "
    "mention or reveal your internal checklist."
)


def generation_metadata(settings: Settings) -> dict:
    """Fingerprint both strategies and settings, never credentials."""
    values = {
        "model": settings.model,
        "temperature": settings.temperature if settings.use_temperature else None,
        "max_output_tokens": settings.max_output_tokens,
    }
    protocol = {**values, "version": PROTOCOL_VERSION, "baseline": BASELINE_INSTRUCTIONS, "improved": IMPROVED_INSTRUCTIONS}
    digest = hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest()[:16]
    return {**values, "protocol_id": f"{PROTOCOL_VERSION}-{digest}"}


def strategy_instructions(strategy: str) -> str:
    if strategy not in STRATEGIES:
        raise ValueError("Choose Baseline or Constraint-aware.")
    return BASELINE_INSTRUCTIONS if strategy == BASELINE else IMPROVED_INSTRUCTIONS
