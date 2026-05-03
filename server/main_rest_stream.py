"""Listen to Firebase RTDB GeoJSON changes for a session branch.

This script mirrors the session + geoObjects structure used in public/app.js:
  /<sessionName>/geoObjects

Behavior:
1) Prompt for session name.
2) Download initial geoObjects payload and build a local in-memory dict.
3) Open a Firebase REST streaming listener and print every add/update/delete.
4) Keep the local dict synchronized with RTDB events.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_DATABASE_URL = "https://geogm-simple-map-default-rtdb.firebaseio.com"
GEO_OBJECTS_NODE = "geoObjects"


@dataclass
class StreamEvent:
	"""Single Firebase stream event payload."""

	event_type: str
	path: str
	data: Any


def normalize_session_name(raw_value: str) -> str:
	"""Mirror app.js normalizeSessionName behavior."""
	trimmed = raw_value.strip()
	without_slashes = trimmed.strip("/")
	return without_slashes or "testBed"


def build_geo_objects_url(database_url: str, session_name: str) -> str:
	"""Build URL for /<session>/geoObjects.json."""
	base = database_url.rstrip("/")
	encoded_session = quote(session_name, safe="")
	encoded_collection = quote(GEO_OBJECTS_NODE, safe="")
	return f"{base}/{encoded_session}/{encoded_collection}.json"


def normalize_geo_objects(raw_objects: Any) -> dict[str, dict[str, Any]]:
	"""Normalize payload to id-keyed GeoJSON dict."""
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


def fetch_geo_objects(database_url: str, session_name: str) -> dict[str, dict[str, Any]]:
	"""Fetch current /<session>/geoObjects snapshot."""
	url = build_geo_objects_url(database_url, session_name)

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

	return normalize_geo_objects(decoded)


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


def _parse_path(path: str) -> list[str]:
	if not path or path == "/":
		return []
	return [segment for segment in path.split("/") if segment]


def _print_key_diff(previous: dict[str, Any], current: dict[str, Any], prefix: str = "") -> None:
	prev_keys = set(previous.keys())
	curr_keys = set(current.keys())

	for key in sorted(curr_keys - prev_keys):
		print(f"[ADD] {prefix}{key}")

	for key in sorted(prev_keys - curr_keys):
		print(f"[DELETE] {prefix}{key}")

	for key in sorted(prev_keys & curr_keys):
		before = previous[key]
		after = current[key]
		if before != after:
			if isinstance(before, dict) and isinstance(after, dict):
				_print_key_diff(before, after, prefix=f"{prefix}{key}/")
			else:
				print(f"[UPDATE] {prefix}{key}")


def apply_stream_event(local_geo_objects: dict[str, Any], stream_event: StreamEvent) -> None:
	"""Apply one stream event and print the resulting change(s)."""
	segments = _parse_path(stream_event.path)
	before = json.loads(json.dumps(local_geo_objects))

	if stream_event.data is None:
		_delete_nested(local_geo_objects, segments)
	else:
		is_patch = stream_event.event_type == "patch"
		_set_nested(local_geo_objects, segments, stream_event.data, merge=is_patch)

	_print_key_diff(before, local_geo_objects)


def iter_firebase_stream(database_url: str, session_name: str):
	"""Yield parsed StreamEvent objects from Firebase REST streaming API."""
	url = build_geo_objects_url(database_url, session_name)
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

					if not isinstance(payload, dict):
						event_type = None
						data_lines = []
						continue

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
				continue

			if line.startswith("data:"):
				data_lines.append(line.split(":", 1)[1].strip())


def run_listener(database_url: str, session_name: str, local_geo_objects: dict[str, Any]) -> None:
	"""Keep local dict in sync with Firebase stream events forever."""
	print(f"Listening for changes at /{session_name}/{GEO_OBJECTS_NODE} ...")

	# Firebase sends an initial full 'put' event on stream connect.
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

				apply_stream_event(local_geo_objects, stream_event)
				print(f"[STATE] Local dict now has {len(local_geo_objects)} top-level object(s).")
		except KeyboardInterrupt:
			print("\nStopped listener.")
			return
		except (HTTPError, URLError, RuntimeError) as error:
			print(f"[WARN] Stream disconnected: {error}")
			print("[INFO] Reconnecting in 2 seconds...")
			time.sleep(2)


def main() -> None:
	print("Firebase Session Listener")
	raw_session = input("Session name: ")
	session_name = normalize_session_name(raw_session)

	try:
		geo_objects = fetch_geo_objects(DEFAULT_DATABASE_URL, session_name)
	except RuntimeError as error:
		print(f"Error: {error}")
		sys.exit(1)

	print(f"Loaded {len(geo_objects)} object(s) from /{session_name}/{GEO_OBJECTS_NODE}.")
	for each_id in sorted(geo_objects.keys()):
		print(f"[INIT] {each_id}")

	run_listener(DEFAULT_DATABASE_URL, session_name, geo_objects)


if __name__ == "__main__":
	main()
