"""Verify SDK requests and failure handling without network calls."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock
import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, AuthenticationError, BadRequestError, InternalServerError, NotFoundError, PermissionDeniedError, RateLimitError
from src import openai_client
from src.config import Settings
from src.generation import generation_metadata
from src.openai_client import GenerationError, generate_pair, generate_response


@pytest.fixture
def sdk(monkeypatch):
    constructor = MagicMock()
    client = constructor.return_value.__enter__.return_value
    client.responses.create.return_value = SimpleNamespace(status="completed", output=[], output_text="Please send Friday update.")
    monkeypatch.setattr(openai_client, "OpenAI", constructor)
    return constructor, client


def test_request_contains_task_and_every_constraint(sdk, task):
    constructor, client = sdk
    assert generate_response(task, settings=Settings(api_key="test-only"))
    arguments = client.responses.create.call_args.kwargs
    assert task["main_request"] in arguments["input"][0]["content"]
    for rule in task["constraints"]: assert rule["description"] in arguments["input"][0]["content"]
    assert arguments["store"] is False
    assert arguments["temperature"] == 0.7
    assert "conversation" not in arguments
    assert "previous_response_id" not in arguments
    constructor.assert_called_once_with(api_key="test-only", timeout=30.0, max_retries=1)


def test_pair_changes_only_instructions(sdk, task):
    _, client = sdk
    result = generate_pair(task, Settings(api_key="test-only", use_temperature=False))
    assert result["Baseline"] == result["Constraint-aware"]
    first, second = client.responses.create.call_args_list
    a, b = dict(first.kwargs), dict(second.kwargs)
    assert a.pop("instructions") != b.pop("instructions")
    assert a == b
    assert "temperature" not in a


@pytest.mark.parametrize("key", [None, "", "your_api_key_here"])
def test_missing_key_never_calls_sdk(sdk, task, key):
    with pytest.raises(GenerationError, match="OPENAI_API_KEY"):
        generate_response(task, settings=Settings(api_key=key))
    sdk[0].assert_not_called()


def test_invalid_task_never_calls_sdk(sdk, task):
    task["constraints"] = []
    with pytest.raises(GenerationError): generate_response(task, settings=Settings(api_key="test-only"))
    sdk[0].assert_not_called()


@pytest.mark.parametrize("kind,status,expected", [(AuthenticationError,401,"API key"), (RateLimitError,429,"limit"), (BadRequestError,400,"settings"), (NotFoundError,404,"unavailable"), (PermissionDeniedError,403,"unavailable"), (InternalServerError,500,"try again")])
def test_api_errors_are_friendly_and_do_not_expose_response(sdk, task, kind, status, expected):
    sdk[1].responses.create.side_effect = kind("unsafe test-key detail", response=httpx.Response(status, request=httpx.Request("POST", "https://api.openai.com/v1/responses")), body=None)
    with pytest.raises(GenerationError) as caught: generate_response(task, settings=Settings(api_key="test-key"))
    assert expected.casefold() in str(caught.value).casefold()
    assert "test-key" not in str(caught.value)


@pytest.mark.parametrize("kind", [APIConnectionError, APITimeoutError])
def test_transport_errors_are_handled(sdk, task, kind):
    sdk[1].responses.create.side_effect = kind(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    with pytest.raises(GenerationError): generate_response(task, settings=Settings(api_key="test"))


@pytest.mark.parametrize("response", [SimpleNamespace(status="incomplete", output=[], output_text="Partial"), SimpleNamespace(status="completed", output=[], output_text=" "), SimpleNamespace(status="completed", output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])], output_text="Refusal")])
def test_incomplete_empty_and_refused_outputs_are_rejected(sdk, task, response):
    sdk[1].responses.create.return_value = response
    with pytest.raises(GenerationError): generate_response(task, settings=Settings(api_key="test"))


def test_second_generation_failure_returns_no_partial_pair(monkeypatch, task):
    mock = MagicMock(side_effect=["First response", GenerationError("Failed second request")])
    monkeypatch.setattr(openai_client, "generate_response", mock)
    with pytest.raises(GenerationError): generate_pair(task, Settings(api_key="test"))
    assert mock.call_count == 2


def test_protocol_fingerprint_excludes_secret_and_tracks_generation_settings():
    settings = Settings(api_key="secret-a")
    original = generation_metadata(settings)
    assert original == generation_metadata(replace(settings, api_key="secret-b"))
    assert "secret" not in str(original)
    for change in ({"model": "another-model"}, {"temperature": 0.2}, {"use_temperature": False}, {"max_output_tokens": 2048}):
        assert generation_metadata(replace(settings, **change))["protocol_id"] != original["protocol_id"]
