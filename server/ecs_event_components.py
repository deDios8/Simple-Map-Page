from dataclasses import dataclass
import json
import pathlib
import esper
from ecs_geo_components import ID, DisplayName

_PUBLIC_DIR = pathlib.Path(__file__).parent.parent / "public"

# ---------------------------------------------------------------------------
# Components for constructing events
# ---------------------------------------------------------------------------
'''
One entity is the trigger. It has name, criteria, which geo objects meet criteria.
One entity is the target. It has name, criteria, which geo objects meet criteria.
One entity is the event result. It specifies, by name, which trigger and target entities it is associated with, and what to do to the target when the trigger conditions are met.
'''

# ---------------------------------------------------------------------------
# Components for trigger/target criteria
# ---------------------------------------------------------------------------
@dataclass
class CriteriaHasTags:
    tags: list

@dataclass
class CriteriaIsWithin:
    tags: list

@dataclass
class CriteriaNotWithin:
    tags: list

@dataclass
class CriteriaJustEntered:
    tags: list

@dataclass
class CriteriaJustExited:
    tags: list

@dataclass
class CriteriaVisibleTo:
    tags: list

@dataclass
class CriteriaNotVisibleTo:
    tags: list

@dataclass
class CriteriaFirstEntered:
    tags: list

@dataclass
class ObjectsThatMetAllCriteria:
    object_ids: list

@dataclass
class ObjectsThatMetAnyCriteria:
    object_ids: list


class Criteria:
    def __init__(self, id: str, name: str) -> None:
        new_entity_id = esper.create_entity()
        self.entity_id = new_entity_id
        esper.add_component(new_entity_id, ID(id=id))
        esper.add_component(new_entity_id, DisplayName(display_name=name))
        esper.add_component(new_entity_id, ObjectsThatMetAllCriteria(object_ids=[]))
        esper.add_component(new_entity_id, ObjectsThatMetAnyCriteria(object_ids=[]))


# ---------------------------------------------------------------------------
# Components for results
# ---------------------------------------------------------------------------
@dataclass
class EventTriggerNames: # should maybe use ID's
    criteria_ids: list

@dataclass
class EventTargetNames: # should maybe use ID's
    criteria_ids: list

@dataclass
class ResultGrantVisibility:
    tags: list

@dataclass
class ResultRevokeVisibility:
    tags: list

@dataclass
class ResultToggleVisibility:
    tags: list

@dataclass
class ResultSetColor:
    color: str

@dataclass
class ResultSetRadius:
    radius: int

@dataclass
class ResultChangeRadius:
    change: int

@dataclass
class ResultGrantTraits:
    tags: list

@dataclass
class ResultRevokeTraits:
    tags: list

@dataclass
class ResultToggleTraits:
    tags: list

@dataclass
class ResultRevokeStats:
    tags: list

@dataclass
class ResultToggleStats:
    stats: list

@dataclass
class ResultSetStatsToValues:
    '''This is also used to grant a stat if it doesn't exist yet.'''
    stats_to_values: dict

@dataclass
class ResultChangeStatsByValues:
    stats_to_values: dict

@dataclass
class ResultPopupMessage:
    text: str

class Event:
    def __init__(self, id: str, name: str) -> None:
        new_entity_id = esper.create_entity()
        self.entity_id = new_entity_id
        esper.add_component(new_entity_id, ID(id=id))
        esper.add_component(new_entity_id, DisplayName(display_name=name))
        esper.add_component(new_entity_id, EventTriggerNames(criteria_ids=[]))
        esper.add_component(new_entity_id, EventTargetNames(criteria_ids=[]))


# ---------------------------------------------------------------------------
# Components for criteria client requests
# ---------------------------------------------------------------------------
@dataclass
class AddCriteria:
    requester_id: str

@dataclass
class EditedCriteria:
    target_id: str
    form_data: dict

@dataclass
class DeletedCriteria:
    target_id: str

@dataclass
class AddEvent:
    requester_id: str

@dataclass
class EditedEvent:
    target_id: str
    form_data: dict

@dataclass
class DeletedEvent:
    target_id: str


# ---------------------------------------------------------------------------
# Single-source registries: maps component name → class
# Import these instead of repeating the lists in db_stream, main, or debug_console.
# ---------------------------------------------------------------------------

_criteria_json: dict = json.loads((_PUBLIC_DIR / "map_criteria_components.json").read_text())
CRITERIA_COMPONENT_NAMES: frozenset[str] = frozenset(_criteria_json.keys())
CRITERIA_COMPONENT_MAP: dict[str, type] = {name: globals()[name] for name in CRITERIA_COMPONENT_NAMES}
CRITERIA_COMPONENT_HANDLER_NAMES: dict[str, str] = {name: meta["handler"] for name, meta in _criteria_json.items()}

# Separate tracking components added to every criteria entity (not filter criteria).
CRITERIA_TRACKING_COMPONENT_MAP: dict[str, type] = {
    "ObjectsThatMetAnyCriteria": ObjectsThatMetAnyCriteria,
    "ObjectsThatMetAllCriteria": ObjectsThatMetAllCriteria,
}

_result_json: dict = json.loads((_PUBLIC_DIR / "map_result_components.json").read_text())
EVENT_RESULT_COMPONENT_NAMES: frozenset[str] = frozenset(_result_json.keys())
EVENT_RESULT_COMPONENT_MAP: dict[str, type] = {name: globals()[name] for name in EVENT_RESULT_COMPONENT_NAMES}
EVENT_RESULT_COMPONENT_HANDLER_NAMES: dict[str, str] = {name: meta["handler"] for name, meta in _result_json.items()}
EVENT_RESULT_COMPONENT_CONFIG: dict[str, dict] = dict(_result_json)

