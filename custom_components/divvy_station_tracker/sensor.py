"""Support for ComEd Hourly Pricing data."""

from __future__ import annotations

import enum
import logging
from operator import itemgetter

import pybikes
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor.const import STATE_CLASS_MEASUREMENT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MANUFACTURER,
    ATTR_NAME,
    CONF_ZONE,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.location import distance

from . import CONF_COORDINATOR, CONF_STATION_NAME, DOMAIN, BikeCoordinator

_LOGGER = logging.getLogger(__name__)


class _MetaType(enum.Enum):
    FREE = 0
    REGULAR_BIKE = 1
    EBIKE = 2
    SCOOTER = 3

    def extract(self, station: pybikes.BikeShareStation):
        if self == _MetaType.FREE:
            return int(station.free)
        if self == _MetaType.REGULAR_BIKE:
            return int(station.bikes) - _MetaType.EBIKE.extract(station)
        if self == _MetaType.SCOOTER and station.extra.get("has_scooters", False):
            return int(station.extra["scooters"])
        if self == _MetaType.EBIKE and station.extra.get("has_ebikes", False):
            return int(station.extra["ebikes"])

        return 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""

    entry_data = hass.data[DOMAIN][entry.entry_id]

    coordinator = entry_data[CONF_COORDINATOR]

    entities: list[SensorEntity] = []
    for station_name in (desired_stations := entry_data.get(CONF_STATION_NAME, [])):
        if station_name not in coordinator.data:
            _LOGGER.error(f"Divvy Could not find station named {station_name}")
            continue

        _LOGGER.info(f"Setting up divvy tracker for station {station_name}")
        device = DeviceInfo(
            identifiers={(DOMAIN, station_name)},
            **{
                ATTR_MANUFACTURER: "Divvy",
                ATTR_NAME: station_name,
            },
        )
        entities.append(
            BikeStationMetadata(
                f"{station_name} Open Docks",
                coordinator,
                station_name,
                _MetaType.FREE,
                device,
            )
        )
        entities.append(
            BikeStationMetadata(
                f"{station_name} Regular Bikes",
                coordinator,
                station_name,
                _MetaType.REGULAR_BIKE,
                device,
            )
        )
        entities.append(
            BikeStationMetadata(
                f"{station_name} E-Bikes",
                coordinator,
                station_name,
                _MetaType.EBIKE,
                device,
            )
        )
        entities.append(
            BikeStationMetadata(
                f"{station_name} Scooters",
                coordinator,
                station_name,
                _MetaType.SCOOTER,
                device,
            )
        )

    for zone_id in (desired_zones := entry_data.get(CONF_ZONE, [])):
        registry = er.async_get(hass)
        er.async_validate_entity_ids(registry, [zone_id])
        zone_name = hass.states.get(zone_id).name
        _LOGGER.info(f"Setting up free bikes near zone {zone_name} {zone_id}")
        entities.append(
            NearbyFreeBikes(f"Free bikes near {zone_name}", coordinator, zone_id)
        )

    ent_reg = er.async_get(hass)
    remove_entities = set()
    remove_devs = set()
    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if not any(x in ent.unique_id for x in desired_stations) and not any(
            x in ent.unique_id for x in desired_zones
        ):
            remove_entities.add(ent.entity_id)
            if ent.device_id:
                remove_devs.add(ent.device_id)

    if remove_entities:
        _LOGGER.info(f"Removing {len(remove_entities)} stale divvy entities")
        for entity_id in remove_entities:
            _LOGGER.info(f"Removing entity: {entity_id}")
            ent_reg.async_remove(entity_id)

    desired_device_ids = {}
    for x in entities:
        if x.device_info:
            desired_device_ids.update(x.device_info["identifiers"])

    dev_reg = dr.async_get(hass)
    for ent in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if not any(x in desired_device_ids for x in ent.identifiers):

            _LOGGER.info(f"Removing stale divvy device: {ent.id} {ent.identifiers}")
            remove_devs.add(ent.id)

    if remove_devs:
        _LOGGER.info(f"Removing {len(remove_devs)} stale divvy devices")
        for dev_id in remove_devs:
            _LOGGER.info(f"Removing device: {dev_id}")
            dev_reg.async_remove_device(dev_id)

    _LOGGER.info(f"Adding {len(entities)} divvy entities")
    async_add_entities(entities, True)


class NearbyFreeBikes(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        name: str,
        coordinator: BikeCoordinator,
        zone_id: str,
    ):
        """Initialize the select."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{DOMAIN}_free_near_{zone_id}"
        self._attr_suggested_display_precision = 0
        self._attr_name = name
        self._attr_extra_state_attributes = {}
        self._attr_state_class = STATE_CLASS_MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def async_state_changed_listener(event: Event) -> None:
            """Handle child updates."""
            self.async_set_context(event.context)
            self.async_defer_or_update_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._zone_id], async_state_changed_listener
            )
        )

        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not (zone := self.hass.states.get(self._zone_id)):
            _LOGGER.warning(f"Missing state info for zone {self._zone_id}")
            return

        station_lat = zone.attributes["latitude"]
        station_long = zone.attributes["longitude"]
        radius = zone.attributes["radius"]
        nearby: list[tuple[float, dict]] = []
        for bike in self.coordinator.divvy.free_bikes:
            bike_lat = bike.get("lat", 0)
            bike_long = bike.get("long", 0)
            dist = distance(station_lat, station_long, bike_lat, bike_long)
            if dist <= radius:
                obj = {
                    "latitude:": bike_lat,
                    "longitude": bike_long,
                    "distance_meters": dist,
                    "type": bike["type"],
                }
                nearby.append((dist, obj))

        nearby.sort(key=itemgetter(0))
        self._attr_extra_state_attributes["free_bikes"] = nearby
        self._attr_native_value = len(nearby)
        self.async_write_ha_state()


class BikeStationMetadata(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        name: str,
        coordinator: BikeCoordinator,
        station_name: str,
        metadata_key: _MetaType,
        device: DeviceInfo,
    ):
        """Initialize the select."""
        super().__init__(coordinator)
        self._station_name = station_name
        self._meta_key = metadata_key
        self._attr_unique_id = f"{DOMAIN}_{self._station_name}_{metadata_key}"
        self._attr_suggested_display_precision = 0
        self._attr_name = name
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._device = device

    @property
    def device_info(self) -> DeviceInfo:
        return self._device

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        station = self.coordinator.data.get(self._station_name, None)
        if not station:
            raise Exception(f"Missing station {self._station_name}")
        self._attr_native_value = self._meta_key.extract(station)
        self.async_write_ha_state()
