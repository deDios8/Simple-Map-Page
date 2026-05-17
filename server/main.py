"""
Main server application that listens to Firebase database changes and updates the ECS world accordingly.
"""

import random
import string
import ecs_geo_components
import ecs_processors
import esper
import queue
import time
from debug_console import SessionDebugConsole
from db_stream import (
    DEFAULT_DATABASE_URL,
    CLIENT_REQUESTS_NODE,
    CLIENT_REQUESTS_PROCESSED_NODE,
    GEO_OBJECTS_NODE,
    DatabaseStream,
    SyncChange,
    ClientRequestEntry,
    GeoObjectEntry,
    fetch_client_requests,
    fetch_geo_objects,
    put_db_entry,
    patch_db_entry,
    delete_db_entry,
    normalize_stats,
    normalize_statuses,
    to_bool,
    to_float,
)


class SessionState:
    def __init__(self, database_url: str, session_name: str) -> None:
        self.database_url = database_url
        self.session_name = session_name.strip().strip("/") or "testBed"

        # Keep dict-backed state so Firebase keys can map directly to ECS entities.
        self.GeoObjects: dict[str, ecs_geo_components.GeoObject] = {}
        self.ClientRequests: dict[str, ecs_geo_components.ClientRequest] = {}
        self.GeoObjectEntityIds: dict[str, int] = {}
        self.ClientRequestEntityIds: dict[str, int] = {}
        self._zone_borders_cache: dict[tuple[str, str], dict | None] = {}

        self.stream = DatabaseStream(self.database_url, self.session_name)
        self.debug = SessionDebugConsole(self)
        self._initialize_from_snapshot()

    def _random_string(self, length: int = 2) -> str:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    def _normalize_zone_ids(self, zone_ids: object) -> list[str]:
        if not isinstance(zone_ids, list):
            return []
        return [str(z) for z in zone_ids if z is not None]

    def _sync_zone_component_from_payload(
        self,
        entity_id: int,
        payload: dict,
        payload_key: str,
        component_type: type,
    ) -> None:
        entry = payload.get(payload_key)
        zone_ids = self._normalize_zone_ids(entry.get("zone_ids")) if isinstance(entry, dict) else None
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
            ecs_geo_components.WithinZones,
        )
        self._sync_zone_component_from_payload(
            entity_id,
            payload,
            "enteredZones",
            ecs_geo_components.EnteredZones,
        )
        self._sync_zone_component_from_payload(
            entity_id,
            payload,
            "exitedZones",
            ecs_geo_components.ExitedZones,
        )

    def _sync_stats_component(self, entity_id: int, props: object) -> dict[str, dict]:
        normalized_stats = normalize_stats(props)
        stats_component = esper.try_component(entity_id, ecs_geo_components.Stats)
        if normalized_stats:
            if stats_component is None:
                esper.add_component(entity_id, ecs_geo_components.Stats(items=normalized_stats))
            else:
                stats_component.items = normalized_stats
        elif stats_component is not None:
            esper.remove_component(entity_id, ecs_geo_components.Stats)

        return normalized_stats

    def _sync_statuses_component(self, entity_id: int, props: object) -> dict[str, dict]:
        normalized_statuses = normalize_statuses(props)
        statuses_component = esper.try_component(entity_id, ecs_geo_components.Statuses)
        if normalized_statuses:
            if statuses_component is None:
                esper.add_component(entity_id, ecs_geo_components.Statuses(items=normalized_statuses))
            else:
                statuses_component.items = normalized_statuses
        elif statuses_component is not None:
            esper.remove_component(entity_id, ecs_geo_components.Statuses)



        return normalized_statuses

    def _build_zone_borders_payload(self, entity_id: int) -> dict | None:
        zone_borders: dict[str, dict[str, list[str]]] = {}

        within = esper.try_component(entity_id, ecs_geo_components.WithinZones)
        if within is not None:
            zone_borders["withinZones"] = {"zone_ids": self._normalize_zone_ids(within.zone_ids)}

        entered = esper.try_component(entity_id, ecs_geo_components.EnteredZones)
        if entered is not None:
            zone_borders["enteredZones"] = {"zone_ids": self._normalize_zone_ids(entered.zone_ids)}

        exited = esper.try_component(entity_id, ecs_geo_components.ExitedZones)
        if exited is not None:
            zone_borders["exitedZones"] = {"zone_ids": self._normalize_zone_ids(exited.zone_ids)}

        return zone_borders or None

    def _patch_zone_borders(self, node: str, key: str, entity_id: int) -> None:
        payload = self._build_zone_borders_payload(entity_id)
        cache_key = (node, key)
        if self._zone_borders_cache.get(cache_key) == payload:
            return
        patch_db_entry(
            self.database_url,
            self.session_name,
            key,
            {"properties/zoneBorders": payload},
            node=node,
        )
        self._zone_borders_cache[cache_key] = payload

    def _sync_dirty_zone_borders_to_database(self) -> None:
        geo_by_entity = {entity_id: key for key, entity_id in self.GeoObjectEntityIds.items()}
        req_by_entity = {entity_id: key for key, entity_id in self.ClientRequestEntityIds.items()}

        for entity_id, _ in list(esper.get_component(ecs_geo_components.ZoneBordersDirty)):
            geo_key = geo_by_entity.get(entity_id)
            req_key = req_by_entity.get(entity_id)

            if geo_key is not None:
                self._patch_zone_borders(GEO_OBJECTS_NODE, geo_key, entity_id)
            elif req_key is not None:
                self._patch_zone_borders(CLIENT_REQUESTS_NODE, req_key, entity_id)

            try:
                esper.remove_component(entity_id, ecs_geo_components.ZoneBordersDirty)
            except KeyError:
                pass

    def _initialize_from_snapshot(self) -> None:
        geo_objects = fetch_geo_objects(self.database_url, self.session_name)
        for key, raw in geo_objects.items():
            entry = GeoObjectEntry(raw)
            self._upsert_geo_object_entity(key, entry)

        client_requests = fetch_client_requests(self.database_url, self.session_name)
        for key, raw in client_requests.items():
            entry = ClientRequestEntry(raw)
            self._upsert_client_request_entity(key, entry)


    def _sync_geo_type_marker_components(self, entity_id: int, is_user: bool) -> None:
        if is_user:
            try:
                esper.remove_component(entity_id, ecs_geo_components.IsZone)
            except KeyError:
                pass
            try:
                esper.component_for_entity(entity_id, ecs_geo_components.IsUser)
            except KeyError:
                esper.add_component(entity_id, ecs_geo_components.IsUser())
            return

        try:
            esper.remove_component(entity_id, ecs_geo_components.IsUser)
        except KeyError:
            pass
        try:
            esper.component_for_entity(entity_id, ecs_geo_components.IsZone)
        except KeyError:
            esper.add_component(entity_id, ecs_geo_components.IsZone())

    def _find_geo_object_key_by_identifier(self, identifier: str) -> str | None:
        if not identifier:
            return None
        if identifier in self.GeoObjectEntityIds:
            return identifier

        for key, entity_id in self.GeoObjectEntityIds.items():
            id_component = esper.try_component(entity_id, ecs_geo_components.ID)
            if id_component is not None and str(id_component.id) == identifier:
                return key
        return None

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
            ecs_geo_components.NewLocation,
            ecs_geo_components.EditedObject,
            ecs_geo_components.DeletedObject,
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
        request_geometry = esper.try_component(request_entity_id, ecs_geo_components.Geometry)
        request_props = esper.try_component(request_entity_id, ecs_geo_components.ClientRequestProperties)
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

        target_key = self._find_geo_object_key_by_identifier(requester_id) or requester_id
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
                    "is_user": True,
                    "metaData": {
                        "name": requester_id,
                        "description": "Live user location.",
                        "type": "user",
                    },
                    "appearance": {
                        "color": "#000000",
                        "visible": True,
                        "radius": 5,
                    },
                    "data": {},
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

        geometry = esper.component_for_entity(target_entity_id, ecs_geo_components.Geometry)
        geometry.coordinates = [lon, lat]
        esper.add_component(target_entity_id, ecs_geo_components.ZoneBordersDirty())

        patch_db_entry(
            self.database_url,
            self.session_name,
            target_key,
            {"geometry/coordinates": [lon, lat]},
            node=GEO_OBJECTS_NODE,
        )
        self._consume_client_request(request_entity_id)

    def apply_add_object_request(self, request_entity_id: int) -> None:
        request_geometry = esper.try_component(request_entity_id, ecs_geo_components.Geometry)
        request_props = esper.try_component(request_entity_id, ecs_geo_components.ClientRequestProperties)
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
                "metaData": {
                    "name": f"{new_object_key}",
                    "description": f"Added by {requester_id}.",
                    "type": "pin",
                },
                "appearance": {
                    "color": "#0b8f87",
                    "visible": True,
                    "radius": 5,
                },
                "data": {},
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
        edited = esper.try_component(request_entity_id, ecs_geo_components.EditedObject)
        if edited is None:
            self._consume_client_request(request_entity_id)
            return

        target_key = (
            self._find_geo_object_key_by_identifier(edited.target_id)
            or self._find_geo_object_key_by_identifier(self._extract_geo_key_from_target_path(edited.target_path))
        )
        if target_key is None:
            self._consume_client_request(request_entity_id)
            return

        target_entity_id = self.GeoObjectEntityIds.get(target_key)
        if target_entity_id is None:
            self._consume_client_request(request_entity_id)
            return

        form_data = edited.form_data if isinstance(edited.form_data, dict) else {}

        metadata = esper.component_for_entity(target_entity_id, ecs_geo_components.MetaData)
        appearance = esper.component_for_entity(target_entity_id, ecs_geo_components.Appearance)
        geometry = esper.component_for_entity(target_entity_id, ecs_geo_components.Geometry)

        metadata.name = str(form_data.get("name", metadata.name) or metadata.name)
        metadata.type = str(form_data.get("type", metadata.type) or metadata.type)
        metadata.description = str(form_data.get("description", metadata.description) or metadata.description)

        appearance.color = str(form_data.get("color", appearance.color) or appearance.color)
        appearance.radius = to_float(form_data.get("radius"), float(appearance.radius))

        visible_fallback = True
        geo_snapshot = self.stream.geo_object_state.get(target_key)
        if isinstance(geo_snapshot, dict):
            props = geo_snapshot.get("properties") if isinstance(geo_snapshot.get("properties"), dict) else {}
            appearance_snapshot = props.get("appearance") if isinstance(props.get("appearance"), dict) else {}
            visible_fallback = bool(appearance_snapshot.get("visible", True))
        appearance_visible = to_bool(form_data.get("visible"), visible_fallback)

        lat = to_float(form_data.get("latitude"), float(geometry.coordinates[1]))
        lon = to_float(form_data.get("longitude"), float(geometry.coordinates[0]))
        geometry.coordinates = [lon, lat]
        esper.add_component(target_entity_id, ecs_geo_components.ZoneBordersDirty())

        stats_payload = form_data.get("stats") if isinstance(form_data.get("stats"), dict) else {}
        next_stats_payload = normalize_stats({"stats": stats_payload})

        self._sync_stats_component(target_entity_id, {"stats": next_stats_payload})

        statuses_payload = form_data.get("statuses") if isinstance(form_data.get("statuses"), dict) else {}
        next_statuses_payload = normalize_statuses({"statuses": statuses_payload})

        self._sync_statuses_component(target_entity_id, {"statuses": next_statuses_payload})

        extra_data = form_data.get("extraData")
        if not isinstance(extra_data, dict):
            extra_data = {}

        patch_db_entry(
            self.database_url,
            self.session_name,
            target_key,
            {
                "geometry/coordinates": [lon, lat],
                "properties/metaData/name": metadata.name,
                "properties/metaData/type": metadata.type,
                "properties/metaData/description": metadata.description,
                "properties/appearance/color": appearance.color,
                "properties/appearance/radius": appearance.radius,
                "properties/appearance/visible": appearance_visible,
                "properties/data": extra_data,
                "properties/stats": next_stats_payload,
                "properties/statuses": next_statuses_payload,
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
                meta = props.setdefault("metaData", {})
                if isinstance(meta, dict):
                    meta["name"] = metadata.name
                    meta["type"] = metadata.type
                    meta["description"] = metadata.description
                appr = props.setdefault("appearance", {})
                if isinstance(appr, dict):
                    appr["color"] = appearance.color
                    appr["radius"] = appearance.radius
                    appr["visible"] = appearance_visible
                props["data"] = extra_data
                if next_stats_payload:
                    props["stats"] = next_stats_payload
                else:
                    props.pop("stats", None)
                if next_statuses_payload:
                    props["statuses"] = next_statuses_payload
                else:
                    props.pop("statuses", None)

        self._consume_client_request(request_entity_id)

    def apply_deleted_object_request(self, request_entity_id: int) -> None:
        deleted = esper.try_component(request_entity_id, ecs_geo_components.DeletedObject)
        if deleted is None:
            self._consume_client_request(request_entity_id)
            return

        target_key = (
            self._find_geo_object_key_by_identifier(deleted.target_id)
            or self._find_geo_object_key_by_identifier(self._extract_geo_key_from_target_path(deleted.target_path))
        )
        if target_key is None:
            self._consume_client_request(request_entity_id)
            return

        self._delete_geo_object_entity(target_key)
        delete_db_entry(
            self.database_url,
            self.session_name,
            target_key,
            node=GEO_OBJECTS_NODE,
        )
        self._consume_client_request(request_entity_id)


    def _upsert_geo_object_entity(self, key: str, geo_object: GeoObjectEntry) -> int:
        existing_entity_id = self.GeoObjectEntityIds.get(key)
        if existing_entity_id is None:
            geo = ecs_geo_components.GeoObject(
                id=geo_object.id or key,
                geometry=geo_object.geometry,
                properties=geo_object.properties,
            )
            self.GeoObjects[key] = geo
            self.GeoObjectEntityIds[key] = geo.entity_id
            self._apply_zone_borders_from_properties(geo.entity_id, geo_object.properties)
            self._sync_geo_type_marker_components(geo.entity_id, geo_object.is_user)
            
            self._sync_stats_component(geo.entity_id, geo_object.properties)
            self._sync_statuses_component(geo.entity_id, geo_object.properties)
            
            return geo.entity_id

        props = geo_object.properties if isinstance(geo_object.properties, dict) else {}

        id_component = esper.component_for_entity(existing_entity_id, ecs_geo_components.ID)
        id_component.id = props.get("id", geo_object.id or key)

        metadata = esper.component_for_entity(existing_entity_id, ecs_geo_components.MetaData)
        meta_data = props.get("metaData", {}) if isinstance(props.get("metaData"), dict) else {}
        metadata.name = meta_data.get("name", "")
        metadata.description = meta_data.get("description", "")
        metadata.type = meta_data.get("type", "")

        appearance = esper.component_for_entity(existing_entity_id, ecs_geo_components.Appearance)
        appearance_data = props.get("appearance", {}) if isinstance(props.get("appearance"), dict) else {}
        appearance.color = appearance_data.get("color", "")
        appearance.shape = appearance_data.get("shape", "")
        appearance.radius = appearance_data.get("radius", 0)

        geometry = esper.component_for_entity(existing_entity_id, ecs_geo_components.Geometry)
        geometry.coordinates = geo_object.geometry.get("coordinates", [0, 0])
        self._apply_zone_borders_from_properties(existing_entity_id, props)
        self._sync_geo_type_marker_components(existing_entity_id, geo_object.is_user)

        self._sync_stats_component(existing_entity_id, props)
        self._sync_statuses_component(existing_entity_id, props)
        
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
            esper.add_component(entity_id, ecs_geo_components.NewLocation(requester_id=requester_id))
        elif requested_action == "add_object":
            esper.add_component(entity_id, ecs_geo_components.AddObject(requester_id=requester_id))
        elif request_type == "edited_object":
            esper.add_component(entity_id, ecs_geo_components.EditedObject(target_id=target_id, target_path=target_path, form_data=form_data))
        elif request_type == "deleted_object":
            esper.add_component(entity_id, ecs_geo_components.DeletedObject(target_id=target_id, target_path=target_path))

    def _upsert_client_request_entity(self, key: str, request: ClientRequestEntry) -> int:
        existing_entity_id = self.ClientRequestEntityIds.get(key)
        if existing_entity_id is None:
            entity = ecs_geo_components.ClientRequest(
                id=request.id or key,
                geometry=request.geometry,
                properties=request.properties,
            )
            self.ClientRequests[key] = entity
            self.ClientRequestEntityIds[key] = entity.entity_id
            request_params = esper.component_for_entity(entity.entity_id, ecs_geo_components.ClientRequestProperties)
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

        id_component = esper.component_for_entity(existing_entity_id, ecs_geo_components.ID)
        id_component.id = props.get("id", request.id or key)

        geometry = esper.component_for_entity(existing_entity_id, ecs_geo_components.Geometry)
        geometry.coordinates = request.geometry.get("coordinates", [0, 0])

        request_params = esper.component_for_entity(existing_entity_id, ecs_geo_components.ClientRequestProperties)
        crp = props.get("clientRequestProperties", {}) if isinstance(props.get("clientRequestProperties"), dict) else {}
        request_params.requester_id = crp.get("requesterId", "")
        request_params.timestamp = crp.get("timestamp", "")
        request_params.request_type = crp.get("type", "")

        for marker_component in (
            ecs_geo_components.NewLocation,
            ecs_geo_components.AddObject,
            ecs_geo_components.EditedObject,
            ecs_geo_components.DeletedObject,
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


    def _delete_geo_object_entity(self, key: str) -> int | None:
        entity_id = self.GeoObjectEntityIds.pop(key, None)
        self.GeoObjects.pop(key, None)
        if entity_id is not None:
            esper.delete_entity(entity_id)
        return entity_id

    def _delete_client_request_entity(self, key: str) -> int | None:
        entity_id = self.ClientRequestEntityIds.pop(key, None)
        self.ClientRequests.pop(key, None)
        if entity_id is not None:
            esper.delete_entity(entity_id)
        return entity_id


    def run_db_and_ecs_processor(self) -> None:
        self.stream.start()
        self.debug.start()
        self.debug.print_help()

        ticks_per_second = 2.0
        tick_dt = 1.0 / ticks_per_second
        next_tick = time.perf_counter()

        while True:
            try:
                self.debug.drain_commands()

                # Run ECS ticks on schedule while avoiding runaway catch-up.
                now = time.perf_counter()
                tick_steps = 0
                max_catchup_steps = 5
                while now >= next_tick and tick_steps < max_catchup_steps:
                    esper.process()
                    self._sync_dirty_zone_borders_to_database()
                    next_tick += tick_dt
                    tick_steps += 1

                # If far behind, resync the schedule to keep the loop stable.
                if now - next_tick > 1.0:
                    next_tick = now + tick_dt

                # Wait for DB events, but never longer than time until next tick.
                time_until_tick = max(0.0, next_tick - time.perf_counter())
                wait_timeout = min(time_until_tick, 0.1)

                # Handle DB events as they come in, but don't let them block the loop indefinitely.
                change: SyncChange = self.stream.event_queue.get(timeout=wait_timeout)
                if change.action == "create":
                    if isinstance(change.feature, ClientRequestEntry):
                        self._upsert_client_request_entity(change.key, change.feature)
                    else:
                        self._upsert_geo_object_entity(change.key, change.feature)
                elif change.action == "update" and change.feature is not None:
                    if isinstance(change.feature, ClientRequestEntry):
                        self._upsert_client_request_entity(change.key, change.feature)
                    else:
                        self._upsert_geo_object_entity(change.key, change.feature)
                elif change.action == "delete":
                    if change.stream_name == CLIENT_REQUESTS_NODE:
                        self._delete_client_request_entity(change.key)
                    elif change.stream_name == GEO_OBJECTS_NODE:
                        self._delete_geo_object_entity(change.key)
                    elif isinstance(change.feature, ClientRequestEntry) or change.feature is None:
                        self._delete_client_request_entity(change.key)
                    else:
                        self._delete_geo_object_entity(change.key)
            except KeyboardInterrupt:
                self.stream.stop()
                print("\nStopped listener.")
                return
            except queue.Empty:
                continue


def main() -> None:
    print("Firebase Feature Listener")
    session_name = input("Session name: ")
    session_state = SessionState(DEFAULT_DATABASE_URL, session_name)
    esper.add_processor(ecs_processors.ApplyClientRequests(session_state), priority=100)
    esper.add_processor(ecs_processors.CheckZoneEntryExit(), priority=99)
    esper.add_processor(ecs_processors.RemoveZoneEntryExit(), priority=1)
    session_state.run_db_and_ecs_processor()



if __name__ == "__main__":
    main()

