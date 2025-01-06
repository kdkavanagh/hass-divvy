import asyncio
import logging
from datetime import timedelta

import async_timeout
import pybikes
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ZONE, SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


DOMAIN = "divvy_station_tracker"

PLATFORMS = [Platform.SENSOR]

CONF_COORDINATOR = "coord"
CONF_STATION_NAME = "station_name"


class BikeCoordinator(DataUpdateCoordinator):

    def __init__(self, hass):
        super().__init__(
            hass,
            _LOGGER,
            name="divvy_bikes",
            update_interval=timedelta(seconds=10),
        )
        self.divvy = pybikes.get("divvy")

    async def _async_update_data(self):
        async with async_timeout.timeout(10):
            await self.hass.async_add_executor_job(self.divvy.update)
        return {x.name: x for x in self.divvy.stations}


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    hass.data.setdefault(DOMAIN, {})
    entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    coordinator = BikeCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()
    entry_data[CONF_COORDINATOR] = coordinator
    if entry.options:
        config = entry.options
        entry_data[CONF_STATION_NAME] = config[CONF_STATION_NAME]
        entry_data[CONF_ZONE] = config[CONF_ZONE]

    async def _handle_reload(service):
        """Handle reload service call."""
        _LOGGER.info("Service %s.reload called: reloading integration", DOMAIN)

        current_entries = hass.config_entries.async_entries(DOMAIN)

        reload_tasks = [
            hass.config_entries.async_reload(entry.entry_id)
            for entry in current_entries
        ]

        await asyncio.gather(*reload_tasks)

    hass.helpers.service.async_register_admin_service(
        DOMAIN,
        SERVICE_RELOAD,
        _handle_reload,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
