"""Config flow for RTL-SDR Radio integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class RTLSDRRadioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RTL-SDR Radio."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Test connection to the API
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"http://{host}:{port}/api/health"
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            # Create unique ID based on host
                            await self.async_set_unique_id(
                                f"rtlsdr_radio_{host}_{port}"
                            )
                            self._abort_if_unique_id_configured()

                            return self.async_create_entry(
                                title=f"RTL-SDR Radio ({host})",
                                data=user_input,
                            )
                        else:
                            errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
