"""Firebase Feature Listener — entry point.

Responsibilities:
- Handlers for clientRequests changes (on_request_create, on_request_update, on_request_delete)
- Write helpers for making changes to the geoObjects node (put, patch, delete)
- Main loop that wires the DatabaseStream event queue to the handlers
"""

import queue
from db_stream import (
    DEFAULT_DATABASE_URL,
    DatabaseStream,
    SyncChange,
    ClientRequest,
    put_db_entry,
    patch_db_entry,
    delete_db_entry,
)


# ---------------------------------------------------------------------------
# clientRequests handlers  — fill in logic here
# ---------------------------------------------------------------------------


def on_request_create(key: str, request: ClientRequest) -> None:
    print(f"[REQUEST CREATE] {key}: from={request.requester_id}")

def on_geo_object_create(key: str, geo_object: dict) -> None:
    print(f"[GEO OBJECT CREATE] {key}: {geo_object}")

def on_request_update(key: str, request: ClientRequest) -> None:
    print(f"[REQUEST UPDATE] {key}: from={request.requester_id}")

def on_geo_object_update(key: str, geo_object: dict) -> None:
    print(f"[GEO OBJECT UPDATE] {key}: {geo_object}")

def on_request_delete(key: str, request: ClientRequest | None) -> None:
    if request is None:
        print(f"[REQUEST DELETE] {key}: request is None")
    else:
        print(f"[REQUEST DELETE] {key}: from={request.requester_id}")

def on_geo_object_delete(key: str, geo_object: dict | None) -> None:
    if geo_object is None:
        print(f"[GEO OBJECT DELETE] {key}: geo_object is None")
    else:
        print(f"[GEO OBJECT DELETE] {key}: {geo_object}")

def run_listener(database_url: str, session_name: str) -> None:
    session_name_without_slashes = session_name.strip().strip("/") or "testBed"
    stream = DatabaseStream(database_url, session_name_without_slashes)
    stream.start()

    while True:
        try:
            change: SyncChange = stream.event_queue.get(timeout=0.5)
            if change.action == "create":
                if isinstance(change.feature, ClientRequest):
                    on_request_create(change.key, change.feature)
                else:
                    on_geo_object_create(change.key, change.feature)
            elif change.action == "update" and change.feature is not None:
                if isinstance(change.feature, ClientRequest):
                    on_request_update(change.key, change.feature)
                else:
                    on_geo_object_update(change.key, change.feature)
            elif change.action == "delete":
                if isinstance(change.feature, ClientRequest) or change.feature is None:
                    on_request_delete(change.key, change.feature)
                else:
                    on_geo_object_delete(change.key, change.feature)
            # Removed redundant delete handling
        except KeyboardInterrupt:
            stream.stop()
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
    run_listener(DEFAULT_DATABASE_URL, session_name)


if __name__ == "__main__":
    main()
