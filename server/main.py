from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError

from db_stream import (
    DEFAULT_DATABASE_URL,
    apply_stream_event,
    fetch_geo_objects,
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


class client_Request:
    def __init__(self, client_requeset: dict[str, Any]) -> None:
        self.coordinates = client_requeset.get("coordinates", [])
        self.properties = client_requeset.get("properties", {})
        self.id = self.properties.get("id", "")
        self.requester_id = self.properties.get("requester_id", "")
        self.timestamp = self.properties.get("timestamp", 0)


def _default_on_create(feature_key: str, feature: geo_Feature) -> None:
    print(f"[FEATURE CREATE] {feature_key}")


def _default_on_update(feature_key: str, feature: geo_Feature) -> None:
    print(f"[FEATURE UPDATE] {feature_key}")


def _default_on_delete(feature_key: str, feature: geo_Feature | None) -> None:
    print(f"[FEATURE DELETE] {feature_key}")


def _build_feature_index(geo_objects: dict[str, Any]) -> dict[str, geo_Feature]:
    index: dict[str, geo_Feature] = {}
    for object_key, geo_object in geo_objects.items():
        if isinstance(geo_object, dict):
            index[object_key] = geo_Feature(geo_object)
    return index


def _sync_feature_index(
    feature_index: dict[str, geo_Feature],
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    callbacks: FeatureCallbacks,
) -> None:
    before_keys = set(before_state.keys())
    after_keys = set(after_state.keys())

    for deleted_key in sorted(before_keys - after_keys):
        removed_feature = feature_index.pop(deleted_key, None)
        callbacks.on_delete(deleted_key, removed_feature)

    for added_key in sorted(after_keys - before_keys):
        geo_object = after_state.get(added_key)
        if isinstance(geo_object, dict):
            created_feature = geo_Feature(geo_object)
            feature_index[added_key] = created_feature
            callbacks.on_create(added_key, created_feature)

    for shared_key in sorted(before_keys & after_keys):
        before_object = before_state.get(shared_key)
        after_object = after_state.get(shared_key)
        if before_object == after_object:
            continue

        if not isinstance(after_object, dict):
            removed_feature = feature_index.pop(shared_key, None)
            callbacks.on_delete(shared_key, removed_feature)
            continue

        existing = feature_index.get(shared_key)
        if existing is None:
            created_feature = geo_Feature(after_object)
            feature_index[shared_key] = created_feature
            callbacks.on_create(shared_key, created_feature)
        else:
            existing.update_from_geo_object(after_object)
            callbacks.on_update(shared_key, existing)


@dataclass
class FeatureCallbacks:
    on_create: Callable[[str, geo_Feature], None] = _default_on_create
    on_update: Callable[[str, geo_Feature], None] = _default_on_update
    on_delete: Callable[[str, geo_Feature | None], None] = _default_on_delete


def run_feature_listener(
    database_url: str,
    session_name: str,
) -> None:
    callbacks = FeatureCallbacks()
    local_geo_objects = fetch_geo_objects(database_url, session_name)
    feature_index = _build_feature_index(local_geo_objects)

    print(f"Loaded {len(local_geo_objects)} object(s) from /{session_name}/geoObjects.")
    for key in sorted(feature_index.keys()):
        feature = feature_index[key]
        print(f"[INIT] {key}: id={feature.id}, name={feature.name}")

    seen_initial_stream_snapshot = False

    while True:
        try:
            for stream_event in iter_firebase_stream(database_url, session_name):
                if stream_event.event_type in {"keep-alive", "cancel", "auth_revoked"}:
                    print(f"[INFO] Stream event: {stream_event.event_type}")
                    continue

                if stream_event.event_type not in {"put", "patch"}:
                    print(f"[INFO] Ignoring unknown stream event type: {stream_event.event_type}")
                    continue

                if not seen_initial_stream_snapshot and stream_event.path == "/":
                    seen_initial_stream_snapshot = True
                    print("[INFO] Initial stream snapshot received.")
                    continue

                before_state = json.loads(json.dumps(local_geo_objects))
                apply_stream_event(local_geo_objects, stream_event)
                _sync_feature_index(
                    feature_index,
                    before_state,
                    local_geo_objects,
                    callbacks,
                )

                print(
                    f"[STATE] geoObjects={len(local_geo_objects)} featureObjects={len(feature_index)}"
                )
        except KeyboardInterrupt:
            print("\nStopped listener.")
            return
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
