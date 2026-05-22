from dataclasses import dataclass
import esper
from ecs_geo_components import ID, MetaData

# ---------------------------------------------------------------------------
# Components for constructing events
# ---------------------------------------------------------------------------
'''
One entity is the trigger. It has name, criteria, which geo objects meet criteria, and matching objects.
One entity is the target. It has name, criteria, which geo objects meet criteria, and matching objects.
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
class CriteriaJustEntered:
    tags: list

@dataclass
class CriteriaJustExited:
    tags: list

@dataclass
class CriteriaIsVisible:
    is_visible: bool

@dataclass
class CriteriaIsNotVisible:
    is_visible: bool

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
    def __init__(self, id: str, name: str, description: str = "") -> None:
        new_entity_id = esper.create_entity()
        self.entity_id = new_entity_id
        esper.add_component(new_entity_id, ID(id=id))
        esper.add_component(new_entity_id, MetaData(name=name, description=description))
        esper.add_component(new_entity_id, ObjectsThatMetAllCriteria(object_ids=[]))
        esper.add_component(new_entity_id, ObjectsThatMetAnyCriteria(object_ids=[]))




# ---------------------------------------------------------------------------
# Components for results
# ---------------------------------------------------------------------------
@dataclass
class ResultTriggerNames: # should maybe use ID's
    names: list

@dataclass
class ResultTargetNames: # should maybe use ID's
    names: list

@dataclass
class ResultSetVisibility:
    visible: bool

@dataclass
class ResultToggleVisibility:
    toggle: bool

@dataclass
class ResultChangeColor:
    color: str

@dataclass
class ResultChangeRadius:
    radius: int

@dataclass
class ResultAddStats:
    stats: list

@dataclass
class ResultRemoveStats:
    stats: list

@dataclass
class ResultToggleStats:
    stats: list

@dataclass
class ResultSetStatsToValues:
    stats_to_values: dict

@dataclass
class ResultIncreaseStatsByValues:
    stats_to_values: dict

@dataclass
class ResultDecreaseStatsByValues:
    stats_to_values: dict


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

