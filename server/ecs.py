import esper


# ---------------------------------------------------------------------------
# Comonents
# ---------------------------------------------------------------------------

class MetaData:
    def __init__(self, id: str, name: str, type: str, description: str) -> None:
        self.id = id
        self.name = name
        self.type = type
        self.description = description

class Appearance:
    def __init__(self, color: str, shape: str, radius: int) -> None:
        self.color = color
        self.shape = shape
        self.radius = radius

class Geometry:
    def __init__(self, coordinates: list) -> None:
        self.coordinates = coordinates # Longitude, Latitude
        self.type = "Point"  # Assuming all geo objects are points for simplicity; can be extended to support other types

class RequestParameters:
    def __init__(self, requester_id: str, timestamp: str) -> None:
        self.requester_id = requester_id
        self.timestamp = timestamp


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

class GeoObject:
    def __init__(self, id: str, geometry: dict, data: dict) -> None:
        new_entity = esper.create_entity()
        self.entity_id = new_entity
        esper.add_component(new_entity, MetaData(id=id, name=data.get("name", ""), type=data.get("type", ""), description=data.get("description", "")))
        esper.add_component(new_entity, Appearance(color=data.get("color", ""), shape=data.get("shape", ""), radius=data.get("radius", 0)))
        esper.add_component(new_entity, Geometry(coordinates=geometry.get("coordinates", [0,0])))

class ClientRequest:
    def __init__(self, requester_id: str, timestamp: str) -> None:
        new_request = esper.create_entity()
        self.entity_id = new_request
        esper.add_component(new_request, RequestParameters(requester_id=requester_id, timestamp=timestamp))
