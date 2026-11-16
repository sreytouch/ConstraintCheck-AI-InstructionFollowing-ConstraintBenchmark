"""Independent, bounded OpenAI Responses requests with safe interface errors."""

from openai import (
    APIConnectionError, APIError, APITimeoutError, AuthenticationError,
    BadRequestError, NotFoundError, OpenAI, PermissionDeniedError, RateLimitError,
)

from src.config import Settings, get_settings
from src.generation import BASELINE, IMPROVED, strategy_instructions
from src.task_library import validate_task


class GenerationError(RuntimeError):
    """A generation problem whose message can be displayed to the user."""


def generate_response(task: dict, strategy: str = BASELINE, settings: Settings | None = None) -> str:
    """Generate one independent response containing all task requirements."""
    try:
        task = validate_task(task)
        instructions = strategy_instructions(strategy)
    except ValueError as error:
        raise GenerationError(str(error)) from error
    settings = settings or get_settings()
    if not settings.api_key or settings.api_key == "your_api_key_here":
        raise GenerationError("Copy .env.example to .env and set OPENAI_API_KEY to your own key before generating.")
    request = task["main_request"] + "\n\nRequirements:\n" + "\n".join(
        f"{index}. {constraint['description']}" for index, constraint in enumerate(task["constraints"], 1)
    )
    arguments = {
        "model": settings.model, "instructions": instructions,
        "input": [{"role": "user", "content": request}],
        "max_output_tokens": settings.max_output_tokens, "store": False,
    }
    if settings.use_temperature:
        arguments["temperature"] = settings.temperature
    try:
        with OpenAI(api_key=settings.api_key, timeout=30.0, max_retries=1) as client:
            response = client.responses.create(**arguments)
        if response.status != "completed":
            raise GenerationError("The response did not finish. Try shorter input or increase OPENAI_MAX_OUTPUT_TOKENS. No partial answer was saved.")
        if any(getattr(part, "type", None) == "refusal" for item in response.output for part in getattr(item, "content", [])):
            raise GenerationError("The model declined this request. Try another task; no evaluation was created.")
        answer = response.output_text.strip()
        if not answer:
            raise GenerationError("The model returned no response text. Try another task or model.")
        return answer
    except AuthenticationError as error:
        raise GenerationError("OpenAI rejected the API key. Check OPENAI_API_KEY in .env.") from error
    except RateLimitError as error:
        raise GenerationError("OpenAI's rate or usage limit was reached. Check API billing and limits, then try later.") from error
    except APITimeoutError as error:
        raise GenerationError("OpenAI took too long to respond. Please try again.") from error
    except APIConnectionError as error:
        raise GenerationError("Could not connect to OpenAI. Check your connection and try again.") from error
    except (PermissionDeniedError, NotFoundError) as error:
        raise GenerationError("The configured model is unavailable to this API key. Check OPENAI_MODEL and model access.") from error
    except BadRequestError as error:
        raise GenerationError("OpenAI rejected the generation settings. Check OPENAI_MODEL and the token limit. If this model does not support temperature, set OPENAI_USE_TEMPERATURE=false.") from error
    except APIError as error:
        raise GenerationError("OpenAI could not complete the request. Please try again later.") from error


def generate_pair(task: dict, settings: Settings | None = None) -> dict[str, str]:
    """Use identical task/model/settings for two independent calls; never return a partial pair."""
    settings = settings or get_settings()
    baseline = generate_response(task, BASELINE, settings)
    improved = generate_response(task, IMPROVED, settings)
    return {BASELINE: baseline, IMPROVED: improved}
