"""Unit tests for the local emergentintegrations compatibility shim.

The shim replaces Emergent's private package (not on PyPI) with the same
import paths backed by public SDKs (litellm / stripe). These tests verify
the interface contract server.py relies on — no network calls are made.
"""
import inspect
import os

import pytest

from emergentintegrations.llm.chat import (
    LLM_TIMEOUT_SECONDS,
    LlmChat,
    StreamDone,
    TextDelta,
    UserMessage,
    is_llm_configured,
    resolve_api_key,
)
from emergentintegrations.payments.stripe.checkout import (
    CheckoutSessionRequest,
    StripeCheckout,
)


@pytest.fixture(autouse=True)
def clean_llm_env(monkeypatch):
    for var in ("OPENAI_API_KEY", "EMERGENT_LLM_KEY", "STRIPE_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_resolve_api_key_prefers_openai_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("EMERGENT_LLM_KEY", "emergent-key")
    assert resolve_api_key("passed-key") == "sk-openai"


def test_resolve_api_key_falls_back_to_passed_then_emergent(monkeypatch):
    assert resolve_api_key("passed-key") == "passed-key"
    monkeypatch.setenv("EMERGENT_LLM_KEY", "emergent-key")
    assert resolve_api_key("") == "emergent-key"


def test_resolve_api_key_raises_when_nothing_set():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        resolve_api_key(None)


def test_is_llm_configured(monkeypatch):
    assert is_llm_configured() is False
    monkeypatch.setenv("EMERGENT_LLM_KEY", "legacy-key")
    assert is_llm_configured() is True
    monkeypatch.setenv("OPENAI_API_KEY", "sk-new")
    assert is_llm_configured() is True


def test_llm_chat_with_model_chains():
    chat = LlmChat(api_key="k", session_id="s", system_message="sys")
    assert chat.with_model("openai", "gpt-4o") is chat
    assert chat._litellm_model() == "gpt-4o"


def test_message_dataclasses():
    assert UserMessage(text="hi").text == "hi"
    assert TextDelta(content="x").content == "x"
    assert isinstance(StreamDone(), StreamDone)


def test_stream_message_is_async_generator():
    chat = LlmChat(api_key="k")
    assert inspect.isasyncgenfunction(chat.stream_message)


@pytest.mark.asyncio
async def test_send_message_fails_fast_without_key():
    chat = LlmChat(api_key="")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await chat.send_message(UserMessage(text="hello"))


class _FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()
        self.delta = type("D", (), {"content": content})()


class _FakeResponse:
    def __init__(self, content="ok"):
        self.choices = [_FakeChoice(content)]


@pytest.mark.asyncio
async def test_send_message_passes_timeout(monkeypatch):
    import emergentintegrations.llm.chat as chat_mod

    seen = {}

    async def fake_acompletion(**kwargs):
        seen.update(kwargs)
        return _FakeResponse("timed reply")

    monkeypatch.setattr(chat_mod.litellm, "acompletion", fake_acompletion)
    chat = LlmChat(api_key="k")
    assert await chat.send_message(UserMessage(text="hi")) == "timed reply"
    assert seen["timeout"] == LLM_TIMEOUT_SECONDS == 120.0


@pytest.mark.asyncio
async def test_stream_message_passes_timeout(monkeypatch):
    import emergentintegrations.llm.chat as chat_mod

    seen = {}

    async def fake_stream(**kwargs):
        seen.update(kwargs)
        yield _FakeResponse("chunk")

    async def fake_acompletion(**kwargs):
        return fake_stream(**kwargs)

    monkeypatch.setattr(chat_mod.litellm, "acompletion", fake_acompletion)
    chat = LlmChat(api_key="k")
    events = [ev async for ev in chat.stream_message(UserMessage(text="hi"))]
    assert seen["timeout"] == LLM_TIMEOUT_SECONDS == 120.0
    assert any(isinstance(ev, TextDelta) and ev.content == "chunk" for ev in events)
    assert isinstance(events[-1], StreamDone)
    assert events[-1].usage is None  # provider supplied none


@pytest.mark.asyncio
async def test_stream_message_captures_usage(monkeypatch):
    import emergentintegrations.llm.chat as chat_mod

    class _Usage:
        prompt_tokens = 7
        completion_tokens = 3
        total_tokens = 10

    usage_chunk = _FakeResponse("")
    usage_chunk.usage = _Usage()
    usage_chunk.choices = []

    async def fake_stream(**kwargs):
        assert kwargs.get("stream_options") == {"include_usage": True}
        yield _FakeResponse("chunk")
        yield usage_chunk

    async def fake_acompletion(**kwargs):
        return fake_stream(**kwargs)

    monkeypatch.setattr(chat_mod.litellm, "acompletion", fake_acompletion)
    chat = LlmChat(api_key="k")
    events = [ev async for ev in chat.stream_message(UserMessage(text="hi"))]
    assert isinstance(events[-1], StreamDone)
    assert events[-1].usage == {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}


def test_checkout_request_defaults():
    req = CheckoutSessionRequest(amount=2900)
    assert req.amount == 2900
    assert req.currency == "usd"
    assert req.metadata == {}


def test_stripe_checkout_keeps_interface():
    sc = StripeCheckout(api_key="", webhook_url="https://x/hook")
    assert sc.webhook_url == "https://x/hook"
    assert inspect.iscoroutinefunction(sc.create_checkout_session)
    assert inspect.iscoroutinefunction(sc.get_checkout_status)


@pytest.mark.asyncio
async def test_stripe_calls_fail_fast_without_key():
    sc = StripeCheckout(api_key="")
    with pytest.raises(RuntimeError, match="STRIPE_API_KEY"):
        await sc.create_checkout_session(CheckoutSessionRequest(amount=100))
    with pytest.raises(RuntimeError, match="STRIPE_API_KEY"):
        await sc.get_checkout_status("cs_test_123")
