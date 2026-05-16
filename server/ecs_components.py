from dataclasses import dataclass
import esper


# ---------------------------------------------------------------------------
# Components for GeoObjects and ClientRequests
# ---------------------------------------------------------------------------
@dataclass
class ID:
    id: str

@dataclass
class MetaData:
    name: str
    type: str
    description: str

@dataclass
class IsUser:
    is_user: bool = True

@dataclass
class IsZone:
    is_zone: bool = True

@dataclass
class Appearance:
    color: str
    shape: str
    radius: int

@dataclass
class Geometry:
    coordinates: list
    type: str = "Point"  # Assuming all geo objects are points for simplicity; can be extended to support other types

@dataclass
class ClientRequestProperties:
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

class EditedObject:
    def __init__(self, target_id: str, target_path: str, form_data: dict) -> None:
        self.target_id = target_id
        self.target_path = target_path
        self.form_data = form_data if isinstance(form_data, dict) else {}

@dataclass
class DeletedObject:
    target_id: str
    target_path: str

@dataclass
class Stat:
    name: str
    type: str
    value: int
    min_value: int = 0
    max_value: int = 100

class Stats:
    def __init__(self, items: dict | None = None) -> None:
        self.items = items if isinstance(items, dict) else {}

@dataclass
class Status:
    name: str
    type: str
    strength: int
    time_until_expire: int = 5

class Statuses:
    def __init__(self, items: dict | None = None) -> None:
        self.items = items if isinstance(items, dict) else {}


# ---------------------------------------------------------------------------
# Components for constructive events
# ---------------------------------------------------------------------------
'''
Seeker looks for matching entities and attached a trigger component to them.
Trigger components check for matching properties and if they match, they fire a Targetted search.
Valid targets have a result component attached to them.
Result components are then processed to apply their effects and then removed.
'''
@dataclass
class Seeker:
    '''
    if ALL of these are true for an entity then attach a trigger to it, AND condition
    multiple seekers can be built to create an OR condition instead of an AND condition
    '''
    seeker_id: str

    seeking_ids: list = []
    seeking_types: list = []
    seeking_statuses: list = [] 

    trigger_ids_to_assign: list = []  # IDs of the triggers to assign to suspect entity when a match is found

@dataclass
class Trigger:
    '''
    ALL trigger conditions must be met for this to launch a targetted search, AND condition
    multiple triggers can be assigned to make an OR condition instead of an AND condition
    '''
    trigger_id: str

    is_within_ids: list = None
    is_not_within_ids: list = None
    is_within_types: list = None
    is_not_within_types: list = None
    just_entered_zone_ids: list = None
    just_exited_zone_ids: list = None
    just_entered_zone_types: list = None
    just_exited_zone_types: list = None
    has_statuses: list = None
    does_not_have_statuses: list = None
    stat_id_is_above: dict | None = None
    stat_id_is_below: dict | None = None
    stat_type_is_above: dict | None = None
    stat_type_is_below: dict | None = None

    target_ids_to_fire: list = []  # IDs of the targets to launch looking for matching entities to when the trigger conditions are met

@dataclass
class Target:
    '''
    if ALL are true, attach a Result component to the entity
    attaching multiple Target components that attach the same result_id to an entity can create an OR condition instead of an AND condition
    '''
    target_id: str

    target_ids: list = []
    target_types: list = []
    target_statuses: list = []
    target_stat_id_is_above: dict | None = None
    target_stat_id_is_below: dict | None = None
    target_stat_type_is_above: dict | None = None
    target_stat_type_is_below: dict | None = None

    result_id_to_assign: str | None = None  # ID of the result to assign to the entity when a match is found

@dataclass
class Result:
    '''
    do all of the following to the entity with this ID when the trigger conditions are met
    '''
    result_id: str

    set_visibility: bool | None = None
    toggle_visibility: bool = False
    change_color_to: str | None = None
    change_radius_to: int | None = None
    
    add_statuses: list | None = None
    remove_statuses: list | None = None
    toggle_statuses: list | None = None

    set_stats_to_values: dict | None = None
    increase_stats_by_values: dict | None = None
    decrease_stats_by_values: dict | None = None


# ---------------------------------------------------------------------------
# Components for tracking zone interactions
# ---------------------------------------------------------------------------
@dataclass
class WithinZones:
    zone_ids: list

@dataclass
class NotWithinZones:
    zone_ids: list

@dataclass
class EnteredZones:
    zone_ids: list

@dataclass
class ExitedZones:
    zone_ids: list

@dataclass
class ZoneBordersDirty:
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
        meta_data = properties.get("metaData", {}) if isinstance(properties, dict) else {}
        esper.add_component(new_entity_id, ID(id=id))
        esper.add_component(new_entity_id, Geometry(coordinates=geometry.get("coordinates", [0,0])))
        esper.add_component(
            new_entity_id,
            MetaData(
                name=meta_data.get("name", ""),
                type=meta_data.get("type", nested_data.get("type", "")),
                description=meta_data.get("description", ""),
            ),
        )
        esper.add_component(
            new_entity_id,
            Appearance(
                color=appearance.get("color", ""),
                shape=appearance.get("shape", ""),
                radius=appearance.get("radius", 0),
            ),
        )

class ClientRequest:
    def __init__(self, id: str, geometry: dict, properties: dict) -> None:
        new_entity_id = esper.create_entity()
        self.entity_id = new_entity_id
        crp = properties.get("clientRequestProperties", {}) if isinstance(properties, dict) else {}
        esper.add_component(new_entity_id, ID(id=id))
        esper.add_component(new_entity_id, Geometry(coordinates=geometry.get("coordinates", [0,0])))
        esper.add_component(
            new_entity_id,
            ClientRequestProperties(
                requester_id=crp.get("requesterId", ""),
                timestamp=crp.get("timestamp", ""),
                request_type=crp.get("type", ""),
                requested_action=crp.get("requestedAction", ""),
            ),
        )

