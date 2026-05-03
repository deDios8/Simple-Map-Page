"""Firebase RTDB stream initialization and local-dict synchronization.

Responsibilities:
- Dataclasses and feature models (geo_Feature, client_Request, StreamEvent, SyncChange)
- URL construction helpers
- Snapshot fetching and normalization
- Stream event parsing and application
- Feature index building and diffing
- Background stream worker thread
- DatabaseStream class: manages the clientRequests listener and exposes a change queue
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_DATABASE_URL = "https://geogm-simple-map-default-rtdb.firebaseio.com"
CLIENT_REQUESTS_NODE = "clientRequests"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


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
class StreamEvent:
    """Single parsed Firebase SSE payload."""
    event_type: str
    path: str
    data: Any


@dataclass
class SyncChange:
    """Describes one add/update/delete change derived from a stream event."""
    stream_name: str
    action: str  # "create" | "update" | "delete"
    key: str
    feature: geo_Feature | None


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def normalize_session_name(raw_value: str) -> str:
    """Mirror app.js normalizeSessionName behaviour."""
    without_slashes = raw_value.strip().strip("/")
    return without_slashes or "testBed"


def build_node_url(database_url: str, *path_segments: str) -> str:
    """Build a Firebase REST URL from path segments, appending .json."""
    base = database_url.rstrip("/")
    encoded = "/".join(quote(s, safe="") for s in path_segments)
    return f"{base}/{encoded}.json"


def build_client_requests_url(database_url: str, session_name: str) -> str:
    return build_node_url(database_url, session_name, CLIENT_REQUESTS_NODE)


# ---------------------------------------------------------------------------
# Snapshot fetching
# ---------------------------------------------------------------------------


def _normalize_objects(raw: Any) -> dict[str, dict[str, Any]]:
    """Normalize a Firebase snapshot into a string-keyed dict of objects."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    if isinstance(raw, list):
        result: dict[str, dict[str, Any]] = {}
        for i, entry in enumerate(raw):
            if not isinstance(entry, dict):
                continue
            props = entry.get("properties") or {}
            entry_id = props.get("id") or f"item-{i}"
            result[entry_id] = {**entry, "properties": {**props, "id": entry_id}}
        return result
    return {}


def _fetch_snapshot(url: str) -> dict[str, dict[str, Any]]:
    try:
        with urlopen(url) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as error:
        raise RuntimeError(f"Firebase HTTP error {error.code} for URL: {url}") from error
    except URLError as error:
        raise RuntimeError(f"Network error when contacting Firebase: {error.reason}") from error

    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError("Firebase response was not valid JSON.") from error

    return _normalize_objects(decoded)


def fetch_client_requests(database_url: str, session_name: str) -> dict[str, dict[str, Any]]:
    return _fetch_snapshot(build_client_requests_url(database_url, session_name))


# ---------------------------------------------------------------------------
# Stream event application
# ---------------------------------------------------------------------------


def _parse_path(path: str) -> list[str]:
    if not path or path == "/":
        return []
    return [s for s in path.split("/") if s]


def _get_nested(target: Any, segments: list[str]) -> Any:
    current = target
    for segment in segments:
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def _ensure_nested_dict(target: dict[str, Any], segments: list[str]) -> dict[str, Any]:
    current: dict[str, Any] = target
    for segment in segments:
        nxt = current.get(segment)
        if not isinstance(nxt, dict):
            nxt = {}
            current[segment] = nxt
        current = nxt
    return current


def _delete_nested(target: dict[str, Any], segments: list[str]) -> None:
    if not segments:
        target.clear()
        return
    if len(segments) == 1:
        target.pop(segments[0], None)
        return
    parent = _get_nested(target, segments[:-1])
    if isinstance(parent, dict):
        parent.pop(segments[-1], None)


def _set_nested(target: dict[str, Any], segments: list[str], value: Any, merge: bool) -> None:
    if not segments:
        if merge and isinstance(value, dict):
            for k, v in value.items():
                if v is None:
                    target.pop(k, None)
                else:
                    target[k] = v
        else:
            target.clear()
            if isinstance(value, dict):
                target.update(value)
        return

    parent = _ensure_nested_dict(target, segments[:-1])
    key = segments[-1]
    if merge and isinstance(value, dict):
        existing = parent.get(key)
        if not isinstance(existing, dict):
            existing = {}
            parent[key] = existing
        for ck, cv in value.items():
            if cv is None:
                existing.pop(ck, None)
            else:
                existing[ck] = cv
    else:
        parent[key] = value


def apply_stream_event(local_state: dict[str, Any], event: StreamEvent) -> None:
    segments = _parse_path(event.path)
    if event.data is None:
        _delete_nested(local_state, segments)
    else:
        _set_nested(local_state, segments, event.data, merge=(event.event_type == "patch"))


# ---------------------------------------------------------------------------
# Feature index building and diffing
# ---------------------------------------------------------------------------


def _build_feature_index(
    raw_objects: dict[str, Any],
    factory: type[geo_Feature] = geo_Feature,
) -> dict[str, geo_Feature]:
    return {k: factory(v) for k, v in raw_objects.items() if isinstance(v, dict)}


def _sync_feature_index(
    feature_index: dict[str, geo_Feature],
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    factory: type[geo_Feature] = geo_Feature,
) -> list[SyncChange]:
    changes: list[SyncChange] = []
    before_keys = set(before_state)
    after_keys = set(after_state)

    for key in sorted(before_keys - after_keys):
        removed = feature_index.pop(key, None)
        changes.append(SyncChange("", "delete", key, removed))

    for key in sorted(after_keys - before_keys):
        obj = after_state[key]
        if isinstance(obj, dict):
            created = factory(obj)
            feature_index[key] = created
            changes.append(SyncChange("", "create", key, created))

    for key in sorted(before_keys & after_keys):
        if before_state[key] == after_state[key]:
            continue
        after_obj = after_state[key]
        if not isinstance(after_obj, dict):
            removed = feature_index.pop(key, None)
            changes.append(SyncChange("", "delete", key, removed))
            continue
        existing = feature_index.get(key)
        if existing is None:
            created = factory(after_obj)
            feature_index[key] = created
            changes.append(SyncChange("", "create", key, created))
        else:
            existing.update_from_geo_object(after_obj)
            changes.append(SyncChange("", "update", key, existing))

    return changes


# ---------------------------------------------------------------------------
# Low-level SSE stream iterator
# ---------------------------------------------------------------------------


def _iter_stream_from_url(url: str):
    """Yield StreamEvent objects from a Firebase REST SSE endpoint."""
    request = Request(url, headers={"Accept": "text/event-stream"})
    with urlopen(request) as response:
        if response.status != 200:
            raise RuntimeError(f"Stream listener failed with HTTP status {response.status}.")

        event_type: str | None = None
        data_lines: list[str] = []

        for raw_line in response:
            line = raw_line.decode("utf-8").strip()

            if not line:
                if event_type and data_lines:
                    data_raw = "\n".join(data_lines)
                    try:
                        payload = json.loads(data_raw)
                    except json.JSONDecodeError:
                        event_type = None
                        data_lines = []
                        continue
                    if isinstance(payload, dict):
                        yield StreamEvent(
                            event_type=event_type,
                            path=payload.get("path", "/"),
                            data=payload.get("data"),
                        )
                event_type = None
                data_lines = []
                continue

            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())


# ---------------------------------------------------------------------------
# Background stream worker
# ---------------------------------------------------------------------------


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

    seen_initial = False
    while not stop_event.is_set():
        try:
            for event in iter_stream(database_url, session_name):
                if stop_event.is_set():
                    return
                if event.event_type in {"keep-alive", "cancel", "auth_revoked"}:
                    continue
                if event.event_type not in {"put", "patch"}:
                    continue
                if not seen_initial and event.path == "/":
                    seen_initial = True
                    continue

                before = json.loads(json.dumps(local_state))
                apply_stream_event(local_state, event)
                for change in _sync_feature_index(feature_index, before, local_state, factory=factory):
                    change.stream_name = stream_name
                    output_queue.put(change)

        except (HTTPError, URLError, RuntimeError) as error:
            print(f"[WARN] {stream_name} stream disconnected: {error}")
            print(f"[INFO] Reconnecting {stream_name} in 2 seconds...")
            time.sleep(2)


# ---------------------------------------------------------------------------
# DatabaseStream — manages the clientRequests listener thread
# ---------------------------------------------------------------------------


class DatabaseStream:
    """Manages the live clientRequests listener and exposes a change queue."""

    def __init__(self, database_url: str, session_name: str) -> None:
        self.database_url = database_url
        self.session_name = session_name
        self.request_state: dict[str, Any] = {}
        self.request_index: dict[str, client_Request] = {}
        self.event_queue: queue.Queue[SyncChange] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        def _iter(db: str, session: str):
            yield from _iter_stream_from_url(build_client_requests_url(db, session))

        self._thread = threading.Thread(
            target=_run_stream_worker,
            args=(
                self.database_url,
                self.session_name,
                CLIENT_REQUESTS_NODE,
                self.request_state,
                self.request_index,
                fetch_client_requests,
                _iter,
                client_Request,
                self.event_queue,
                self._stop_event,
            ),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
