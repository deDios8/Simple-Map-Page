from dataclasses import dataclass
import esper
 

# ---------------------------------------------------------------------------
# Components for constructive events
# ---------------------------------------------------------------------------
'''
Seeker looks for matching entities and attached a trigger component to them.
Trigger components check for matching properties and if they match, they fire a Targetted search.
Valid targets have a result component attached to them.
Result components are then processed to apply their effects and then removed.
'''
"""class Trigger:
    def __init__(self, items: dict | None = None) -> None:
        '''
        ALL trigger conditions must be met for this to trigger, (AND condition)
        multiple triggers can be assigned to make an OR condition instead of an AND condition
        '''

        self.trigger_id: str = 'trigger' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=2))

        self.has_name: list | None = []
        self.hatype: list | None = []
        self.has_statuses: list | None = []
        self.does_not_have_statuses: list | None = []

        self.is_within_names: list | None = []
        self.is_not_within_names: list | None = []
        self.is_within_statuses: list | None = []
        self.is_not_within_statuses: list | None = []
        self.just_entered_names: list | None = []
        self.just_exited_names: list | None = []
        self.just_entered_statuses: list | None = []
        self.just_exited_statuses: list | None = []

        self.stat_name_equals: dict | None = {}
        self.stat_name_is_above: dict | None = {}
        self.stat_name_is_below: dict | None = {}

        self.entities_meeting_trigger_criteria: list | None = []

class Triggers:
    def __init__(self, items: dict | None = None) -> None:
        self.items = items if isinstance(items, dict) else {}
"""

class CriteriaHasStatuses:
    def __init__(self, statuses: list) -> None:
        self.statuses = statuses

class CriteriaIsWithin:
    def __init__(self, statuses: list) -> None:
        self.statuses = statuses

class CriteriaJustEntered:
    def __init__(self, statuses: list) -> None:
        self.statuses = statuses

class CriteriaJustExited:
    def __init__(self, statuses: list) -> None:
        self.statuses = statuses


class Target:
    '''
    if ALL are true, attach a Result component to the entity
    attaching multiple Target components that attach the same result_id to an entity can create an OR condition instead of an AND condition
    '''
    def __init__(self, items: dict | None = None) -> None:
        target_id: str

        target_triggering_entities: bool = False  # if true, the target conditions apply to the triggering entity/entities

        target_names: list | None = []
        target_types: list | None = []
        target_statuses: list | None = []
        target_stat_id_is_above: dict | None = {}
        target_stat_id_is_below: dict | None = {}
        target_stat_type_is_above: dict | None = {}
        target_stat_type_is_below: dict | None = {}

        entities_meeting_target_criteria: list | None = []  # ID of the entities that match target conditions, apply result to these

class Targets:
    def __init__(self, items: dict | None = None) -> None:
        self.items = items if isinstance(items, dict) else {}


class Result:
    '''
    do all of the following to the entity with this ID when the trigger conditions are met
    '''
    def __init__(self, items: dict | None = None) -> None:
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

class Results:
    def __init__(self, items: dict | None = None) -> None:
        self.items = items if isinstance(items, dict) else {}

