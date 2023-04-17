# Divvy Station Tracker Home Assistant Component

A custom component which tracks available (e)bikes at divvy stations of interest.
Undocked, "free" bikes within a Home Assistant Zone may also be tracked.

This component leverages a modified version of the [pybikes](https://github.com/eskerda/pybikes) API to use Divvy's gbfs data

## Installation
Install via HACS or by deploying `custom_components/divvy_station_tracker` to your installation's `custom_components` directory

## Configuration
Configuration is supported via the UI by clicking "Configure" after installing the integration

Each "Station" entry will create four new sensor entities:

* "[Station-Name] Open Docks"
* "[Station-Name] Regular Bikes"
* "[Station-Name] E-Bikes"
* "[Station-Name] Scooters"

Each "zone" entry will create a single entity "Free bikes near [zone-name]", counting the number of available bikes in that zone (respecting the radius of the zone).  An additional attribute `free_bikes` containing a list of bikes sorted by distance to the center of the zone is added to the entity.