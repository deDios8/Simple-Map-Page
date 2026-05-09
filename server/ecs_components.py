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

class IsUser:
    def __init__(self) -> None:
        self.is_user = True

class IsZone:
    def __init__(self) -> None:
        self.is_zone = True

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
    def __init__(self, requester_id: str, timestamp: str, request_type: str = "") -> None:
        self.requester_id = requester_id
        self.timestamp = timestamp
        self.request_type = request_type


class NewLocation:
    def __init__(self, requester_id: str) -> None:
        self.requester_id = requester_id


class EditedObject:
    def __init__(self, target_id: str, target_path: str, form_data: dict) -> None:
        self.target_id = target_id
        self.target_path = target_path
        self.form_data = form_data if isinstance(form_data, dict) else {}


class DeletedObject:
    def __init__(self, target_id: str, target_path: str) -> None:
        self.target_id = target_id
        self.target_path = target_path


class Stat:
    def __init__(self, name: str, type: str, value: int, max_value: int = 100, min_value: int = 0) -> None:
        self.name = name
        self.type = type
        self.value = value
        self.max_value = max_value
        self.min_value = min_value


class Stats:
    def __init__(self, items: dict | None = None) -> None:
        self.items = items if isinstance(items, dict) else {}

class Status:
    def __init__(self, name: str, type: str, strength: int, time_until_expire: int = 5) -> None:
        self.name = name
        self.type = type
        self.strength = strength
        self.time_until_expire = time_until_expire


class Statuses:
    def __init__(self, items: dict | None = None) -> None:
        self.items = items if isinstance(items, dict) else {}


class StatusA(Status): # Legacy alias for single-status callers
    pass

class WithinZones:
    def __init__(self, zone_ids: list) -> None:
        self.zone_ids = zone_ids

class EnteredZones:
    def __init__(self, zone_ids: list) -> None:
        self.zone_ids = zone_ids

class ExitedZones:
    def __init__(self, zone_ids: list) -> None:
        self.zone_ids = zone_ids


class ZoneBordersDirty:
    def __init__(self) -> None:
        self.is_dirty = True



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
            ),
        )
