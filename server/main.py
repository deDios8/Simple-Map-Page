"""Firebase Feature Listener — entry point.

Responsibilities:
- Handlers for clientRequests changes (_on_client_request_create, _on_client_request_update, _on_client_request_delete)
- Write helpers for making changes to the geoObjects node (put, patch, delete)
- Main loop that wires the DatabaseStream event queue to the handlers
"""

import server.ecs_components as ecs_components
import esper
import queue
import time
from debug_console import SessionDebugConsole
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
        self.GeoObjects: dict[str, ecs_components.GeoObject] = {}
        self.ClientRequests: dict[str, ecs_components.ClientRequest] = {}
        self.GeoObjectEntityIds: dict[str, int] = {}
        self.ClientRequestEntityIds: dict[str, int] = {}

        self.stream = DatabaseStream(self.database_url, self.session_name)
        self.debug = SessionDebugConsole(self)
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


    def _upsert_geo_object_entity(self, key: str, geo_object: GeoObjectEntry) -> int:
        existing_entity_id = self.GeoObjectEntityIds.get(key)
        if existing_entity_id is None:
            geo = ecs_components.GeoObject(
                id=geo_object.id or key,
                geometry=geo_object.geometry,
                properties=geo_object.properties,
            )
            self.GeoObjects[key] = geo
            self.GeoObjectEntityIds[key] = geo.entity_id
            return geo.entity_id

        props = geo_object.properties if isinstance(geo_object.properties, dict) else {}

        id_component = esper.component_for_entity(existing_entity_id, ecs_components.ID)
        id_component.id = props.get("id", geo_object.id or key)

        metadata = esper.component_for_entity(existing_entity_id, ecs_components.MetaData)
        meta_data = props.get("metaData", {}) if isinstance(props.get("metaData"), dict) else {}
        metadata.name = meta_data.get("name", "")
        metadata.description = meta_data.get("description", "")
        metadata.type = meta_data.get("type", "")

        appearance = esper.component_for_entity(existing_entity_id, ecs_components.Appearance)
        appearance_data = props.get("appearance", {}) if isinstance(props.get("appearance"), dict) else {}
        appearance.color = appearance_data.get("color", "")
        appearance.shape = appearance_data.get("shape", "")
        appearance.radius = appearance_data.get("radius", 0)

        geometry = esper.component_for_entity(existing_entity_id, ecs_components.Geometry)
        geometry.coordinates = geo_object.geometry.get("coordinates", [0, 0])
        return existing_entity_id

    def _upsert_client_request_entity(self, key: str, request: ClientRequestEntry) -> int:
        existing_entity_id = self.ClientRequestEntityIds.get(key)
        if existing_entity_id is None:
            entity = ecs_components.ClientRequest(
                id=request.id or key,
                geometry=request.geometry,
                properties=request.properties,
            )
            self.ClientRequests[key] = entity
            self.ClientRequestEntityIds[key] = entity.entity_id
            return entity.entity_id

        props = request.properties if isinstance(request.properties, dict) else {}

        id_component = esper.component_for_entity(existing_entity_id, ecs_components.ID)
        id_component.id = props.get("id", request.id or key)

        geometry = esper.component_for_entity(existing_entity_id, ecs_components.Geometry)
        geometry.coordinates = request.geometry.get("coordinates", [0, 0])

        request_params = esper.component_for_entity(existing_entity_id, ecs_components.ClientRequestProperties)
        crp = props.get("clientRequestProperties", {}) if isinstance(props.get("clientRequestProperties"), dict) else {}
        request_params.requester_id = crp.get("requesterId", "")
        request_params.timestamp = crp.get("timestamp", "")
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


    def _on_geo_object_create(self, key: str, geo_object: GeoObjectEntry) -> None:
        entity_id = self._upsert_geo_object_entity(key, geo_object)
        print(f"[GEO OBJECT CREATE] {key}: entity={entity_id}")

    def _on_client_request_create(self, key: str, request: ClientRequestEntry) -> None:
        entity_id = self._upsert_client_request_entity(key, request)
        print(f"[REQUEST CREATE] {key}: from={request.requester_id}, entity={entity_id}")


    def _on_geo_object_update(self, key: str, geo_object: GeoObjectEntry) -> None:
        entity_id = self._upsert_geo_object_entity(key, geo_object)
        print(f"[GEO OBJECT UPDATE] {key}: entity={entity_id}")

    def _on_client_request_update(self, key: str, request: ClientRequestEntry) -> None:
        entity_id = self._upsert_client_request_entity(key, request)
        print(f"[REQUEST UPDATE] {key}: from={request.requester_id}, entity={entity_id}")


    def _on_geo_object_delete(self, key: str, geo_object: GeoObjectEntry | None) -> None:
        entity_id = self._delete_geo_object_entity(key)
        if geo_object is None:
            print(f"[GEO OBJECT DELETE] {key}: geo_object is None, entity={entity_id}")
        else:
            print(f"[GEO OBJECT DELETE] {key}: entity={entity_id}")

    def _on_client_request_delete(self, key: str, request: ClientRequestEntry | None) -> None:
        entity_id = self._delete_client_request_entity(key)
        if request is None:
            print(f"[REQUEST DELETE] {key}: request is None, entity={entity_id}")
        else:
            print(f"[REQUEST DELETE] {key}: from={request.requester_id}, entity={entity_id}")


    def run_db_and_ecs_processor(self) -> None:
        self.stream.start()
        self.debug.start()
        self.debug.print_help()

        ticks_per_second = 2.0
        tick_dt = 1.0 / ticks_per_second
        next_tick = time.perf_counter()

        while True:
            try:
                self.debug.drain_commands()

                # Run ECS ticks on schedule while avoiding runaway catch-up.
                now = time.perf_counter()
                tick_steps = 0
                max_catchup_steps = 5
                while now >= next_tick and tick_steps < max_catchup_steps:
                    esper.process()
                    next_tick += tick_dt
                    tick_steps += 1

                # If far behind, resync the schedule to keep the loop stable.
                if now - next_tick > 1.0:
                    next_tick = now + tick_dt

                # Wait for DB events, but never longer than time until next tick.
                time_until_tick = max(0.0, next_tick - time.perf_counter())
                wait_timeout = min(time_until_tick, 0.1)

                # Handle DB events as they come in, but don't let them block the loop indefinitely.
                change: SyncChange = self.stream.event_queue.get(timeout=wait_timeout)
                if change.action == "create":
                    if isinstance(change.feature, ClientRequestEntry):
                        self._on_client_request_create(change.key, change.feature)
                    else:
                        self._on_geo_object_create(change.key, change.feature)
                elif change.action == "update" and change.feature is not None:
                    if isinstance(change.feature, ClientRequestEntry):
                        self._on_client_request_update(change.key, change.feature)
                    else:
                        self._on_geo_object_update(change.key, change.feature)
                elif change.action == "delete":
                    if change.stream_name == CLIENT_REQUESTS_NODE:
                        self._on_client_request_delete(change.key, change.feature)
                    elif change.stream_name == GEO_OBJECTS_NODE:
                        self._on_geo_object_delete(change.key, change.feature)
                    elif isinstance(change.feature, ClientRequestEntry) or change.feature is None:
                        self._on_client_request_delete(change.key, change.feature)
                    else:
                        self._on_geo_object_delete(change.key, change.feature)
            except KeyboardInterrupt:
                self.stream.stop()
                print("\nStopped listener.")
                return
            except queue.Empty:
                continue



def main() -> None:
    print("Firebase Feature Listener")
    session_name = input("Session name: ")
    session_state = SessionState(DEFAULT_DATABASE_URL, session_name)
    session_state.run_db_and_ecs_processor()


if __name__ == "__main__":
    main()
