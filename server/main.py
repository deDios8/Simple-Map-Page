"""Firebase Feature Listener — entry point.

Responsibilities:
- Handlers for clientRequests changes (on_request_create, on_request_update, on_request_delete)
- Write helpers for making changes to the geoObjects node (put, patch, delete)
- Main loop that wires the DatabaseStream event queue to the handlers
"""

from __future__ import annotations

import json
import queue
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from db_stream import (
    DEFAULT_DATABASE_URL,
    DatabaseStream,
    SyncChange,
    client_Request,
    geo_Feature,
    build_node_url,
    normalize_session_name,
)


GEO_OBJECTS_NODE = "geoObjects"


# ---------------------------------------------------------------------------
# geoObjects write helpers
# ---------------------------------------------------------------------------


def put_geo_object(
    database_url: str, session_name: str, key: str, geo_object: dict[str, Any]
) -> None:
    """Write (overwrite) a single geoObject entry by key."""
    url = build_node_url(database_url, session_name, GEO_OBJECTS_NODE, key)
    data = json.dumps(geo_object).encode("utf-8")
    req = Request(url, data=data, method="PUT", headers={"Content-Type": "application/json"})
    with urlopen(req) as response:
        response.read()


def patch_geo_object(
    database_url: str, session_name: str, key: str, fields: dict[str, Any]
) -> None:
    """Merge-update specific fields of a geoObject entry by key."""
    url = build_node_url(database_url, session_name, GEO_OBJECTS_NODE, key)
    data = json.dumps(fields).encode("utf-8")
    req = Request(url, data=data, method="PATCH", headers={"Content-Type": "application/json"})
    with urlopen(req) as response:
        response.read()


def delete_geo_object(database_url: str, session_name: str, key: str) -> None:
    """Delete a geoObject entry by key."""
    url = build_node_url(database_url, session_name, GEO_OBJECTS_NODE, key)
    req = Request(url, method="DELETE")
    with urlopen(req) as response:
        response.read()


# ---------------------------------------------------------------------------
# clientRequests handlers  — fill in logic here
# ---------------------------------------------------------------------------


def on_request_create(key: str, request: client_Request) -> None:
    print(f"[REQUEST CREATE] {key}: from={request.requester_id}")


def on_request_update(key: str, request: client_Request) -> None:
    print(f"[REQUEST UPDATE] {key}: from={request.requester_id}")


def on_request_delete(key: str, request: client_Request | None) -> None:
    print(f"[REQUEST DELETE] {key}: from={request.requester_id}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_listener(database_url: str, session_name: str) -> None:
    stream = DatabaseStream(database_url, session_name)
    stream.start()

    while True:
        try:
            change: SyncChange = stream.event_queue.get(timeout=0.5)
            if change.action == "create" and isinstance(change.feature, client_Request):
                on_request_create(change.key, change.feature)
            elif change.action == "update" and change.feature is not None:
                on_request_update(change.key, change.feature)
            elif change.action == "delete":
                on_request_delete(change.key, change.feature)
        except KeyboardInterrupt:
            stream.stop()
            print("\nStopped listener.")
            return
        except queue.Empty:
            continue


def main() -> None:
    print("Firebase Feature Listener")
    raw_session = input("Session name: ")
    session_name = normalize_session_name(raw_session)
    run_listener(DEFAULT_DATABASE_URL, session_name)


if __name__ == "__main__":
    main()
