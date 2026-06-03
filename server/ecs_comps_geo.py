import esper
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Components for GeoObjects
# ---------------------------------------------------------------------------
@dataclass
class ID:
    id: str

@dataclass
class DisplayName:
    display_name: str

@dataclass
class Appearance:
    color: str
    shape: str
    radius: int
    visible_to: list

@dataclass
class Geometry:
    coordinates: list
    type: str = "Point"  # Assuming all geo objects are points for simplicity; can be extended to support other types

@dataclass
class Stat:
    name: str
    value: int
    min_value: int = 0
    max_value: int = 100

@dataclass
class Stats:
    items: dict = None

@dataclass
class Traits:
    traits: list

@dataclass
class Messages:
    messages: list

@dataclass
class ZoneEntryLog:
    '''Add a zone id to the log whenever an entity enters another, keep the list for historical reference.'''
    zone_ids: list

@dataclass
class ZoneExitLog:
    '''Add a zone id to the log whenever an entity exits another, keep the list for historical reference.'''
    zone_ids: list


## Entity
class GeoObject:
    def __init__(self, id: str, geometry: dict, properties: dict) -> None:
        new_entity_id = esper.create_entity()
        self.entity_id = new_entity_id
        appearance = properties.get("appearance", {}) if isinstance(properties, dict) else {}
        nested_data = properties.get("data", {}) if isinstance(properties, dict) else {}
        esper.add_component(new_entity_id, ID(id=id))
        esper.add_component(new_entity_id, Geometry(coordinates=geometry.get("coordinates", [0,0])))
        esper.add_component(
            new_entity_id,
            DisplayName(
                display_name=properties.get("displayName", "") if isinstance(properties, dict) else "",
            ),
        )
        esper.add_component(
            new_entity_id,
            Appearance(
                color=appearance.get("color", ""),
                shape=appearance.get("shape", ""),
                radius=appearance.get("radius", 0),
                visible_to=appearance.get("visibleTo", []),
            ),
        )


## Temporary components for tracking zone interactions
@dataclass
class WithinZones:
    zone_ids: list

@dataclass
class EnteredZones:
    '''Add a zone id to the list whenever an entity enters another, but only for one processor tick.'''
    zone_ids: list

@dataclass
class ExitedZones:
    '''Add a zone id to the list whenever an entity exits another, but only for one processor tick.'''
    zone_ids: list

@dataclass
class GeoObjectDirty:
    '''Marker component to indicate that zone borders need to be uploaded to the db.'''
    is_dirty: bool = True


