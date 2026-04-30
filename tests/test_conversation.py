"""Tests for the Conversation Forwarder conversation agent."""
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.components.conversation import ConversationInput, ConversationResult
from homeassistant.core import HomeAssistant, Context
from homeassistant.helpers import intent

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.conversation_forwarder.const import CONF_URL, DOMAIN
from custom_components.conversation_forwarder.conversation import (
    ConversationForwarderEntity,
)

TEST_URL = "http://localhost:8080/conversation"


def _make_entity(hass: HomeAssistant) -> ConversationForwarderEntity:
    """Create a ConversationForwarderEntity with a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: TEST_URL},
        title="Conversation Forwarder",
    )
    entity = ConversationForwarderEntity(entry)
    entity.hass = hass
    return entity


def _make_user_input(
    text: str = "Hello!",
    language: str = "en",
    conversation_id: str | None = None,
) -> ConversationInput:
    """Create a ConversationInput for testing."""
    return ConversationInput(
        text=text,
        context=Context(),
        conversation_id=conversation_id,
        device_id=None,
        language=language,
    )


def _make_post_context_manager(response_text: str) -> MagicMock:
    """Build a mock aiohttp POST async context manager returning JSON."""
    mock_resp = MagicMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = AsyncMock(return_value={"text": response_text})
    return mock_resp


async def test_supported_languages(hass: HomeAssistant) -> None:
    """Test that the entity reports all languages as supported."""
    entity = _make_entity(hass)
    assert entity.supported_languages == "*"


async def test_conversation_forward_success(hass: HomeAssistant) -> None:
    """Test that a user message is forwarded and the reply is returned."""
    entity = _make_entity(hass)

    with patch(
        "custom_components.conversation_forwarder.conversation.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = MagicMock()
        mock_session.post = MagicMock(
            return_value=_make_post_context_manager("Hello from the server!")
        )
        mock_session_factory.return_value = mock_session

        result = await entity.async_process(_make_user_input("Hello!"))

    assert isinstance(result, ConversationResult)
    assert result.response.speech["plain"]["speech"] == "Hello from the server!"


async def test_conversation_forward_connection_error(hass: HomeAssistant) -> None:
    """Test that a connection error returns a helpful error message."""
    entity = _make_entity(hass)

    mock_resp = MagicMock()
    mock_resp.__aenter__ = AsyncMock(
        side_effect=aiohttp.ClientError("connection refused")
    )
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "custom_components.conversation_forwarder.conversation.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session_factory.return_value = mock_session

        result = await entity.async_process(_make_user_input("Hello!"))

    speech = result.response.speech["plain"]["speech"]
    assert "Connection error" in speech


async def test_conversation_forward_http_error(hass: HomeAssistant) -> None:
    """Test that an HTTP error status returns a helpful error message."""
    entity = _make_entity(hass)

    mock_resp = MagicMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_resp.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=500,
            message="Internal Server Error",
        )
    )

    with patch(
        "custom_components.conversation_forwarder.conversation.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session_factory.return_value = mock_session

        result = await entity.async_process(_make_user_input("Hello!"))

    speech = result.response.speech["plain"]["speech"]
    assert "HTTP error 500" in speech


async def test_conversation_preserves_conversation_id(hass: HomeAssistant) -> None:
    """Test that the conversation_id is passed through correctly."""
    entity = _make_entity(hass)

    with patch(
        "custom_components.conversation_forwarder.conversation.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = MagicMock()
        mock_session.post = MagicMock(
            return_value=_make_post_context_manager("Reply text")
        )
        mock_session_factory.return_value = mock_session

        result = await entity.async_process(
            _make_user_input("Hello!", conversation_id="my-convo-id")
        )

    assert result.conversation_id == "my-convo-id"

    call_kwargs = mock_session.post.call_args
    sent_payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
    assert sent_payload["conversation_id"] == "my-convo-id"
    assert sent_payload["text"] == "Hello!"


async def test_conversation_unexpected_error(hass: HomeAssistant) -> None:
    """Test that an unexpected exception returns an error message."""
    entity = _make_entity(hass)

    mock_resp = MagicMock()
    mock_resp.__aenter__ = AsyncMock(side_effect=RuntimeError("boom"))
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "custom_components.conversation_forwarder.conversation.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session_factory.return_value = mock_session

        result = await entity.async_process(_make_user_input("Hello!"))

    speech = result.response.speech["plain"]["speech"]
    assert "Unexpected error" in speech
