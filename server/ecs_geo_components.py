from dataclasses import dataclass
import esper


# ---------------------------------------------------------------------------
# Components for GeoObjects and ClientRequests
# ---------------------------------------------------------------------------
@dataclass
class ID:
    id: str

@dataclass
class DisplayName:
    display_name: str

@dataclass
class IsUser:
    is_user: bool = True

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
class ClientRequestPayload:
    requester_id: str
    timestamp: str
    request_type: str = ""
    requested_action: str = ""

@dataclass
class AddObject:
    requester_id: str

@dataclass
class NewLocation:
    requester_id: str

@dataclass
class EditedObject:
    target_id: str
    target_path: str
    form_data: dict

@dataclass
class DeletedObject:
    target_id: str
    target_path: str

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


# ---------------------------------------------------------------------------
# Components for tracking zone interactions
# ---------------------------------------------------------------------------
@dataclass
class WithinZones:
    zone_ids: list

@dataclass
class EnteredZones:
    zone_ids: list

@dataclass
class ExitedZones:
    zone_ids: list

@dataclass
class GeoObjectDirty:
    '''Marker component to indicate that zone borders need to be uploaded to the db.'''
    is_dirty: bool = True


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


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


class ClientRequest:
    def __init__(self, id: str, geometry: dict, properties: dict) -> None:
        new_entity_id = esper.create_entity()
        self.entity_id = new_entity_id
        crp = properties.get("clientRequestPayload", {}) if isinstance(properties, dict) else {}
        esper.add_component(new_entity_id, ID(id=id))
        esper.add_component(new_entity_id, Geometry(coordinates=geometry.get("coordinates", [0,0])))
        esper.add_component(
            new_entity_id,
            ClientRequestPayload(
                requester_id=crp.get("requesterId", ""),
                timestamp=crp.get("timestamp", ""),
                request_type=crp.get("type", ""),
                requested_action=crp.get("requestedAction", ""),
            ),
        )

