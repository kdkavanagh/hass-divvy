"""Config flow for Divvy integration."""
import logging
from homeassistant.core import callback

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ZONE
from homeassistant.helpers import selector

from . import CONF_STATION_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

import pybikes


class DivvyOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for Waze Travel Time."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize waze options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        
        if user_input is not None:
            if not user_input[CONF_ZONE] and not user_input[CONF_STATION_NAME]:
                raise Exception("Must specify at least one station or zone")

            return self.async_create_entry(
                title="Divvy Bikes",
                data={
                    CONF_STATION_NAME: user_input[CONF_STATION_NAME],
                    CONF_ZONE: user_input[CONF_ZONE],
                },
            )

        api = pybikes.get("divvy")
        await self.hass.async_add_executor_job(
            api.update,
        )
        if not api.stations:
            raise Exception("Failed to get any stations for divvy")

        errors = {}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    
                    vol.Optional(
                        CONF_STATION_NAME, default=self.config_entry.options.get(CONF_STATION_NAME, None)
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=sorted(x.name for x in api.stations),
                            multiple=True,

                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_ZONE, default=self.config_entry.options.get(CONF_ZONE, None)
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=CONF_ZONE, multiple=True)
                    ),
                }
            ),
            errors=errors,
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ):
        """Get the options flow for this handler."""
        return DivvyOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        return self.async_create_entry(
                title="Divvy Bikes",
                data={})
 #       """Handle the initial step."""
#
        # if user_input is not None:
        #     self._abort_if_unique_id_configured()
        #     if not user_input[CONF_ZONE] and not user_input[CONF_STATION_NAME]:
        #         raise Exception("Must specify at least one station or zone")

        #     return self.async_create_entry(
        #         title="Divvy Bikes",
        #         data={
        #             CONF_STATION_NAME: user_input[CONF_STATION_NAME],
        #             CONF_ZONE: user_input[CONF_ZONE],
        #         },
        #     )

        # api = pybikes.get("divvy")
        # await self.hass.async_add_executor_job(
        #     api.update,
        # )
        # if not api.stations:
        #     raise Exception("Failed to get any stations for divvy")

        # errors = {}
        # return self.async_show_form(
        #     step_id="user",
        #     data_schema=vol.Schema(
        #         {
                    
        #             vol.Optional(
        #                 CONF_STATION_NAME,
        #             ): selector.SelectSelector(
        #                 selector.SelectSelectorConfig(
        #                     options=sorted(x.name for x in api.stations),
        #                     multiple=True,
        #                     mode=selector.SelectSelectorMode.DROPDOWN,
        #                 )
        #             ),
        #             vol.Optional(
        #                 CONF_ZONE,
        #             ): selector.EntitySelector(
        #                 selector.EntitySelectorConfig(domain=CONF_ZONE, multiple=True)
        #             ),
        #         }
        #     ),
        #     errors=errors,
        # )
