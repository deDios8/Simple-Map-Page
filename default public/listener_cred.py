"""Firebase Admin listener for one session's GeoJSON objects.

Behavior:
1) Prompt for a session name.
2) Load /<session>/geoObjects into an in-memory dict.
3) Listen for realtime changes with firebase_admin listeners.
4) Print add/update/delete changes and keep local dict synchronized.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import threading
from dataclasses import dataclass
from typing import Any
import firebase_admin
from firebase_admin import credentials, db


DEFAULT_DATABASE_URL = "https://geogm-simple-map-default-rtdb.firebaseio.com"
GEO_OBJECTS_NODE = "geoObjects"


@dataclass
class ListenerState:
	"""Holds local synchronized copy and stream state."""

	geo_objects: dict[str, Any]
	received_first_listener_snapshot: bool = False


def normalize_session_name(raw_value: str) -> str:
	"""Mirror app.js normalizeSessionName behavior."""
	trimmed = raw_value.strip()
	without_slashes = trimmed.strip("/")
	return without_slashes or "testBed"


def normalize_geo_objects(raw_objects: Any) -> dict[str, dict[str, Any]]:
	"""Normalize payload to an id-keyed GeoJSON dict."""
	if not raw_objects:
		return {}

	if isinstance(raw_objects, list):
		normalized: dict[str, dict[str, Any]] = {}
		for index, entry in enumerate(raw_objects):
			if not isinstance(entry, dict):
				continue

			properties = entry.get("properties") or {}
			entry_id = properties.get("id") or f"item-{index}"
			normalized[entry_id] = {
				**entry,
				"properties": {
					**properties,
					"id": entry_id,
				},
			}
		return normalized

	if isinstance(raw_objects, dict):
		normalized: dict[str, dict[str, Any]] = {}
		for key, entry in raw_objects.items():
			if not isinstance(entry, dict):
				continue

			properties = entry.get("properties") or {}
			entry_id = properties.get("id") or str(key)
			normalized[str(key)] = {
				**entry,
				"properties": {
					**properties,
					"id": entry_id,
				},
			}
		return normalized

	return {}


def _parse_path(path: str) -> list[str]:
	if not path or path == "/":
		return []
	return [segment for segment in path.split("/") if segment]


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
		next_value = current.get(segment)
		if not isinstance(next_value, dict):
			next_value = {}
			current[segment] = next_value
		current = next_value
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
			for key, child_value in value.items():
				if child_value is None:
					target.pop(key, None)
				else:
					target[key] = child_value
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
		for child_key, child_value in value.items():
			if child_value is None:
				existing.pop(child_key, None)
			else:
				existing[child_key] = child_value
	else:
		parent[key] = value


def _ensure_ids(local_geo_objects: dict[str, Any]) -> None:
	for key, value in local_geo_objects.items():
		if not isinstance(value, dict):
			continue
		properties = value.get("properties")
		if not isinstance(properties, dict):
			properties = {}
			value["properties"] = properties
		properties.setdefault("id", key)


def _print_key_diff(previous: dict[str, Any], current: dict[str, Any], prefix: str = "") -> None:
	prev_keys = set(previous.keys())
	curr_keys = set(current.keys())

	for key in sorted(curr_keys - prev_keys):
		print(f"[ADD] {prefix}{key}", flush=True)

	for key in sorted(prev_keys - curr_keys):
		print(f"[DELETE] {prefix}{key}", flush=True)

	for key in sorted(prev_keys & curr_keys):
		before = previous[key]
		after = current[key]
		if before != after:
			if isinstance(before, dict) and isinstance(after, dict):
				_print_key_diff(before, after, prefix=f"{prefix}{key}/")
			else:
				print(f"[UPDATE] {prefix}{key}", flush=True)


def apply_event_to_local_dict(local_geo_objects: dict[str, Any], event_type: str, path: str, data: Any) -> None:
	"""Apply one listener event and print resulting changes."""
	segments = _parse_path(path)
	before = copy.deepcopy(local_geo_objects)

	if data is None:
		_delete_nested(local_geo_objects, segments)
	else:
		_set_nested(local_geo_objects, segments, data, merge=(event_type == "patch"))

	_ensure_ids(local_geo_objects)
	_print_key_diff(before, local_geo_objects)


def init_firebase_admin(database_url: str) -> None:
	"""Initialize Firebase Admin app once."""
	if firebase_admin._apps:
		return

	service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

	if service_account_path:
		cred = credentials.Certificate(service_account_path)
		firebase_admin.initialize_app(cred, {"databaseURL": database_url})
		return

	# Falls back to ADC; if unavailable, Firebase will raise a clear error.
	firebase_admin.initialize_app(options={"databaseURL": database_url})


def main() -> None:
	print("Firebase Admin Session Listener")
	raw_session = input("Session name: ")
	session_name = normalize_session_name(raw_session)
	branch_path = f"/{session_name}/{GEO_OBJECTS_NODE}"

	try:
		init_firebase_admin(DEFAULT_DATABASE_URL)
	except Exception as error:  # pragma: no cover - startup failure path
		print(f"Failed to initialize Firebase Admin: {error}", file=sys.stderr)
		sys.exit(1)

	branch_ref = db.reference(branch_path)

	try:
		initial_snapshot = branch_ref.get()
	except Exception as error:  # pragma: no cover - network/auth failure path
		print(f"Failed to read initial snapshot: {error}", file=sys.stderr)
		sys.exit(1)

	local_geo_objects = normalize_geo_objects(initial_snapshot)
	state = ListenerState(geo_objects=local_geo_objects)

	print(f"Loaded {len(state.geo_objects)} object(s) from {branch_path}")
	for each_id in sorted(state.geo_objects.keys()):
		print(f"[INIT] {each_id}")

	stop_event = threading.Event()

	def on_change(event: Any) -> None:
		event_type = getattr(event, "event_type", "unknown")
		path = getattr(event, "path", "/")
		data = getattr(event, "data", None)

		# Firebase listener sends a full snapshot first; skip because we already fetched it.
		if not state.received_first_listener_snapshot and path == "/":
			state.received_first_listener_snapshot = True
			print("[INFO] Initial listener snapshot received.", flush=True)
			return

		apply_event_to_local_dict(state.geo_objects, event_type, path, data)
		print(
			f"[STATE] Local dict has {len(state.geo_objects)} top-level object(s).",
			flush=True,
		)

	print(f"Listening for changes at {branch_path} ...")
	registration = branch_ref.listen(on_change)

	try:
		stop_event.wait()
	except KeyboardInterrupt:
		print("\nStopping listener...")
	finally:
		registration.close()


if __name__ == "__main__":
	main()
