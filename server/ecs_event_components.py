from dataclasses import dataclass
 

# ---------------------------------------------------------------------------
# Components for constructing events
# ---------------------------------------------------------------------------
'''
One entity is the trigger. It has name, criteria, which items meet criteria, and matching objects.
One entity is the target. It has name, criteria, which items meet criteria, and matching objects.
One entity is the event result. It specifies, by name, which trigger and target entities it is associated with, and what to do to the target when the trigger conditions are met.
'''

# ---------------------------------------------------------------------------
# Components for trigger/target criteria
# ---------------------------------------------------------------------------
@dataclass
class CriteriaName:
    id: str
    name: str

@dataclass
class CriteriaHasStats:
    stats: list

@dataclass
class CriteriaIsWithin:
    stats: list

@dataclass
class CriteriaJustEntered:
    stats: list

@dataclass
class CriteriaJustExited:
    stats: list

@dataclass
class ObjectsThatMetAllCriteria:
    object_ids: list

@dataclass
class ObjectsThatMetAnyCriteria:
    object_ids: list

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

