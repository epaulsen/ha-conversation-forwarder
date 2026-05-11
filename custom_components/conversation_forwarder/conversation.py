"""Conversation agent platform for Conversation Forwarder."""
from __future__ import annotations

import aiohttp

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_URL, DEFAULT_NAME, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Conversation Forwarder agent from a config entry."""
    agent = ConversationForwarderEntity(config_entry)
    async_add_entities([agent])


class ConversationForwarderEntity(conversation.ConversationEntity):
    """Conversation agent that forwards requests to a remote HTTP endpoint."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the forwarder entity."""
        self._entry = entry
        self._url: str = entry.data[CONF_URL]
        self._attr_unique_id = entry.entry_id
        self._attr_name = DEFAULT_NAME

    @property
    def supported_languages(self) -> list[str] | str:
        """Return all languages as supported."""
        return "*"

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Forward the user message to the configured HTTP endpoint and return the reply."""
        session = async_get_clientsession(self.hass)
        response_text: str

        payload = {
            "text": user_input.text,
            "language": user_input.language,
            "conversation_id": user_input.conversation_id,
        }

        try:
            async with session.post(
                self._url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                response_text = data.get("text", "")
        except aiohttp.ClientResponseError as err:
            response_text = f"HTTP error {err.status}: {err.message}"
        except aiohttp.ClientError as err:
            response_text = f"Connection error: {err}"
        except Exception as err:  # noqa: BLE001
            response_text = f"Unexpected error: {err}"

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(response_text)

        return conversation.ConversationResult(
            response=response,
            conversation_id=user_input.conversation_id,
        )
