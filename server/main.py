"""Firebase Feature Listener — entry point.

Responsibilities:
- Handlers for clientRequests changes (on_request_create, on_request_update, on_request_delete)
- Write helpers for making changes to the geoObjects node (put, patch, delete)
- Main loop that wires the DatabaseStream event queue to the handlers
"""

import ecs
import esper
import queue
import threading
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
        self.debug_command_queue: queue.Queue[str] = queue.Queue()
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
        appearance = geo_object.appearance if isinstance(geo_object.appearance, dict) else {}
        payload.setdefault("name", geo_object.name)
        payload.setdefault("description", geo_object.description)
        payload.setdefault("color", appearance.get("color", geo_object.color))
        payload.setdefault("radius", appearance.get("radius", geo_object.radius))
        payload.setdefault("shape", appearance.get("shape", ""))
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

        appearance_data = geo_object.appearance if isinstance(geo_object.appearance, dict) else {}
        appearance.color = appearance_data.get("color", geo_object.color)
        appearance.shape = appearance_data.get("shape", "")
        appearance.radius = appearance_data.get("radius", geo_object.radius)

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

    def _start_debug_console(self) -> None:
        def _read_commands() -> None:
            while True:
                try:
                    raw = input()
                except EOFError:
                    return
                except KeyboardInterrupt:
                    return

                command = raw.strip()
                if not command:
                    continue
                self.debug_command_queue.put(command)

        thread = threading.Thread(target=_read_commands, daemon=True)
        thread.start()

    def _print_debug_help(self) -> None:
        print(
            "[DEBUG] Commands: "
            "help | stats | world | list [geo|req] [count] | "
            "dump <key> | dumpgeo <key> | dumpreq <key>"
        )

    def _print_debug_stats(self) -> None:
        print(
            "[DEBUG] "
            f"geoObjects={len(self.GeoObjects)} "
            f"geoEntityIds={len(self.GeoObjectEntityIds)} "
            f"clientRequests={len(self.ClientRequests)} "
            f"requestEntityIds={len(self.ClientRequestEntityIds)}"
        )

    def _print_world_stats(self) -> None:
        metadata_count = len(list(esper.get_component(ecs.MetaData)))
        appearance_count = len(list(esper.get_component(ecs.Appearance)))
        geometry_count = len(list(esper.get_component(ecs.Geometry)))
        request_count = len(list(esper.get_component(ecs.RequestParameters)))

        geo_entities = {
            entity_id for entity_id, _ in esper.get_component(ecs.MetaData)
        }
        request_entities = {
            entity_id for entity_id, _ in esper.get_component(ecs.RequestParameters)
        }
        all_entities = geo_entities | request_entities

        print(
            "[DEBUG][world] "
            f"entities={len(all_entities)} "
            f"meta={metadata_count} appearance={appearance_count} geometry={geometry_count} "
            f"requestParameters={request_count}"
        )

    def _print_debug_list(self, subject: str, count: int) -> None:
        if subject == "geo":
            keys = sorted(self.GeoObjectEntityIds.keys())
            print(f"[DEBUG] geo keys ({len(keys)} total): {keys[:count]}")
            return
        if subject == "req":
            keys = sorted(self.ClientRequestEntityIds.keys())
            print(f"[DEBUG] req keys ({len(keys)} total): {keys[:count]}")
            return
        print("[DEBUG] list usage: list [geo|req] [count]")

    def _print_geo_dump(self, key: str) -> bool:
        entity_id = self.GeoObjectEntityIds.get(key)
        if entity_id is None:
            return False
        metadata = esper.component_for_entity(entity_id, ecs.MetaData)
        appearance = esper.component_for_entity(entity_id, ecs.Appearance)
        geometry = esper.component_for_entity(entity_id, ecs.Geometry)
        print(
            "[DEBUG][geo] "
            f"key={key} entity={entity_id} "
            f"id={metadata.id} name={metadata.name!r} type={metadata.type!r} "
            f"description={metadata.description!r} color={appearance.color!r} "
            f"shape={appearance.shape!r} radius={appearance.radius} "
            f"coordinates={geometry.coordinates}"
        )
        return True

    def _print_request_dump(self, key: str) -> bool:
        entity_id = self.ClientRequestEntityIds.get(key)
        if entity_id is None:
            return False
        request = esper.component_for_entity(entity_id, ecs.RequestParameters)
        print(
            "[DEBUG][req] "
            f"key={key} entity={entity_id} requester_id={request.requester_id!r} "
            f"timestamp={request.timestamp!r}"
        )
        return True

    def _process_debug_command(self, raw_command: str) -> None:
        parts = raw_command.split()
        if not parts:
            return

        command = parts[0].lower()

        if command == "help":
            self._print_debug_help()
            return
        if command == "stats":
            self._print_debug_stats()
            return
        if command == "world":
            self._print_world_stats()
            return
        if command == "list":
            subject = "geo"
            count = 10
            if len(parts) >= 2:
                subject = parts[1].lower()
            if len(parts) >= 3:
                try:
                    count = max(1, int(parts[2]))
                except ValueError:
                    print("[DEBUG] count must be an integer")
                    return
            self._print_debug_list(subject, count)
            return
        if command == "dumpgeo":
            if len(parts) < 2:
                print("[DEBUG] dumpgeo usage: dumpgeo <key>")
                return
            if not self._print_geo_dump(parts[1]):
                print(f"[DEBUG] geo key not found: {parts[1]}")
            return
        if command == "dumpreq":
            if len(parts) < 2:
                print("[DEBUG] dumpreq usage: dumpreq <key>")
                return
            if not self._print_request_dump(parts[1]):
                print(f"[DEBUG] req key not found: {parts[1]}")
            return
        if command == "dump":
            if len(parts) < 2:
                print("[DEBUG] dump usage: dump <key>")
                return
            key = parts[1]
            if self._print_geo_dump(key):
                return
            if self._print_request_dump(key):
                return
            print(f"[DEBUG] key not found in geo or req maps: {key}")
            return

        print(f"[DEBUG] Unknown command: {raw_command}")

    def _drain_debug_commands(self) -> None:
        while True:
            try:
                command = self.debug_command_queue.get_nowait()
            except queue.Empty:
                return
            self._process_debug_command(command)

    def run_listener(self) -> None:
        self.stream.start()
        self._start_debug_console()
        self._print_debug_help()

        while True:
            try:
                self._drain_debug_commands()
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
                self._drain_debug_commands()
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
