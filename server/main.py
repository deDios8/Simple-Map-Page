"""Firebase Feature Listener — entry point.

Responsibilities:
- Handlers for clientRequests changes (on_request_create, on_request_update, on_request_delete)
- Write helpers for making changes to the geoObjects node (put, patch, delete)
- Main loop that wires the DatabaseStream event queue to the handlers
"""

import ecs
import queue
from db_stream import (
    DEFAULT_DATABASE_URL,
    DatabaseStream,
    SyncChange,
    ClientRequestEntry,
    GeoObjectEntry,
    put_db_entry,
    patch_db_entry,
    delete_db_entry,
)


class SessionState:
    def __init__(self) -> None:
        self.GeoObjects = []
        self.ClientRequests = []
        # initialize starting entries here
        for each in self.stream.fetch_geo_objects(DEFAULT_DATABASE_URL, "testBed").values():
            self.GeoObjects.append(ecs.GeoObject(id=each.id, geometry=each.geometry, data=each.data))
        for each in self.stream.fetch_client_requests(DEFAULT_DATABASE_URL, "testBed").values():
            self.ClientRequests.append(ecs.ClientRequest(requester_id=each.requester_id, timestamp=each.timestamp))

    def on_request_create(self, key: str, request: ClientRequestEntry) -> None:
        print(f"[REQUEST CREATE] {key}: from={request.requester_id}")

    def on_geo_object_create(self, key: str, geo_object: GeoObjectEntry) -> None:
        print(f"[GEO OBJECT CREATE] {key}: {geo_object}")

    def on_request_update(self, key: str, request: ClientRequestEntry) -> None:
        print(f"[REQUEST UPDATE] {key}: from={request.requester_id}")

    def on_geo_object_update(self, key: str, geo_object: GeoObjectEntry) -> None:
        print(f"[GEO OBJECT UPDATE] {key}: {geo_object}")

    def on_request_delete(self, key: str, request: ClientRequestEntry | None) -> None:
        if request is None:
            print(f"[REQUEST DELETE] {key}: request is None")
        else:
            print(f"[REQUEST DELETE] {key}: from={request.requester_id}")

    def on_geo_object_delete(self, key: str, geo_object: GeoObjectEntry | None) -> None:
        if geo_object is None:
            print(f"[GEO OBJECT DELETE] {key}: geo_object is None")
        else:
            print(f"[GEO OBJECT DELETE] {key}: {geo_object}")

    def run_listener(self, database_url: str, session_name: str) -> None:
        session_name_without_slashes = session_name.strip().strip("/") or "testBed"
        self.stream = DatabaseStream(database_url, session_name_without_slashes)
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
                    if isinstance(change.feature, ClientRequestEntry) or change.feature is None:
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
    session_state = SessionState()
    session_state.run_listener(DEFAULT_DATABASE_URL, session_name)


if __name__ == "__main__":
    main()
