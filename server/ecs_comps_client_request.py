import esper
from dataclasses import dataclass
from ecs_comps_geo import ID, Geometry

# Components for client requests
@dataclass
class ClientRequestPayload:
    requester_id: str
    timestamp: str
    request_type: str = ""
    requested_action: str = ""

@dataclass
class NewLocation:
    requester_id: str

@dataclass
class AddObject:
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
class AddEvent:
    requester_id: str

@dataclass
class EditedEvent:
    target_id: str
    form_data: dict

@dataclass
class DeletedEvent:
    target_id: str

@dataclass
class DismissMessage:
    target_id: str
    message: str

@dataclass
class ClearLogs:
    target_id: str
    target_path: str

@dataclass
class ClearLogsAll:
    requester_id: str


## Entity
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

