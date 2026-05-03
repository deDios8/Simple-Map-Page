"""Load session-scoped GeoJSON objects from Firebase Realtime Database.

This script prompts for a session name and fetches only:
	/<sessionName>/geoObjects

The result is reconstructed as a Python dictionary in memory so a local
program can consume it directly.
"""

from __future__ import annotations

import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen


# Matches app.js firebaseConfig.databaseURL
DEFAULT_DATABASE_URL = "https://geogm-simple-map-default-rtdb.firebaseio.com"


def normalize_session_name(raw_value: str) -> str:
	"""Mirror app.js normalizeSessionName behavior."""
	trimmed = raw_value.strip()
	without_slashes = trimmed.strip("/")
	return without_slashes or "testBed"


def build_geo_objects_url(database_url: str, session_name: str) -> str:
	"""Build the RTDB REST URL for /<session>/geoObjects."""
	base = database_url.rstrip("/")
	encoded_session = quote(session_name, safe="")
	return f"{base}/{encoded_session}/geoObjects.json"


def normalize_geo_objects(raw_objects: Any) -> dict[str, dict[str, Any]]:
	"""Normalize RTDB payload to an id-keyed dict of GeoJSON feature dicts."""
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
		normalized = {}
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


def fetch_session_geo_objects(database_url: str, session_name: str) -> dict[str, dict[str, Any]]:
	"""Fetch and reconstruct GeoJSON objects from one session path."""
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


def main() -> None:
	print("Firebase GeoJSON Loader")
	raw_session = input("Session name: ")
	session_name = normalize_session_name(raw_session)

	try:
		geo_objects = fetch_session_geo_objects(DEFAULT_DATABASE_URL, session_name)
	except RuntimeError as error:
		print(f"Error: {error}")
		sys.exit(1)

	# Keep this dict in memory for local program use.
	print(f"Loaded {len(geo_objects)} object(s) from session '{session_name}'.")
	print("In-memory dict variable: geo_objects")
	# print(json.dumps(geo_objects, indent=2))
	for each_id, each_object in geo_objects.items():
		print(f"ID: {each_id}, Name: {each_object.get('properties').get('name')}")


if __name__ == "__main__":
	main()

