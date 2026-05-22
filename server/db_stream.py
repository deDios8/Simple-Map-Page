"""Firebase RTDB stream initialization and local-dict synchronization.

Responsibilities:
- Dataclasses and feature models (DBEntry, ClientRequestEntry, StreamEvent, SyncChange)
- URL construction helpers
- Snapshot fetching and normalization
- Stream event parsing and application
- Feature index building and diffing
- Background stream worker thread
- DatabaseStream class: manages the clientRequests listener and exposes a change queue
"""

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
GEO_OBJECTS_NODE = "geoObjects"
CLIENT_REQUESTS_NODE = "clientRequests"
CLIENT_REQUESTS_PROCESSED_NODE = "clientRequests_processed"
EVENT_CRITERIA_NODE = "eventCriteria"

CRITERIA_COMPONENT_NAMES = frozenset({
    "CriteriaHasTags",
    "CriteriaIsWithin",
    "CriteriaJustEntered",
    "CriteriaJustExited",
    "CriteriaIsVisible",
    "CriteriaIsNotVisible",
    "CriteriaFirstEntered",
})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class DBEntry:
    def __init__(self, db_entry: dict[str, Any]) -> None:
        self.update_from_db_entry(db_entry)

    def update_from_db_entry(self, db_entry: dict[str, Any]) -> None:
        self.type = db_entry.get("type", "")
        self.geometry = db_entry.get("geometry", {})
        self.properties = db_entry.get("properties", {})
        self.id = self.properties.get("id", "")
        meta_data = self.properties.get("metaData", {}) if isinstance(self.properties.get("metaData"), dict) else {}
        self.name = meta_data.get("name", "")
        self.description = meta_data.get("description", "")
        if isinstance(self.geometry, dict):
            self.coordinates = self.geometry.get("coordinates", [])


class ClientRequestEntry(DBEntry):
    def update_from_db_entry(self, db_entry: dict[str, Any]) -> None:
        super().update_from_db_entry(db_entry)
        crp = self.properties.get("clientRequestPayload", {}) if isinstance(self.properties.get("clientRequestPayload"), dict) else {}
        self.requester_id = crp.get("requesterId", "")
        self.timestamp = crp.get("timestamp", "")
        self.request_type = crp.get("type", "")
        self.requested_action = crp.get("requestedAction", "")
        self.target_id = crp.get("targetId", "")
        self.target_path = crp.get("targetPath", "")
        self.form_data = self.properties.get("formData", {}) if isinstance(self.properties.get("formData"), dict) else {}


def normalize_stats(properties: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(properties, dict):
        return {}
    stats_value = properties.get("stats")
    if isinstance(stats_value, dict):
        normalized_stats: dict[str, dict[str, Any]] = {}
        for key, raw_stat in stats_value.items():
            if not isinstance(raw_stat, dict):
                continue
            stat_key = str(key).strip() or str(raw_stat.get("name", "")).strip()
            if not stat_key:
                continue
            normalized_stats[stat_key] = {
                "name": str(raw_stat.get("name", "") or ""),
                "value": raw_stat.get("value", 0),
                "max_value": raw_stat.get("max_value", 100),
                "min_value": raw_stat.get("min_value", 0),
            }
        if normalized_stats:
            return normalized_stats

    return {}



def to_bool(value: object, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    if isinstance(value, (int, float)):
        return value != 0
    return fallback


def normalize_visible(value: object) -> list[str]:
    """Normalize a ``visible`` field to a list of permission-key strings.

    Each string in the list is a stat *name* value; a geo object is rendered
    for the current user only when the user's own geo object has at least one
    stat whose ``name`` field matches (case-insensitively) one of the entries.
    """
    if isinstance(value, list):
        return [str(s) for s in value if isinstance(s, str) and s.strip()]
    if isinstance(value, str) and value.strip():
        return [s.strip() for s in value.split(",") if s.strip()]
    return []


def normalize_traits(value: object) -> list[str]:
    """Normalize a ``traits`` field to a list of trait strings."""
    if isinstance(value, list):
        return [str(s) for s in value if isinstance(s, str) and s.strip()]
    if isinstance(value, str) and value.strip():
        return [s.strip() for s in value.split(",") if s.strip()]
    return []


def to_float(value: object, fallback: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


class GeoObjectEntry(DBEntry):
    def update_from_db_entry(self, db_entry: dict[str, Any]) -> None:
        super().update_from_db_entry(db_entry)

        self.appearance = self.properties.get("appearance", {})
        self.radius = self.appearance.get("radius", 2) if isinstance(self.appearance, dict) else 2
        self.color = self.appearance.get("color", "#000000") if isinstance(self.appearance, dict) else "#000000"
        self.visible = normalize_visible(self.appearance.get("visible", [])) if isinstance(self.appearance, dict) else []

        meta_data = self.properties.get("metaData", {}) if isinstance(self.properties.get("metaData"), dict) else {}
        self.name = meta_data.get("name", "")
        self.description = meta_data.get("description", "")
        
        self.stats = normalize_stats(self.properties)

        self.traits = normalize_traits(self.properties.get("traits", []))

        self.data = self.properties.get("data", {})


class CriteriaEntry(DBEntry):
    def update_from_db_entry(self, db_entry: dict[str, Any]) -> None:
        super().update_from_db_entry(db_entry)
        self.criteria_components: dict[str, dict] = {}
        for key, value in self.properties.items():
            if key in CRITERIA_COMPONENT_NAMES and isinstance(value, dict):
                self.criteria_components[key] = value
        all_met = self.properties.get("ObjectsThatMetAllCriteria", {})
        self.objects_that_met_all: list = all_met.get("object_ids", []) if isinstance(all_met, dict) else []
        any_met = self.properties.get("ObjectsThatMetAnyCriteria", {})
        self.objects_that_met_any: list = any_met.get("object_ids", []) if isinstance(any_met, dict) else []


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
    feature: DBEntry | None


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def build_node_url(database_url: str, *path_segments: str) -> str:
    """Build a Firebase REST URL from path segments, appending .json."""
    base = database_url.rstrip("/")
    encoded = "/".join(quote(s, safe="") for s in path_segments)
    return f"{base}/{encoded}.json"


def build_client_requests_url(database_url: str, session_name: str) -> str:
    return build_node_url(database_url, session_name, CLIENT_REQUESTS_NODE)


def build_geo_objects_url(database_url: str, session_name: str) -> str:
    return build_node_url(database_url, session_name, GEO_OBJECTS_NODE)


def build_event_criteria_url(database_url: str, session_name: str) -> str:
    return build_node_url(database_url, session_name, EVENT_CRITERIA_NODE)


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


def fetch_geo_objects(database_url: str, session_name: str) -> dict[str, dict[str, Any]]:
    return _fetch_snapshot(build_geo_objects_url(database_url, session_name))


def fetch_event_criteria(database_url: str, session_name: str) -> dict[str, dict[str, Any]]:
    return _fetch_snapshot(build_event_criteria_url(database_url, session_name))


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
                elif "/" in k:
                    # Firebase multi-path key (e.g. "properties/stats"): treat
                    # the slash as a path separator and recurse rather than
                    # setting a literal slash-keyed entry in the dict.
                    sub_segs = [s for s in k.split("/") if s]
                    _set_nested(target, sub_segs, v, merge=False)
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
            elif "/" in ck:
                # Same multi-path handling one level down.
                sub_segs = [s for s in ck.split("/") if s]
                _set_nested(existing, sub_segs, cv, merge=False)
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
    factory: type[DBEntry] = DBEntry,
) -> dict[str, DBEntry]:
    return {k: factory(v) for k, v in raw_objects.items() if isinstance(v, dict)}


def _sync_feature_index(
    feature_index: dict[str, DBEntry],
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    factory: type[DBEntry] = DBEntry,
    stream_name: str = "",
) -> list[SyncChange]:
    changes: list[SyncChange] = []
    before_keys = set(before_state)
    after_keys = set(after_state)

    for key in sorted(before_keys - after_keys):
        removed = feature_index.pop(key, None)
        changes.append(SyncChange(stream_name, "delete", key, removed))

    for key in sorted(after_keys - before_keys):
        obj = after_state[key]
        if isinstance(obj, dict):
            created = factory(obj)
            feature_index[key] = created
            changes.append(SyncChange(stream_name, "create", key, created))

    for key in sorted(before_keys & after_keys):
        if before_state[key] == after_state[key]:
            continue
        after_obj = after_state[key]
        if not isinstance(after_obj, dict):
            removed = feature_index.pop(key, None)
            changes.append(SyncChange(stream_name, "delete", key, removed))
            continue
        existing = feature_index.get(key)
        if existing is None:
            created = factory(after_obj)
            feature_index[key] = created
            changes.append(SyncChange(stream_name, "create", key, created))
        else:
            existing.update_from_db_entry(after_obj)
            changes.append(SyncChange(stream_name, "update", key, existing))

    return changes


# ---------------------------------------------------------------------------
# DB write helpers
# ---------------------------------------------------------------------------


def put_db_entry(
    database_url: str, session_name: str, key: str, db_entry: dict[str, Any], NODE: str = GEO_OBJECTS_NODE
) -> None:
    """Write (overwrite) a single geoObject entry by key."""
    url = build_node_url(database_url, session_name, NODE, key)
    data = json.dumps(db_entry).encode("utf-8")
    req = Request(url, data=data, method="PUT", headers={"Content-Type": "application/json"})
    with urlopen(req) as response:
        response.read()


def patch_db_entry(
    database_url: str, session_name: str, key: str, fields: dict[str, Any], node: str = GEO_OBJECTS_NODE
) -> None:
    """Merge-update specific fields of a database entry by key."""

    url = build_node_url(database_url, session_name, node, key)
    data = json.dumps(fields).encode("utf-8")
    req = Request(url, data=data, method="PATCH", headers={"Content-Type": "application/json"})
    with urlopen(req) as response:
        response.read()


def delete_db_entry(database_url: str, session_name: str, key: str, node: str = GEO_OBJECTS_NODE) -> None:
    """Delete a geoObject entry by key."""
    url = build_node_url(database_url, session_name, node, key)
    req = Request(url, method="DELETE")
    with urlopen(req) as response:
        response.read()


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
            # if event_type and not "keep-alive" in event_type:
            #     print(f"PARSED SSE LINE: '{line}' (event_type={event_type}, data_lines={data_lines})")

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
    feature_index: dict[str, DBEntry],
    fetch_snapshot: Callable[[str, str], dict[str, dict[str, Any]]],
    iter_stream: Callable[[str, str], Any],
    factory: type[DBEntry],
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
                for change in _sync_feature_index(feature_index, before, local_state, factory=factory, stream_name=stream_name):
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
        self.geo_object_state: dict[str, Any] = {}
        self.criteria_state: dict[str, Any] = {}
        self.request_index: dict[str, ClientRequestEntry] = {}
        self.geo_object_index: dict[str, GeoObjectEntry] = {}
        self.criteria_index: dict[str, CriteriaEntry] = {}
        self.event_queue: queue.Queue[SyncChange] = queue.Queue()
        self._stop_event = threading.Event()
        self._client_request_thread: threading.Thread | None = None
        self._geo_object_thread: threading.Thread | None = None
        self._criteria_thread: threading.Thread | None = None

    def start(self) -> None:
        def _iter_client_requests(db: str, session: str):
            yield from _iter_stream_from_url(build_client_requests_url(db, session))

        def _iter_geo_objects(db: str, session: str):
            yield from _iter_stream_from_url(build_geo_objects_url(db, session))

        def _iter_event_criteria(db: str, session: str):
            yield from _iter_stream_from_url(build_event_criteria_url(db, session))

        self._client_request_thread = threading.Thread(
            target=_run_stream_worker,
            args=(
                self.database_url,
                self.session_name,
                CLIENT_REQUESTS_NODE,
                self.request_state,
                self.request_index,
                fetch_client_requests,
                _iter_client_requests,
                ClientRequestEntry,
                self.event_queue,
                self._stop_event,
            ),
            daemon=True,
        )

        self._geo_object_thread = threading.Thread(
            target=_run_stream_worker,
            args=(
                self.database_url,
                self.session_name,
                GEO_OBJECTS_NODE,
                self.geo_object_state,
                self.geo_object_index,
                fetch_geo_objects,
                _iter_geo_objects,
                GeoObjectEntry,
                self.event_queue,
                self._stop_event,
            ),
            daemon=True,
        )

        self._criteria_thread = threading.Thread(
            target=_run_stream_worker,
            args=(
                self.database_url,
                self.session_name,
                EVENT_CRITERIA_NODE,
                self.criteria_state,
                self.criteria_index,
                fetch_event_criteria,
                _iter_event_criteria,
                CriteriaEntry,
                self.event_queue,
                self._stop_event,
            ),
            daemon=True,
        )

        self._client_request_thread.start()
        self._geo_object_thread.start()
        self._criteria_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
