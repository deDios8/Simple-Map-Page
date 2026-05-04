"""Firebase Feature Listener — entry point.

Responsibilities:
- Handlers for clientRequests changes (on_request_create, on_request_update, on_request_delete)
- Write helpers for making changes to the geoObjects node (put, patch, delete)
- Main loop that wires the DatabaseStream event queue to the handlers
"""

import ecs
import esper
import queue
from db_stream import (
    DEFAULT_DATABASE_URL,
    CLIENT_REQUESTS_NODE,
    GEO_OBJECTS_NODE,
    DatabaseStream,
    SyncChange,
    ClientRequestEntry,
    GeoObjectEntry,
    fetch_client_requests,
    fetch_geo_objects,
    put_db_entry,
    patch_db_entry,
    delete_db_entry,
)


class SessionState:
    def __init__(self, database_url: str, session_name: str) -> None:
        self.database_url = database_url
        self.session_name = session_name.strip().strip("/") or "testBed"

        # Keep dict-backed state so Firebase keys can map directly to ECS entities.
        self.GeoObjects: dict[str, ecs.GeoObject] = {}
        self.ClientRequests: dict[str, ecs.ClientRequest] = {}
        self.GeoObjectEntityIds: dict[str, int] = {}
        self.ClientRequestEntityIds: dict[str, int] = {}

        self.stream = DatabaseStream(self.database_url, self.session_name)
        self._initialize_from_snapshot()

    def _initialize_from_snapshot(self) -> None:
        geo_objects = fetch_geo_objects(self.database_url, self.session_name)
        self.geo_object_state = geo_objects
        for key, raw in geo_objects.items():
            entry = GeoObjectEntry(raw)
            self._upsert_geo_object_entity(key, entry)

        client_requests = fetch_client_requests(self.database_url, self.session_name)
        self.client_request_state = client_requests
        for key, raw in client_requests.items():
            entry = ClientRequestEntry(raw)
            self._upsert_client_request_entity(key, entry)

    def _build_geo_data_payload(self, geo_object: GeoObjectEntry) -> dict:
        payload = dict(geo_object.data or {})
        payload.setdefault("name", geo_object.name)
        payload.setdefault("description", geo_object.description)
        payload.setdefault("color", geo_object.color)
        payload.setdefault("radius", geo_object.radius)
        if isinstance(geo_object.appearance, dict):
            payload.setdefault("shape", geo_object.appearance.get("shape", ""))
        return payload

    def _upsert_geo_object_entity(self, key: str, geo_object: GeoObjectEntry) -> int:
        existing_entity_id = self.GeoObjectEntityIds.get(key)
        if existing_entity_id is None:
            geo = ecs.GeoObject(
                id=geo_object.id or key,
                geometry=geo_object.geometry,
                data=self._build_geo_data_payload(geo_object),
            )
            self.GeoObjects[key] = geo
            self.GeoObjectEntityIds[key] = geo.entity_id
            return geo.entity_id

        metadata = esper.component_for_entity(existing_entity_id, ecs.MetaData)
        appearance = esper.component_for_entity(existing_entity_id, ecs.Appearance)
        geometry = esper.component_for_entity(existing_entity_id, ecs.Geometry)

        metadata.id = geo_object.id or key
        metadata.name = geo_object.name
        metadata.description = geo_object.description

        appearance.color = geo_object.color
        if isinstance(geo_object.appearance, dict):
            appearance.shape = geo_object.appearance.get("shape", "")
        appearance.radius = geo_object.radius

        geometry.coordinates = geo_object.geometry.get("coordinates", [0, 0])
        return existing_entity_id

    def _upsert_client_request_entity(self, key: str, request: ClientRequestEntry) -> int:
        existing_entity_id = self.ClientRequestEntityIds.get(key)
        if existing_entity_id is None:
            entity = ecs.ClientRequest(
                requester_id=request.requester_id,
                timestamp=request.timestamp,
            )
            self.ClientRequests[key] = entity
            self.ClientRequestEntityIds[key] = entity.entity_id
            return entity.entity_id

        request_params = esper.component_for_entity(existing_entity_id, ecs.RequestParameters)
        request_params.requester_id = request.requester_id
        request_params.timestamp = request.timestamp
        return existing_entity_id

    def _delete_geo_object_entity(self, key: str) -> int | None:
        entity_id = self.GeoObjectEntityIds.pop(key, None)
        self.GeoObjects.pop(key, None)
        if entity_id is not None:
            esper.delete_entity(entity_id)
        return entity_id

    def _delete_client_request_entity(self, key: str) -> int | None:
        entity_id = self.ClientRequestEntityIds.pop(key, None)
        self.ClientRequests.pop(key, None)
        if entity_id is not None:
            esper.delete_entity(entity_id)
        return entity_id

    def on_request_create(self, key: str, request: ClientRequestEntry) -> None:
        entity_id = self._upsert_client_request_entity(key, request)
        print(f"[REQUEST CREATE] {key}: from={request.requester_id}, entity={entity_id}")

    def on_geo_object_create(self, key: str, geo_object: GeoObjectEntry) -> None:
        entity_id = self._upsert_geo_object_entity(key, geo_object)
        print(f"[GEO OBJECT CREATE] {key}: entity={entity_id}")

    def on_request_update(self, key: str, request: ClientRequestEntry) -> None:
        entity_id = self._upsert_client_request_entity(key, request)
        print(f"[REQUEST UPDATE] {key}: from={request.requester_id}, entity={entity_id}")

    def on_geo_object_update(self, key: str, geo_object: GeoObjectEntry) -> None:
        entity_id = self._upsert_geo_object_entity(key, geo_object)
        print(f"[GEO OBJECT UPDATE] {key}: entity={entity_id}")

    def on_request_delete(self, key: str, request: ClientRequestEntry | None) -> None:
        entity_id = self._delete_client_request_entity(key)
        if request is None:
            print(f"[REQUEST DELETE] {key}: request is None, entity={entity_id}")
        else:
            print(f"[REQUEST DELETE] {key}: from={request.requester_id}, entity={entity_id}")

    def on_geo_object_delete(self, key: str, geo_object: GeoObjectEntry | None) -> None:
        entity_id = self._delete_geo_object_entity(key)
        if geo_object is None:
            print(f"[GEO OBJECT DELETE] {key}: geo_object is None, entity={entity_id}")
        else:
            print(f"[GEO OBJECT DELETE] {key}: entity={entity_id}")

    def run_listener(self) -> None:
        self.stream.start()

        while True:
            try:
                change: SyncChange = self.stream.event_queue.get(timeout=0.5)
                if change.action == "create":
                    if isinstance(change.feature, ClientRequestEntry):
                        self.on_request_create(change.key, change.feature)
                    else:
                        self.on_geo_object_create(change.key, change.feature)
                elif change.action == "update" and change.feature is not None:
                    if isinstance(change.feature, ClientRequestEntry):
                        self.on_request_update(change.key, change.feature)
                    else:
                        self.on_geo_object_update(change.key, change.feature)
                elif change.action == "delete":
                    if change.stream_name == CLIENT_REQUESTS_NODE:
                        self.on_request_delete(change.key, change.feature)
                    elif change.stream_name == GEO_OBJECTS_NODE:
                        self.on_geo_object_delete(change.key, change.feature)
                    elif isinstance(change.feature, ClientRequestEntry) or change.feature is None:
                        self.on_request_delete(change.key, change.feature)
                    else:
                        self.on_geo_object_delete(change.key, change.feature)
                # Removed redundant delete handling
            except KeyboardInterrupt:
                self.stream.stop()
                print("\nStopped listener.")
                return
            except queue.Empty:
                continue


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    print("Firebase Feature Listener")
    session_name = input("Session name: ")
    session_state = SessionState(DEFAULT_DATABASE_URL, session_name)
    session_state.run_listener()


if __name__ == "__main__":
    main()
