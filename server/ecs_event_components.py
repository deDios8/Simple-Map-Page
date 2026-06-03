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
class TriggerHasTags:
    tags: list

@dataclass
class TargetHasTags:
    tags: list

@dataclass
class TriggerLacksTags:
    tags: list

@dataclass
class TargetLacksTags:
    tags: list

@dataclass
class TriggerIsWithin:
    tags: list

@dataclass
class TargetIsWithin:
    tags: list

@dataclass
class TriggerNotWithin:
    tags: list

@dataclass
class TargetNotWithin:
    tags: list

@dataclass
class TriggerJustEntered:
    tags: list

@dataclass
class TargetJustEntered:
    tags: list

@dataclass
class TriggerJustExited:
    tags: list

@dataclass
class TargetJustExited:
    tags: list

@dataclass
class TriggerFirstEntered:
    tags: list

@dataclass
class TargetFirstEntered:
    tags: list

@dataclass
class TriggerFirstExited:
    tags: list

@dataclass
class TargetFirstExited:
    tags: list

@dataclass
class TriggerEverEntered:
    tags: list

@dataclass
class TargetEverEntered:
    tags: list

@dataclass
class TriggerEverExited:
    tags: list

@dataclass
class TargetEverExited:
    tags: list

@dataclass
class TriggerRecentlyEntered:
    tags: list

@dataclass
class TargetRecentlyEntered:
    tags: list

@dataclass
class TriggerRecentlyExited:
    tags: list

@dataclass
class TargetRecentlyExited:
    tags: list

@dataclass
class TriggerVisibleTo:
    tags: list

@dataclass
class TargetVisibleTo:
    tags: list

@dataclass
class TriggerNotVisibleTo:
    tags: list

@dataclass
class TargetNotVisibleTo:
    tags: list

@dataclass
class ObjectsThatMetAllTriggerCriteria:
    object_ids: list

@dataclass
class ObjectsThatMetAllTargetCriteria:
    object_ids: list

@dataclass
class ObjectsThatMetAnyTriggerCriteria:
    object_ids: list

@dataclass
class ObjectsThatMetAnyTargetCriteria:
    object_ids: list


# ---------------------------------------------------------------------------
# Components for results
# ---------------------------------------------------------------------------
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
class ResultToggleStatsWithValue:
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
        esper.add_component(new_entity_id, ObjectsThatMetAllTriggerCriteria(object_ids=[]))
        esper.add_component(new_entity_id, ObjectsThatMetAllTargetCriteria(object_ids=[]))
        esper.add_component(new_entity_id, ObjectsThatMetAnyTriggerCriteria(object_ids=[]))
        esper.add_component(new_entity_id, ObjectsThatMetAnyTargetCriteria(object_ids=[]))


# ---------------------------------------------------------------------------
# Components for event client requests
# ---------------------------------------------------------------------------
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
TRIGGER_COMPONENT_NAMES: frozenset[str] = frozenset(
    name for name, meta in _criteria_json.items() if meta.get("role") == "trigger")
TARGET_COMPONENT_NAMES: frozenset[str] = frozenset(
    name for name, meta in _criteria_json.items() if meta.get("role") == "target")
TRIGGER_COMPONENT_MAP: dict[str, type] = {name: globals()[name] for name in TRIGGER_COMPONENT_NAMES}
TARGET_COMPONENT_MAP: dict[str, type] = {name: globals()[name] for name in TARGET_COMPONENT_NAMES}
TRIGGER_COMPONENT_HANDLER_NAMES: dict[str, str] = {
    name: meta["handler"] for name, meta in _criteria_json.items() if meta.get("role") == "trigger"}
TARGET_COMPONENT_HANDLER_NAMES: dict[str, str] = {
    name: meta["handler"] for name, meta in _criteria_json.items() if meta.get("role") == "target"}

_result_json: dict = json.loads((_PUBLIC_DIR / "map_result_components.json").read_text())
EVENT_RESULT_COMPONENT_NAMES: frozenset[str] = frozenset(_result_json.keys())
EVENT_RESULT_COMPONENT_MAP: dict[str, type] = {name: globals()[name] for name in EVENT_RESULT_COMPONENT_NAMES}
EVENT_RESULT_COMPONENT_HANDLER_NAMES: dict[str, str] = {name: meta["handler"] for name, meta in _result_json.items()}
EVENT_RESULT_COMPONENT_CONFIG: dict[str, dict] = dict(_result_json)

