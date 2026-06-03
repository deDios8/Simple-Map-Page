"""
Firebase RTDB stream initialization and local-dict synchronization.
"""

import json
import pathlib
import queue
import threading
import time
import random
import string
import esper
import ecs_comps_geo
import ecs_comps_event
import ecs_comps_client_request
from typing import Any, Callable
from dataclasses import dataclass
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from debug_console import SessionDebugConsole


_PUBLIC_DIR = pathlib.Path(__file__).parent.parent / "public"
_online_config: dict = json.loads((_PUBLIC_DIR / "online_config.json").read_text())
_nodes: dict = _online_config["nodes"]

DEFAULT_DATABASE_URL = _online_config["databaseURL"]
GEO_OBJECTS_NODE = _nodes["geoObjects"]
CLIENT_REQUESTS_NODE = _nodes["clientRequests"]
CLIENT_REQUESTS_PROCESSED_NODE = _nodes["clientRequestsProcessed"]
EVENT_CRITERIA_NODE = _nodes["eventCriteria"]
EVENTS_NODE = _nodes["events"]


def build_node_url(database_url: str, *path_segments: str) -> str:
    """Build a Firebase REST URL from path segments, appending .json."""
    base = database_url.rstrip("/")
    encoded = "/".join(quote(s, safe="") for s in path_segments)
    return f"{base}/{encoded}.json"


# ---------------------------------------------------------------------------
# Dataclasses and feature models 
# ---------------------------------------------------------------------------


class DBEntry:
    def __init__(self, db_entry: dict[str, Any]) -> None:
        self.update_from_db_entry(db_entry)

    def update_from_db_entry(self, db_entry: dict[str, Any]) -> None:
        self.type = db_entry.get("type", "")
        self.geometry = db_entry.get("geometry", {})
        self.properties = db_entry.get("properties", {})
        self.id = self.properties.get("id", "")
        self.name = self.properties.get("displayName", "") if isinstance(self.properties, dict) else ""
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


class GeoObjectEntry(DBEntry):
    def update_from_db_entry(self, db_entry: dict[str, Any]) -> None:
        super().update_from_db_entry(db_entry)

        self.appearance = self.properties.get("appearance", {})
        self.radius = self.appearance.get("radius", 2) if isinstance(self.appearance, dict) else 2
        self.color = self.appearance.get("color", "#000000") if isinstance(self.appearance, dict) else "#000000"
        self.visible_to = normalize_string_list(self.appearance.get("visibleTo", [])) if isinstance(self.appearance, dict) else []

        self.name = self.properties.get("displayName", "") if isinstance(self.properties, dict) else ""
        
        self.stats = normalize_stats(self.properties)

        self.traits = normalize_string_list(self.properties.get("traits", []))

        self.messages = normalize_messages(self.properties)

        self.data = self.properties.get("data", {})


class EventResultEntry(DBEntry):
    def update_from_db_entry(self, db_entry: dict[str, Any]) -> None:
        super().update_from_db_entry(db_entry)
        triggers = self.properties.get("Triggers", {}) if isinstance(self.properties, dict) else {}
        self.trigger_components: dict[str, dict] = {
            k: v for k, v in triggers.items()
            if k in ecs_comps_event.TRIGGER_COMPONENT_NAMES and isinstance(v, dict)
        } if isinstance(triggers, dict) else {}
        targets = self.properties.get("Targets", {}) if isinstance(self.properties, dict) else {}
        self.target_components: dict[str, dict] = {
            k: v for k, v in targets.items()
            if k in ecs_comps_event.TARGET_COMPONENT_NAMES and isinstance(v, dict)
        } if isinstance(targets, dict) else {}
        results = self.properties.get("Results", {})
        self.result_components: dict[str, dict] = {
            k: v for k, v in results.items()
            if k in ecs_comps_event.EVENT_RESULT_COMPONENT_NAMES and isinstance(v, dict)
        } if isinstance(results, dict) else {}


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
# Snapshot fetching and normalization helpers
# ---------------------------------------------------------------------------


def to_float(value: object, fallback: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


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


def normalize_string_list(value: object) -> list[str]:
    """Normalize a field to a list of non-empty strings.

    Accepts a list of strings or a comma-separated string.
    """
    if isinstance(value, list):
        return [str(s) for s in value if isinstance(s, str) and s.strip()]
    if isinstance(value, str) and value.strip():
        return [s.strip() for s in value.split(",") if s.strip()]
    return []


def normalize_messages(properties: Any) -> list[str]:
    """Return the messages list from a properties dict, filtering to non-empty strings."""
    if not isinstance(properties, dict):
        return []
    value = properties.get("messages", [])
    if isinstance(value, list):
        return [str(m) for m in value if isinstance(m, str) and m]
    return []


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


def fetch_node(database_url: str, session_name: str, node: str) -> dict[str, dict[str, Any]]:
    url = build_node_url(database_url, session_name, node)
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


def multi_path_patch(
    database_url: str, session_name: str, multi_path_payload: dict[str, Any]
) -> None:
    """Apply a multi-location update at the session root level in a single request.

    Keys in multi_path_payload are slash-separated paths relative to the session node
    (e.g. "geoObjects/Mob/properties/traits").
    """
    url = build_node_url(database_url, session_name)
    data = json.dumps(multi_path_payload).encode("utf-8")
    req = Request(url, data=data, method="PATCH", headers={"Content-Type": "application/json"})
    with urlopen(req) as response:
        response.read()


def delete_db_entry(
    database_url: str, session_name: str, key: str, node: str = GEO_OBJECTS_NODE) -> None:
    """Delete a geoObject entry by key."""
    url = build_node_url(database_url, session_name, node, key)
    req = Request(url, method="DELETE")
    with urlopen(req) as response:
        response.read()


# ---------------------------------------------------------------------------
# Listener thread managers and stream worker
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


class DatabaseStream:
    """Manages the live clientRequests listener and exposes a change queue."""

    def __init__(self, database_url: str, session_name: str) -> None:
        self.database_url = database_url
        self.session_name = session_name
        self.request_state: dict[str, Any] = {}
        self.geo_object_state: dict[str, Any] = {}
        self.request_index: dict[str, ClientRequestEntry] = {}
        self.geo_object_index: dict[str, GeoObjectEntry] = {}
        self.event_results_state: dict[str, Any] = {}
        self.event_results_index: dict[str, EventResultEntry] = {}
        self.event_queue: queue.Queue[SyncChange] = queue.Queue()
        self._stop_event = threading.Event()
        self._client_request_thread: threading.Thread | None = None
        self._geo_object_thread: threading.Thread | None = None
        self._event_results_thread: threading.Thread | None = None

    def start(self) -> None:
        _streams = [
            (CLIENT_REQUESTS_NODE, self.request_state,       self.request_index,       ClientRequestEntry, "_client_request_thread"),
            # (GEO_OBJECTS_NODE,     self.geo_object_state,    self.geo_object_index,    GeoObjectEntry,     "_geo_object_thread"),
            # (EVENTS_NODE,         self.event_results_state, self.event_results_index, EventResultEntry,   "_event_results_thread"),
        ]
        for node, state, index, factory, attr in _streams:
            fetch_fn = lambda db, session, n=node: fetch_node(db, session, n)
            iter_fn = lambda db, session, n=node: _iter_stream_from_url(build_node_url(db, session, n))
            t = threading.Thread(
                target=_run_stream_worker,
                args=(self.database_url, self.session_name, node, state, index,
                      fetch_fn, iter_fn, factory, self.event_queue, self._stop_event),
                daemon=True,
            )
            setattr(self, attr, t)
            t.start()

    def stop(self) -> None:
        self._stop_event.set()


class SessionState:
    def __init__(self, database_url: str, session_name: str) -> None:
        self.database_url = database_url
        self.session_name = session_name.strip().strip("/") or "testBed"

        # Keep dict-backed state so Firebase keys can map directly to ECS entities.
        self.GeoObjects: dict[str, ecs_comps_geo.GeoObject] = {}
        self.ClientRequests: dict[str, ecs_comps_client_request.ClientRequest] = {}
        self.GeoObjectEntityIds: dict[str, int] = {}
        self.ClientRequestEntityIds: dict[str, int] = {}
        self.EventResults: dict[str, ecs_comps_event.Event] = {}
        self.EventResultEntityIds: dict[str, int] = {}

        self.stream = DatabaseStream(self.database_url, self.session_name)
        self.debug = SessionDebugConsole(self)
        self._initialize_from_snapshot()

    def _random_string(self, length: int = 2) -> str:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    def _sync_zone_component_from_payload(
        self,
        entity_id: int,
        payload: dict,
        payload_key: str,
        component_type: type,
    ) -> None:
        entry = payload.get(payload_key)
        zone_ids = normalize_string_list(entry.get("zone_ids")) if isinstance(entry, dict) else None
        if zone_ids is None:
            try:
                esper.remove_component(entity_id, component_type)
            except KeyError:
                pass
            return
        esper.add_component(entity_id, component_type(zone_ids=zone_ids))

    def _apply_zone_borders_from_properties(self, entity_id: int, props: dict) -> None:
        zone_borders = props.get("zoneBorders") if isinstance(props, dict) else None
        payload = zone_borders if isinstance(zone_borders, dict) else {}
        self._sync_zone_component_from_payload(
            entity_id,
            payload,
            "withinZones",
            ecs_comps_geo.WithinZones,
        )
        self._sync_zone_component_from_payload(
            entity_id,
            payload,
            "enteredZones",
            ecs_comps_geo.EnteredZones,
        )
        self._sync_zone_component_from_payload(
            entity_id,
            payload,
            "exitedZones",
            ecs_comps_geo.ExitedZones,
        )

    def _sync_stats_component(self, entity_id: int, props: object) -> dict[str, dict]:
        normalized_stats = normalize_stats(props)
        stats_component = esper.try_component(entity_id, ecs_comps_geo.Stats)
        if normalized_stats:
            if stats_component is None:
                esper.add_component(entity_id, ecs_comps_geo.Stats(items=normalized_stats))
            else:
                stats_component.items = normalized_stats
        elif stats_component is not None:
            esper.remove_component(entity_id, ecs_comps_geo.Stats)

        return normalized_stats

    def _sync_messages_component(self, entity_id: int, props: object) -> list[str]:
        normalized_messages = normalize_messages(props)
        messages_component = esper.try_component(entity_id, ecs_comps_geo.Messages)
        if normalized_messages:
            if messages_component is None:
                esper.add_component(entity_id, ecs_comps_geo.Messages(messages=normalized_messages))
            else:
                messages_component.messages = normalized_messages
        elif messages_component is not None:
            try:
                esper.remove_component(entity_id, ecs_comps_geo.Messages)
            except KeyError:
                pass
        return normalized_messages

    def _sync_traits_component(self, entity_id: int, props: object) -> list[str]:
        traits_value = props.get("traits", []) if isinstance(props, dict) else []
        normalized_traits = normalize_string_list(traits_value)
        traits_component = esper.try_component(entity_id, ecs_comps_geo.Traits)
        if normalized_traits:
            if traits_component is None:
                esper.add_component(entity_id, ecs_comps_geo.Traits(traits=normalized_traits))
            else:
                traits_component.traits = normalized_traits
        elif traits_component is not None:
            esper.remove_component(entity_id, ecs_comps_geo.Traits)

        return normalized_traits

    def _initialize_from_snapshot(self) -> None:
        _nodes = [
            (GEO_OBJECTS_NODE,     GeoObjectEntry,     self._upsert_geo_object_entity),
            (CLIENT_REQUESTS_NODE, ClientRequestEntry, self._upsert_client_request_entity),
            (EVENTS_NODE,          EventResultEntry,   self._upsert_event_entity),
        ]
        for node, entry_class, upsert_fn in _nodes:
            for key, raw in fetch_node(self.database_url, self.session_name, node).items():
                upsert_fn(key, entry_class(raw))

    def _extract_geo_key_from_target_path(self, target_path: str) -> str:
        if not isinstance(target_path, str):
            return ""

        segments = [segment for segment in target_path.strip().split("/") if segment]
        if not segments:
            return ""

        if GEO_OBJECTS_NODE in segments:
            index = segments.index(GEO_OBJECTS_NODE)
            if index + 1 < len(segments):
                return segments[index + 1]

        return segments[-1]

    def _consume_client_request(self, request_entity_id: int) -> None:
        for component_type in (
            ecs_comps_client_request.NewLocation,
            ecs_comps_client_request.EditedObject,
            ecs_comps_client_request.DeletedObject,
            ecs_comps_client_request.AddEvent,
            ecs_comps_client_request.EditedEvent,
            ecs_comps_client_request.DeletedEvent,
        ):
            try:
                esper.remove_component(request_entity_id, component_type)
            except KeyError:
                pass

        request_key: str | None = None
        for key, entity_id in self.ClientRequestEntityIds.items():
            if entity_id == request_entity_id:
                request_key = key
                break

        if request_key is not None:
            # Evict from tracking dicts immediately so _sync_dirty_zone_borders_to_database
            # cannot patch this key back into clientRequests after it is deleted.
            self.ClientRequestEntityIds.pop(request_key, None)
            self.ClientRequests.pop(request_key, None)

        # Remove the ECS entity now so zone processors don't act on it again.
        try:
            esper.delete_entity(request_entity_id)
        except Exception:
            pass

        if request_key is not None:
            try:
                raw_entry = self.stream.request_state.get(request_key)
                if isinstance(raw_entry, dict):
                    put_db_entry(
                        self.database_url,
                        self.session_name,
                        request_key,
                        raw_entry,
                        NODE=CLIENT_REQUESTS_PROCESSED_NODE,
                    )
                delete_db_entry(
                    self.database_url,
                    self.session_name,
                    request_key,
                    node=CLIENT_REQUESTS_NODE,
                )
            except Exception as error:
                print(f"[REQUEST CONSUME ERROR] {request_key}: {error}")

    def apply_new_location_request(self, request_entity_id: int) -> None:
        request_geometry = esper.try_component(request_entity_id, ecs_comps_geo.Geometry)
        request_props = esper.try_component(request_entity_id, ecs_comps_client_request.ClientRequestPayload)
        if request_geometry is None or request_props is None:
            self._consume_client_request(request_entity_id)
            return

        coordinates = request_geometry.coordinates
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            self._consume_client_request(request_entity_id)
            return

        requester_id = str(request_props.requester_id or "").strip()
        if not requester_id:
            self._consume_client_request(request_entity_id)
            return

        lon = coordinates[0]
        lat = coordinates[1]
        try:
            lon = float(lon)
            lat = float(lat)
        except (TypeError, ValueError):
            self._consume_client_request(request_entity_id)
            return

        target_key = self._find_key_by_identifier(self.GeoObjectEntityIds, requester_id) or requester_id
        target_entity_id = self.GeoObjectEntityIds.get(target_key)

        if target_entity_id is None:
            new_user_entry = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
                "properties": {
                    "id": requester_id,
                    "displayName": requester_id,
                    "appearance": {
                        "color": "#000000",
                        "visibleTo": ["USER"],
                        "radius": 2,
                    },
                    "traits": ["USER"],
                    "stats": {},
                },
            }
            put_db_entry(
                self.database_url,
                self.session_name,
                target_key,
                new_user_entry,
                NODE=GEO_OBJECTS_NODE,
            )
            target_entity_id = self._upsert_geo_object_entity(target_key, GeoObjectEntry(new_user_entry))

        geometry = esper.component_for_entity(target_entity_id, ecs_comps_geo.Geometry)
        geometry.coordinates = [lon, lat]
        esper.add_component(target_entity_id, ecs_comps_geo.GeoObjectDirty())

        patch_db_entry(
            self.database_url,
            self.session_name,
            target_key,
            {"geometry/coordinates": [lon, lat]},
            node=GEO_OBJECTS_NODE,
        )
        self._consume_client_request(request_entity_id)

    def apply_add_object_request(self, request_entity_id: int) -> None:
        request_geometry = esper.try_component(request_entity_id, ecs_comps_geo.Geometry)
        request_props = esper.try_component(request_entity_id, ecs_comps_client_request.ClientRequestPayload)
        if request_geometry is None or request_props is None:
            self._consume_client_request(request_entity_id)
            return

        coordinates = request_geometry.coordinates
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            self._consume_client_request(request_entity_id)
            return

        requester_id = str(request_props.requester_id or "").strip()
        if not requester_id:
            self._consume_client_request(request_entity_id)
            return

        try:
            lon = float(coordinates[0])
            lat = float(coordinates[1])
        except (TypeError, ValueError):
            self._consume_client_request(request_entity_id)
            return

        new_object_key = f"Zone{self._random_string()}"
        if new_object_key in self.GeoObjectEntityIds:
            new_object_key = f"{new_object_key}_{self._random_string(3)}"

        new_object_entry = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "id": new_object_key,
                "displayName": f"{new_object_key}",
                "appearance": {
                    "color": "#0b8f87",
                    "visibleTo": ["USER"],
                    "radius": 5,
                },
                "traits": ["ZONE"],
                "stats": {},
            },
        }

        put_db_entry(
            self.database_url,
            self.session_name,
            new_object_key,
            new_object_entry,
            NODE=GEO_OBJECTS_NODE,
        )
        self._upsert_geo_object_entity(new_object_key, GeoObjectEntry(new_object_entry))
        self._consume_client_request(request_entity_id)

    def apply_edited_object_request(self, request_entity_id: int) -> None:
        edited = esper.try_component(request_entity_id, ecs_comps_client_request.EditedObject)
        if edited is None:
            self._consume_client_request(request_entity_id)
            return

        target_key = (
            self._find_key_by_identifier(self.GeoObjectEntityIds, edited.target_id)
            or self._find_key_by_identifier(self.GeoObjectEntityIds, self._extract_geo_key_from_target_path(edited.target_path))
        )
        if target_key is None:
            self._consume_client_request(request_entity_id)
            return

        target_entity_id = self.GeoObjectEntityIds.get(target_key)
        if target_entity_id is None:
            self._consume_client_request(request_entity_id)
            return

        form_data = edited.form_data if isinstance(edited.form_data, dict) else {}

        display_name_comp = esper.component_for_entity(target_entity_id, ecs_comps_geo.DisplayName)
        appearance = esper.component_for_entity(target_entity_id, ecs_comps_geo.Appearance)
        geometry = esper.component_for_entity(target_entity_id, ecs_comps_geo.Geometry)

        display_name_comp.display_name = str(form_data.get("name", display_name_comp.display_name) or display_name_comp.display_name)

        appearance.color = str(form_data.get("color", appearance.color) or appearance.color)
        appearance.radius = to_float(form_data.get("radius"), float(appearance.radius))

        appearance_visible = normalize_string_list(form_data.get("visibleTo")) if "visibleTo" in form_data else appearance.visible_to
        appearance.visible_to = appearance_visible

        traits_component = esper.try_component(target_entity_id, ecs_comps_geo.Traits)
        current_traits = traits_component.traits if traits_component is not None else []
        next_traits = normalize_string_list(form_data.get("traits")) if "traits" in form_data else current_traits
        self._sync_traits_component(target_entity_id, {"traits": next_traits})

        lat = to_float(form_data.get("latitude"), float(geometry.coordinates[1]))
        lon = to_float(form_data.get("longitude"), float(geometry.coordinates[0]))
        geometry.coordinates = [lon, lat]
        esper.add_component(target_entity_id, ecs_comps_geo.GeoObjectDirty())

        stats_payload = form_data.get("stats") if isinstance(form_data.get("stats"), dict) else {}
        next_stats_payload = normalize_stats({"stats": stats_payload})

        self._sync_stats_component(target_entity_id, {"stats": next_stats_payload})

        extra_data = form_data.get("extraData")
        if not isinstance(extra_data, dict):
            extra_data = {}

        patch_db_entry(
            self.database_url,
            self.session_name,
            target_key,
            {
                "geometry/coordinates": [lon, lat],
                "properties/displayName": display_name_comp.display_name,
                "properties/appearance/color": appearance.color,
                "properties/appearance/radius": appearance.radius,
                "properties/appearance/visibleTo": appearance_visible,
                "properties/traits": next_traits,
                "properties/data": extra_data,
                "properties/stats": next_stats_payload,
            },
            node=GEO_OBJECTS_NODE,
        )

        # Mirror the patched values into the stream's local state so that the
        # echo stream event Firebase sends back does not revert the ECS update.
        # Without this, partial stream events (e.g. only geometry arriving first)
        # would call _upsert_geo_object_entity with stale properties and undo the
        # stats/statuses change that was just applied above.
        stream_obj = self.stream.geo_object_state.get(target_key)
        if isinstance(stream_obj, dict):
            geo = stream_obj.setdefault("geometry", {})
            if isinstance(geo, dict):
                geo["coordinates"] = [lon, lat]
            props = stream_obj.setdefault("properties", {})
            if isinstance(props, dict):
                props["displayName"] = display_name_comp.display_name
                appr = props.setdefault("appearance", {})
                if isinstance(appr, dict):
                    appr["color"] = appearance.color
                    appr["radius"] = appearance.radius
                    appr["visibleTo"] = appearance_visible
                props["traits"] = next_traits
                props["data"] = extra_data
                if next_stats_payload:
                    props["stats"] = next_stats_payload
                else:
                    props.pop("stats", None)

        self._consume_client_request(request_entity_id)

    def apply_deleted_object_request(self, request_entity_id: int) -> None:
        deleted = esper.try_component(request_entity_id, ecs_comps_geo.DeletedObject)
        if deleted is None:
            self._consume_client_request(request_entity_id)
            return

        target_key = (
            self._find_key_by_identifier(self.GeoObjectEntityIds, deleted.target_id)
            or self._find_key_by_identifier(self.GeoObjectEntityIds, self._extract_geo_key_from_target_path(deleted.target_path))
        )
        if target_key is None:
            self._consume_client_request(request_entity_id)
            return

        self._delete_tracked_entity(self.GeoObjectEntityIds, self.GeoObjects, target_key)
        delete_db_entry(
            self.database_url,
            self.session_name,
            target_key,
            node=GEO_OBJECTS_NODE,
        )
        self._consume_client_request(request_entity_id)

    def apply_dismiss_message_request(self, request_entity_id: int) -> None:
        dismiss = esper.try_component(request_entity_id, ecs_comps_client_request.DismissMessage)
        if dismiss is None:
            self._consume_client_request(request_entity_id)
            return

        target_key = self._find_key_by_identifier(self.GeoObjectEntityIds, dismiss.target_id)
        if target_key is None:
            self._consume_client_request(request_entity_id)
            return

        target_entity_id = self.GeoObjectEntityIds.get(target_key)
        if target_entity_id is None:
            self._consume_client_request(request_entity_id)
            return

        messages = esper.try_component(target_entity_id, ecs_comps_geo.Messages)
        if messages is not None and dismiss.message in messages.messages:
            messages.messages.remove(dismiss.message)
            esper.add_component(target_entity_id, ecs_comps_geo.GeoObjectDirty())

        self._consume_client_request(request_entity_id)

    def _upsert_geo_object_entity(self, key: str, geo_object: GeoObjectEntry) -> int:
        existing_entity_id = self.GeoObjectEntityIds.get(key)
        if existing_entity_id is None:
            geo = ecs_comps_geo.GeoObject(
                id=geo_object.id or key,
                geometry=geo_object.geometry,
                properties=geo_object.properties,
            )
            self.GeoObjects[key] = geo
            self.GeoObjectEntityIds[key] = geo.entity_id
            self._apply_zone_borders_from_properties(geo.entity_id, geo_object.properties)
            self._sync_stats_component(geo.entity_id, geo_object.properties)
            self._sync_traits_component(geo.entity_id, geo_object.properties)
            self._sync_messages_component(geo.entity_id, geo_object.properties)

            return geo.entity_id

        props = geo_object.properties if isinstance(geo_object.properties, dict) else {}

        id_component = esper.component_for_entity(existing_entity_id, ecs_comps_geo.ID)
        id_component.id = props.get("id", geo_object.id or key)

        display_name_comp = esper.component_for_entity(existing_entity_id, ecs_comps_geo.DisplayName)
        display_name_comp.display_name = props.get("displayName", "")

        appearance = esper.component_for_entity(existing_entity_id, ecs_comps_geo.Appearance)
        appearance_data = props.get("appearance", {}) if isinstance(props.get("appearance"), dict) else {}
        appearance.color = appearance_data.get("color", "")
        appearance.shape = appearance_data.get("shape", "")
        appearance.radius = appearance_data.get("radius", 0)
        appearance.visible_to = normalize_string_list(appearance_data.get("visibleTo", []))

        geometry = esper.component_for_entity(existing_entity_id, ecs_comps_geo.Geometry)
        geometry.coordinates = geo_object.geometry.get("coordinates", [0, 0])
        self._sync_stats_component(existing_entity_id, props)
        self._sync_traits_component(existing_entity_id, props)
        self._sync_messages_component(existing_entity_id, props)
        
        return existing_entity_id

    def _attach_request_marker_component(
        self,
        entity_id: int,
        request_type: str,
        requested_action: str,
        requester_id: str,
        target_id: str,
        target_path: str,
        form_data: dict,
    ) -> None:
        if requested_action == "new_location":
            esper.add_component(entity_id, ecs_comps_client_request.NewLocation(requester_id=requester_id))
        elif requested_action == "add_object":
            esper.add_component(entity_id, ecs_comps_client_request.AddObject(requester_id=requester_id))
        elif request_type == "edited_object":
            esper.add_component(entity_id, ecs_comps_client_request.EditedObject(target_id=target_id, target_path=target_path, form_data=form_data))
        elif request_type == "deleted_object":
            esper.add_component(entity_id, ecs_comps_client_request.DeletedObject(target_id=target_id, target_path=target_path))
        elif requested_action == "add_event":
            esper.add_component(entity_id, ecs_comps_client_request.AddEvent(requester_id=requester_id))
        elif request_type == "edited_event":
            esper.add_component(entity_id, ecs_comps_client_request.EditedEvent(target_id=target_id, form_data=form_data))
        elif request_type == "deleted_event":
            esper.add_component(entity_id, ecs_comps_client_request.DeletedEvent(target_id=target_id))
        elif request_type == "dismiss_message":
            esper.add_component(entity_id, ecs_comps_client_request.DismissMessage(
                target_id=target_id,
                message=form_data.get("message", ""),
            ))

    def _upsert_client_request_entity(self, key: str, request: ClientRequestEntry) -> int:
        existing_entity_id = self.ClientRequestEntityIds.get(key)
        if existing_entity_id is None:
            entity = ecs_comps_client_request.ClientRequest(
                id=request.id or key,
                geometry=request.geometry,
                properties=request.properties,
            )
            self.ClientRequests[key] = entity
            self.ClientRequestEntityIds[key] = entity.entity_id
            request_params = esper.component_for_entity(entity.entity_id, ecs_comps_client_request.ClientRequestPayload)
            self._attach_request_marker_component(
                entity.entity_id,
                request_type=str(request_params.request_type or "").strip().lower(),
                requested_action=str(request_params.requested_action or "").strip().lower(),
                requester_id=request_params.requester_id,
                target_id=request.target_id,
                target_path=request.target_path,
                form_data=request.form_data if isinstance(request.form_data, dict) else {},
            )
            self._apply_zone_borders_from_properties(entity.entity_id, request.properties)
            return entity.entity_id

        props = request.properties if isinstance(request.properties, dict) else {}

        id_component = esper.component_for_entity(existing_entity_id, ecs_comps_geo.ID)
        id_component.id = props.get("id", request.id or key)

        geometry = esper.component_for_entity(existing_entity_id, ecs_comps_geo.Geometry)
        geometry.coordinates = request.geometry.get("coordinates", [0, 0])

        request_params = esper.component_for_entity(existing_entity_id, ecs_comps_client_request.ClientRequestPayload)
        crp = props.get("clientRequestPayload", {}) if isinstance(props.get("clientRequestPayload"), dict) else {}
        request_params.requester_id = crp.get("requesterId", "")
        request_params.timestamp = crp.get("timestamp", "")
        request_params.request_type = crp.get("type", "")

        for marker_component in (
            ecs_comps_client_request.NewLocation,
            ecs_comps_client_request.AddObject,
            ecs_comps_client_request.EditedObject,
            ecs_comps_client_request.DeletedObject,
            ecs_comps_client_request.AddEvent,
            ecs_comps_client_request.EditedEvent,
            ecs_comps_client_request.DeletedEvent,
            ecs_comps_client_request.DismissMessage,
        ):
            try:
                esper.remove_component(existing_entity_id, marker_component)
            except KeyError:
                pass

        self._attach_request_marker_component(
            existing_entity_id,
            request_type=str(request_params.request_type or "").strip().lower(),
            requested_action=str(request_params.requested_action or "").strip().lower(),
            requester_id=request_params.requester_id,
            target_id=crp.get("targetId", ""),
            target_path=crp.get("targetPath", ""),
            form_data=props.get("formData", {}) if isinstance(props.get("formData"), dict) else {},
        )

        self._apply_zone_borders_from_properties(existing_entity_id, props)
        return existing_entity_id

    def _find_key_by_identifier(self, entity_ids: dict, identifier: str) -> str | None:
        if not identifier:
            return None
        if identifier in entity_ids:
            return identifier
        for key, entity_id in entity_ids.items():
            id_component = esper.try_component(entity_id, ecs_comps_geo.ID)
            if id_component is not None and str(id_component.id) == identifier:
                return key
        return None

    def _delete_tracked_entity(self, entity_ids: dict, entity_dict: dict, key: str) -> int | None:
        entity_id = entity_ids.pop(key, None)
        entity_dict.pop(key, None)
        if entity_id is not None:
            esper.delete_entity(entity_id)
        return entity_id

    def _apply_deleted_request(
        self,
        request_entity_id: int,
        deleted_component_type: type,
        entity_ids: dict,
        entity_dict: dict,
        node: str,
    ) -> None:
        deleted = esper.try_component(request_entity_id, deleted_component_type)
        if deleted is None:
            self._consume_client_request(request_entity_id)
            return

        target_key = self._find_key_by_identifier(entity_ids, deleted.target_id)
        if target_key is None:
            self._consume_client_request(request_entity_id)
            return

        self._delete_tracked_entity(entity_ids, entity_dict, target_key)
        delete_db_entry(self.database_url, self.session_name, target_key, node=node)
        self._consume_client_request(request_entity_id)

    ## Criteria management
    def _sync_criteria_components(self, entity_id: int, components: dict, component_map: dict) -> None:
        """Remove all components of the given map from entity, then re-add from the components dict."""
        for comp_type in component_map.values():
            try:
                esper.remove_component(entity_id, comp_type)
            except KeyError:
                pass

        for comp_name, comp_data in components.items():
            if not isinstance(comp_data, dict):
                continue
            if comp_name in component_map:
                comp_type = component_map[comp_name]
                tags = comp_data.get("tags", [])
                if not isinstance(tags, list):
                    tags = []
                esper.add_component(entity_id, comp_type(tags=tags))

    ## Event management
    def _sync_event_result_components(self, entity_id: int, result_components: dict) -> None:
        """Remove all existing result ECS components and re-add from result_components dict."""
        for comp_type in ecs_comps_event.EVENT_RESULT_COMPONENT_MAP.values():
            try:
                esper.remove_component(entity_id, comp_type)
            except KeyError:
                pass

        for comp_name, comp_data in result_components.items():
            if not isinstance(comp_data, dict):
                continue
            comp_type = ecs_comps_event.EVENT_RESULT_COMPONENT_MAP.get(comp_name)
            meta = ecs_comps_event.EVENT_RESULT_COMPONENT_CONFIG.get(comp_name)
            if comp_type is None or meta is None:
                continue
            field_name = meta["fieldName"]
            field_type = meta["fieldType"]
            raw = comp_data.get(field_name)
            if field_type == "csv":
                value = normalize_string_list(raw) if raw is not None else []
            elif field_type == "number":
                try:
                    value = int(raw or 0)
                except (TypeError, ValueError):
                    value = 0
            elif field_type == "json":
                value = raw if isinstance(raw, dict) else {}
            else:  # "text"
                value = str(raw or "")
            esper.add_component(entity_id, comp_type(**{field_name: value}))

    def _upsert_event_entity(self, key: str, entry: EventResultEntry) -> int:
        existing_entity_id = self.EventResultEntityIds.get(key)
        if existing_entity_id is None:
            event = ecs_comps_event.Event(
                id=entry.id or key,
                name=entry.name,
            )
            self.EventResults[key] = event
            self.EventResultEntityIds[key] = event.entity_id
            self._sync_criteria_components(event.entity_id, entry.trigger_components, ecs_comps_event.TRIGGER_COMPONENT_MAP)
            self._sync_criteria_components(event.entity_id, entry.target_components, ecs_comps_event.TARGET_COMPONENT_MAP)
            self._sync_event_result_components(event.entity_id, entry.result_components)
            return event.entity_id

        props = entry.properties if isinstance(entry.properties, dict) else {}

        id_component = esper.component_for_entity(existing_entity_id, ecs_comps_geo.ID)
        id_component.id = props.get("id", entry.id or key)

        display_name_comp = esper.component_for_entity(existing_entity_id, ecs_comps_geo.DisplayName)
        display_name_comp.display_name = props.get("displayName", "")

        self._sync_criteria_components(existing_entity_id, entry.trigger_components, ecs_comps_event.TRIGGER_COMPONENT_MAP)
        self._sync_criteria_components(existing_entity_id, entry.target_components, ecs_comps_event.TARGET_COMPONENT_MAP)
        self._sync_event_result_components(existing_entity_id, entry.result_components)
        return existing_entity_id

    def apply_add_event_request(self, request_entity_id: int) -> None:
        request_props = esper.try_component(request_entity_id, ecs_comps_client_request.ClientRequestPayload)
        if request_props is None:
            self._consume_client_request(request_entity_id)
            return

        requester_id = str(request_props.requester_id or "").strip()
        if not requester_id:
            self._consume_client_request(request_entity_id)
            return

        new_key = f"Event{self._random_string()}"
        if new_key in self.EventResultEntityIds:
            new_key = f"{new_key}_{self._random_string(3)}"

        new_event_entry = {
            "type": "Feature",
            "geometry": None,
            "properties": {
                "id": new_key,
                "displayName": new_key,
                "Triggers": {},
                "Targets": {},
                "Results": {},
            },
        }
        put_db_entry(self.database_url, self.session_name, new_key, new_event_entry, NODE=EVENTS_NODE)
        self._upsert_event_entity(new_key, EventResultEntry(new_event_entry))
        self._consume_client_request(request_entity_id)

    def apply_edited_event_request(self, request_entity_id: int) -> None:
        edited = esper.try_component(request_entity_id, ecs_comps_client_request.EditedEvent)
        if edited is None:
            self._consume_client_request(request_entity_id)
            return

        target_key = self._find_key_by_identifier(self.EventResultEntityIds, edited.target_id)
        if target_key is None:
            self._consume_client_request(request_entity_id)
            return

        target_entity_id = self.EventResultEntityIds.get(target_key)
        if target_entity_id is None:
            self._consume_client_request(request_entity_id)
            return

        form_data = edited.form_data if isinstance(edited.form_data, dict) else {}

        display_name_comp = esper.component_for_entity(target_entity_id, ecs_comps_geo.DisplayName)
        display_name_comp.display_name = str(form_data.get("name", display_name_comp.display_name) or display_name_comp.display_name)

        trigger_components = form_data.get("triggerComponents", {})
        if not isinstance(trigger_components, dict):
            trigger_components = {}
        self._sync_criteria_components(target_entity_id, trigger_components, ecs_comps_event.TRIGGER_COMPONENT_MAP)

        target_components = form_data.get("targetComponents", {})
        if not isinstance(target_components, dict):
            target_components = {}
        self._sync_criteria_components(target_entity_id, target_components, ecs_comps_event.TARGET_COMPONENT_MAP)

        result_components = form_data.get("results", {})
        if not isinstance(result_components, dict):
            result_components = {}
        self._sync_event_result_components(target_entity_id, result_components)

        patch_data: dict = {
            "properties/displayName": display_name_comp.display_name,
        }
        for comp_name in ecs_comps_event.TRIGGER_COMPONENT_NAMES:
            patch_data[f"properties/Triggers/{comp_name}"] = trigger_components.get(comp_name)
        for comp_name in ecs_comps_event.TARGET_COMPONENT_NAMES:
            patch_data[f"properties/Targets/{comp_name}"] = target_components.get(comp_name)
        for comp_name in ecs_comps_event.EVENT_RESULT_COMPONENT_NAMES:
            patch_data[f"properties/Results/{comp_name}"] = result_components.get(comp_name)

        patch_db_entry(
            self.database_url,
            self.session_name,
            target_key,
            patch_data,
            node=EVENTS_NODE,
        )

        # Mirror to stream state to suppress echo
        stream_obj = self.stream.event_results_state.get(target_key)
        if isinstance(stream_obj, dict):
            props = stream_obj.setdefault("properties", {})
            if isinstance(props, dict):
                props["displayName"] = display_name_comp.display_name
                triggers = props.setdefault("Triggers", {})
                if isinstance(triggers, dict):
                    for comp_name in ecs_comps_event.TRIGGER_COMPONENT_NAMES:
                        triggers.pop(comp_name, None)
                    for comp_name, comp_data in trigger_components.items():
                        if comp_name in ecs_comps_event.TRIGGER_COMPONENT_NAMES:
                            triggers[comp_name] = comp_data
                targets = props.setdefault("Targets", {})
                if isinstance(targets, dict):
                    for comp_name in ecs_comps_event.TARGET_COMPONENT_NAMES:
                        targets.pop(comp_name, None)
                    for comp_name, comp_data in target_components.items():
                        if comp_name in ecs_comps_event.TARGET_COMPONENT_NAMES:
                            targets[comp_name] = comp_data
                results = props.setdefault("Results", {})
                if isinstance(results, dict):
                    for comp_name in ecs_comps_event.EVENT_RESULT_COMPONENT_NAMES:
                        results.pop(comp_name, None)
                    for comp_name, comp_data in result_components.items():
                        if comp_name in ecs_comps_event.EVENT_RESULT_COMPONENT_NAMES:
                            results[comp_name] = comp_data

        self._consume_client_request(request_entity_id)

    def apply_deleted_event_request(self, request_entity_id: int) -> None:
        deleted = esper.try_component(request_entity_id, ecs_comps_client_request.DeletedEvent)
        if deleted is None:
            self._consume_client_request(request_entity_id)
            return

        target_key = self._find_key_by_identifier(self.EventResultEntityIds, deleted.target_id)
        if target_key is None:
            self._consume_client_request(request_entity_id)
            return

        self._delete_tracked_entity(self.EventResultEntityIds, self.EventResults, target_key)
        delete_db_entry(self.database_url, self.session_name, target_key, node=EVENTS_NODE)
        self._consume_client_request(request_entity_id)


    ## DB maintenance loop and ECS processing
    def run_db_and_ecs_processor(self) -> None:
        self.stream.start()
        self.debug.start()
        self.debug.print_help()

        # 3x the app.js updateFrequency rate (2000 ms → 0.5 Hz → 1.5 Hz).
        ticks_per_second = 1.5
        tick_dt = 1.0 / ticks_per_second
        next_tick = time.perf_counter()

        while True:
            try:
                if self.debug.drain_commands():
                    self.stream.stop()
                    print("\nStopped listener.")
                    return

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

                # Block briefly for the first available DB event, then drain all
                # remaining events immediately so bursts are never processed one
                # per tick cycle.
                time_until_tick = max(0.0, next_tick - time.perf_counter())
                wait_timeout = min(time_until_tick, 0.1)

                try:
                    change: SyncChange = self.stream.event_queue.get(timeout=wait_timeout)
                except queue.Empty:
                    continue

                while True:
                    if change.action == "create":
                        if isinstance(change.feature, ClientRequestEntry):
                            self._upsert_client_request_entity(change.key, change.feature)
                        elif isinstance(change.feature, EventResultEntry):
                            self._upsert_event_entity(change.key, change.feature)
                        else:
                            self._upsert_geo_object_entity(change.key, change.feature)
                    elif change.action == "update" and change.feature is not None:
                        if isinstance(change.feature, ClientRequestEntry):
                            self._upsert_client_request_entity(change.key, change.feature)
                        elif isinstance(change.feature, EventResultEntry):
                            self._upsert_event_entity(change.key, change.feature)
                        else:
                            self._upsert_geo_object_entity(change.key, change.feature)
                    elif change.action == "delete":
                        if change.stream_name == CLIENT_REQUESTS_NODE:
                            self._delete_tracked_entity(self.ClientRequestEntityIds, self.ClientRequests, change.key)
                        elif change.stream_name == GEO_OBJECTS_NODE:
                            self._delete_tracked_entity(self.GeoObjectEntityIds, self.GeoObjects, change.key)
                        elif change.stream_name == EVENTS_NODE:
                            self._delete_tracked_entity(self.EventResultEntityIds, self.EventResults, change.key)
                        elif isinstance(change.feature, ClientRequestEntry) or change.feature is None:
                            self._delete_tracked_entity(self.ClientRequestEntityIds, self.ClientRequests, change.key)
                        else:
                            self._delete_tracked_entity(self.GeoObjectEntityIds, self.GeoObjects, change.key)
                    try:
                        change = self.stream.event_queue.get_nowait()
                    except queue.Empty:
                        break

            except KeyboardInterrupt:
                self.stream.stop()
                print("\nStopped listener.")
                return


