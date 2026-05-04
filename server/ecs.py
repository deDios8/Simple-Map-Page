import esper


# ---------------------------------------------------------------------------
# Comonents
# ---------------------------------------------------------------------------
class ID:
    def __init__(self, id: str) -> None:
        self.id = id

class MetaData:
    def __init__(self, name: str, type: str, description: str) -> None:
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

class ClientRequestProperties:
    def __init__(self, requester_id: str, timestamp: str) -> None:
        self.requester_id = requester_id
        self.timestamp = timestamp


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
            MetaData(
                name=properties.get("name", ""),
                type=nested_data.get("type", properties.get("type", "")),
                description=properties.get("description", ""),
            ),
        )
        esper.add_component(
            new_entity_id,
            Appearance(
                color=appearance.get("color", properties.get("color", "")),
                shape=appearance.get("shape", properties.get("shape", "")),
                radius=appearance.get("radius", properties.get("radius", 0)),
            ),
        )

class ClientRequest:
    def __init__(self, id: str, geometry: dict, properties: dict) -> None:
        new_entity_id = esper.create_entity()
        self.entity_id = new_entity_id
        esper.add_component(new_entity_id, ID(id=id))
        esper.add_component(new_entity_id, Geometry(coordinates=geometry.get("coordinates", [0,0])))
        esper.add_component(
            new_entity_id,
            ClientRequestProperties(
                requester_id=properties.get("requesterId", ""),
                timestamp=properties.get("timestamp", ""),
            ),
        )
