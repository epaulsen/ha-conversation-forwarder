"""Tests for the Conversation Forwarder config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.conversation_forwarder.const import CONF_URL, DEFAULT_NAME, DOMAIN

TEST_URL = "http://localhost:8080/conversation"


def _make_get_context_manager(*, side_effect=None):
    """Build a mock aiohttp GET async context manager."""
    mock_resp = MagicMock()
    if side_effect is not None:
        mock_resp.__aenter__ = AsyncMock(side_effect=side_effect)
    else:
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    return mock_resp


async def test_form_success(hass: HomeAssistant) -> None:
    """Test that the form is shown and a successful connection creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "custom_components.conversation_forwarder.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=_make_get_context_manager())
        mock_session_factory.return_value = mock_session

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: TEST_URL},
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == DEFAULT_NAME
    assert result2["data"] == {CONF_URL: TEST_URL}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test that a connection error shows the cannot_connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "custom_components.conversation_forwarder.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = MagicMock()
        mock_session.get = MagicMock(
            return_value=_make_get_context_manager(
                side_effect=aiohttp.ClientError("connection refused")
            )
        )
        mock_session_factory.return_value = mock_session

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: TEST_URL},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test that an unexpected error shows the unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "custom_components.conversation_forwarder.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session = MagicMock()
        mock_session.get = MagicMock(
            return_value=_make_get_context_manager(side_effect=Exception("unexpected"))
        )
        mock_session_factory.return_value = mock_session

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: TEST_URL},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
