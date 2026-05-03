from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError

from server.old_db_stream import (
    DEFAULT_DATABASE_URL,
    apply_stream_event,
    fetch_client_requests,
    fetch_geo_objects,
    iter_firebase_client_stream,
    iter_firebase_stream,
    normalize_session_name,
)


class geo_Feature:
    def __init__(self, geo_object: dict[str, Any]) -> None:
        self.update_from_geo_object(geo_object)

    def update_from_geo_object(self, geo_object: dict[str, Any]) -> None:
        self.type = geo_object.get("type", "")
        self.geometry = geo_object.get("geometry", {})
        self.properties = geo_object.get("properties", {})
        self.appearance = self.properties.get("appearance", {})
        self.id = self.properties.get("id", "")
        self.name = self.properties.get("name", "")
        self.description = self.properties.get("description", "")
        self.coordinates = self.geometry.get("coordinates", [])


class client_Request(geo_Feature):
    def update_from_geo_object(self, geo_object: dict[str, Any]) -> None:
        super().update_from_geo_object(geo_object)
        self.requester_id = self.properties.get("requesterId", "")
        self.timestamp = self.properties.get("timestamp", "")


@dataclass
class SyncChange:
    stream_name: str
    action: str
    key: str
    feature: geo_Feature | None


def _default_on_create(feature_key: str, feature: geo_Feature) -> None:
    print(f"[FEATURE CREATE] {feature_key}")


def _default_on_update(feature_key: str, feature: geo_Feature) -> None:
    print(f"[FEATURE UPDATE] {feature_key}")


def _default_on_delete(feature_key: str, feature: geo_Feature | None) -> None:
    print(f"[FEATURE DELETE] {feature_key}")


def _default_on_request_create(request_key: str, request: geo_Feature) -> None:
    requester_id = request.properties.get("requesterId", "")
    print(f"[REQUEST CREATE] {request_key}: from={requester_id}, id={request.id}")


def _default_on_request_delete(request_key: str, request: geo_Feature | None) -> None:
    print(f"[REQUEST DELETE] {request_key}")


def _build_feature_index(
    geo_objects: dict[str, Any],
    factory: type[geo_Feature] = geo_Feature,
) -> dict[str, geo_Feature]:
    index: dict[str, geo_Feature] = {}
    for object_key, geo_object in geo_objects.items():
        if isinstance(geo_object, dict):
            index[object_key] = factory(geo_object)
    return index


def _sync_feature_index(
    feature_index: dict[str, geo_Feature],
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    factory: type[geo_Feature] = geo_Feature,
) -> list[SyncChange]:
    changes: list[SyncChange] = []
    before_keys = set(before_state.keys())
    after_keys = set(after_state.keys())

    for deleted_key in sorted(before_keys - after_keys):
        removed_feature = feature_index.pop(deleted_key, None)
        changes.append(
            SyncChange(
                stream_name="",
                action="delete",
                key=deleted_key,
                feature=removed_feature,
            )
        )

    for added_key in sorted(after_keys - before_keys):
        geo_object = after_state.get(added_key)
        if isinstance(geo_object, dict):
            created_feature = factory(geo_object)
            feature_index[added_key] = created_feature
            changes.append(
                SyncChange(
                    stream_name="",
                    action="create",
                    key=added_key,
                    feature=created_feature,
                )
            )

    for shared_key in sorted(before_keys & after_keys):
        before_object = before_state.get(shared_key)
        after_object = after_state.get(shared_key)
        if before_object == after_object:
            continue

        if not isinstance(after_object, dict):
            removed_feature = feature_index.pop(shared_key, None)
            changes.append(
                SyncChange(
                    stream_name="",
                    action="delete",
                    key=shared_key,
                    feature=removed_feature,
                )
            )
            continue

        existing = feature_index.get(shared_key)
        if existing is None:
            created_feature = factory(after_object)
            feature_index[shared_key] = created_feature
            changes.append(
                SyncChange(
                    stream_name="",
                    action="create",
                    key=shared_key,
                    feature=created_feature,
                )
            )
        else:
            existing.update_from_geo_object(after_object)
            changes.append(
                SyncChange(
                    stream_name="",
                    action="update",
                    key=shared_key,
                    feature=existing,
                )
            )

    return changes


@dataclass
class FeatureCallbacks:
    on_create: Callable[[str, geo_Feature], None] = _default_on_create
    on_update: Callable[[str, geo_Feature], None] = _default_on_update
    on_delete: Callable[[str, geo_Feature | None], None] = _default_on_delete


def _run_stream_worker(
    database_url: str,
    session_name: str,
    stream_name: str,
    local_state: dict[str, Any],
    feature_index: dict[str, geo_Feature],
    fetch_snapshot: Callable[[str, str], dict[str, dict[str, Any]]],
    iter_stream: Callable[[str, str], Any],
    factory: type[geo_Feature],
    output_queue: queue.Queue[SyncChange],
    stop_event: threading.Event,
) -> None:
    local_state.clear()
    local_state.update(fetch_snapshot(database_url, session_name))
    feature_index.update(_build_feature_index(local_state, factory=factory))
    print(f"Loaded {len(local_state)} object(s) from /{session_name}/{stream_name}.")

    seen_initial_snapshot = False

    while True:
        if stop_event.is_set():
            return

        try:
            for stream_event in iter_stream(database_url, session_name):
                if stop_event.is_set():
                    return

                if stream_event.event_type in {"keep-alive", "cancel", "auth_revoked"}:
                    continue

                if stream_event.event_type not in {"put", "patch"}:
                    continue

                if not seen_initial_snapshot and stream_event.path == "/":
                    seen_initial_snapshot = True
                    continue

                before_state = json.loads(json.dumps(local_state))
                apply_stream_event(local_state, stream_event)
                changes = _sync_feature_index(
                    feature_index,
                    before_state,
                    local_state,
                    factory=factory,
                )

                for change in changes:
                    change.stream_name = stream_name
                    output_queue.put(change)
        except (HTTPError, URLError, RuntimeError) as error:
            print(f"[WARN] {stream_name} stream disconnected: {error}")
            print(f"[INFO] Reconnecting {stream_name} stream in 2 seconds...")
            time.sleep(2)


def run_feature_listener(
    database_url: str,
    session_name: str,
) -> None:
    geo_callbacks = FeatureCallbacks()
    request_callbacks = FeatureCallbacks(
        on_create=_default_on_request_create,
        on_update=lambda key, req: None,
        on_delete=_default_on_request_delete,
    )
    callbacks_by_stream = {
        "geoObjects": geo_callbacks,
        "clientRequests": request_callbacks,
    }

    geo_state: dict[str, Any] = {}
    request_state: dict[str, Any] = {}
    feature_index: dict[str, geo_Feature] = {}
    request_index: dict[str, geo_Feature] = {}
    event_queue: queue.Queue[SyncChange] = queue.Queue()
    stop_event = threading.Event()

    geo_thread = threading.Thread(
        target=_run_stream_worker,
        args=(
            database_url,
            session_name,
            "geoObjects",
            geo_state,
            feature_index,
            fetch_geo_objects,
            iter_firebase_stream,
            geo_Feature,
            event_queue,
            stop_event,
        ),
        daemon=True,
    )
    geo_thread.start()

    request_thread = threading.Thread(
        target=_run_stream_worker,
        args=(
            database_url,
            session_name,
            "clientRequests",
            request_state,
            request_index,
            fetch_client_requests,
            iter_firebase_client_stream,
            client_Request,
            event_queue,
            stop_event,
        ),
        daemon=True,
    )
    request_thread.start()

    while True:
        try:
            change = event_queue.get(timeout=0.5)
            callbacks = callbacks_by_stream.get(change.stream_name)
            if callbacks is None:
                continue

            if change.action == "create" and change.feature is not None:
                callbacks.on_create(change.key, change.feature)
            elif change.action == "update" and change.feature is not None:
                callbacks.on_update(change.key, change.feature)
            elif change.action == "delete":
                callbacks.on_delete(change.key, change.feature)
        except KeyboardInterrupt:
            stop_event.set()
            print("\nStopped listener.")
            return
        except queue.Empty:
            continue
        except (HTTPError, URLError, RuntimeError) as error:
            print(f"[WARN] Stream disconnected: {error}")
            print("[INFO] Reconnecting in 2 seconds...")
            time.sleep(2)


def main() -> None:
    print("Firebase Feature Listener")
    raw_session = input("Session name: ")
    session_name = normalize_session_name(raw_session)
    run_feature_listener(DEFAULT_DATABASE_URL, session_name)


if __name__ == "__main__":
    main()
