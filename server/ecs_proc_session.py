import copy
import esper
import math
import ecs_comps_zone
import ecs_comps_client_request
from pyproj import CRS, Transformer
from session_db_state import SessionState
from session_db_state import ZONE_NODE, multi_path_patch


class ApplyClientRequests(esper.Processor):
    def __init__(self, session_state: SessionState) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.NewLocation)):
            self.session_state.apply_new_location_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.AddObject)):
            self.session_state.apply_add_zone_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.EditedObject)):
            self.session_state.apply_edited_zone_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.DeletedObject)):
            self.session_state.apply_deleted_zone_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.AddEvent)):
            self.session_state.apply_add_event_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.EditedEvent)):
            self.session_state.apply_edited_event_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.DeletedEvent)):
            self.session_state.apply_deleted_event_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.DismissMessage)):
            self.session_state.apply_dismiss_message_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.ClearLogs)):
            self.session_state.apply_clear_logs_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.ClearLogsAll)):
            self.session_state.apply_clear_logs_all_request(entity_id)



class CheckZoneEntryExit(esper.Processor):
    def __init__(self, session_state: SessionState) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        all_zone_entities = list(esper.get_components(
            ecs_comps_zone.Geometry,
            ecs_comps_zone.ID,
            ecs_comps_zone.Appearance,
        ))
        transformer_cache: dict = {}

        for entity_id, (geometry, id_component, _) in all_zone_entities:
            current_zones = set()
            for zone_entity_id, (zone_geometry, zone_id_component, zone_appearance) in all_zone_entities:
                if zone_entity_id == entity_id: continue
                if id_component.id == zone_id_component.id: continue

                zone_radius = zone_appearance.radius if zone_appearance is not None else 0

                if self.is_within_zone_intersect(
                    geometry.coordinates,
                    zone_geometry.coordinates,
                    zone_radius,
                    transformer_cache,
                ):
                    current_zones.add(str(zone_id_component.id))

            previous_within = esper.try_component(entity_id, ecs_comps_zone.WithinZones)
            previous_zones = set(previous_within.zone_ids) if previous_within else set()

            entered_zones = current_zones - previous_zones
            exited_zones = previous_zones - current_zones

            if entered_zones or exited_zones:
                display_name_comp = esper.try_component(entity_id, ecs_comps_zone.DisplayName)
                entity_display_name = display_name_comp.display_name if display_name_comp else id_component.id
            if entered_zones:
                esper.add_component(entity_id, ecs_comps_zone.EnteredZones(zone_ids=list(entered_zones)))
                self._terminal_log_border_crossing("entered", entity_display_name, entered_zones)
            if exited_zones:
                esper.add_component(entity_id, ecs_comps_zone.ExitedZones(zone_ids=list(exited_zones)))
                self._terminal_log_border_crossing("exited", entity_display_name, exited_zones)

    def _terminal_log_border_crossing(self, action: str, entity_display_name: str, zone_ids: set[str]) -> None:
        """Convert zone IDs to display names for logging."""
        names = []
        for zone_id in zone_ids:
            zone_eid = self.session_state.ZoneEntityIds.get(zone_id)
            if zone_eid is not None:
                display_name_comp = esper.try_component(zone_eid, ecs_comps_zone.DisplayName)
                if display_name_comp:
                    names.append(display_name_comp.display_name)
                else:
                    names.append(zone_id)
            else:
                names.append(zone_id)
        print(f"[CheckZoneEntryExit] Entity '{entity_display_name}' {action} zones: {names}")

    def is_within_zone_intersect(self, focal_coordinates: list, zone_coordinates: list, zone_radius_value: float, transformer_cache: dict) -> bool:
        if not isinstance(focal_coordinates, list) or len(focal_coordinates) < 2:
            return False
        if not isinstance(zone_coordinates, list) or len(zone_coordinates) < 2:
            return False

        try:
            obj_lon = float(focal_coordinates[0])
            obj_lat = float(focal_coordinates[1])
            zone_lon = float(zone_coordinates[0])
            zone_lat = float(zone_coordinates[1])
            zone_radius_m = 0.0
            zone_radius_m = max(0.0, float(zone_radius_value))
        except (TypeError, ValueError):
            return False

        # Local azimuthal-equidistant CRS keeps distances in meters near the zone center.
        cache_key = (zone_lon, zone_lat)
        if cache_key not in transformer_cache:
            local_crs = CRS.from_proj4(
                f"+proj=aeqd +lat_0={zone_lat} +lon_0={zone_lon} +datum=WGS84 +units=m +no_defs"
            )
            transformer_cache[cache_key] = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True)
        transformer = transformer_cache[cache_key]

        obj_x, obj_y = transformer.transform(obj_lon, obj_lat)
        zone_x, zone_y = transformer.transform(zone_lon, zone_lat)

        distance_m = math.hypot(obj_x - zone_x, obj_y - zone_y)
        return distance_m <= zone_radius_m



class RemoveZoneEntryExit(esper.Processor):
    def __init__(self) -> None:
        super().__init__()
        
    def process(self) -> None:
        for entity_id, entered in list(esper.get_component(ecs_comps_zone.EnteredZones)):
            self._apply_zone_change(
                entity_id=entity_id,
                changed_zone_ids=entered.zone_ids,
                temp_component_type=ecs_comps_zone.EnteredZones,
                log_component_type=ecs_comps_zone.ZoneEntryLog,
                is_entering=True,
            )

        for entity_id, exited in list(esper.get_component(ecs_comps_zone.ExitedZones)):
            self._apply_zone_change(
                entity_id=entity_id,
                changed_zone_ids=exited.zone_ids,
                temp_component_type=ecs_comps_zone.ExitedZones,
                log_component_type=ecs_comps_zone.ZoneExitLog,
                is_entering=False,
            )

    def _apply_zone_change(
        self,
        entity_id: int,
        changed_zone_ids: list[str],
        temp_component_type: type,
        log_component_type: type,
        is_entering: bool,
    ) -> None:
        changed_zones = set(changed_zone_ids)

        # Update WithinZones
        within = esper.try_component(entity_id, ecs_comps_zone.WithinZones)
        before_zones = set(within.zone_ids) if within else set()
        if is_entering:
            within_zones = before_zones | changed_zones
        else:
            within_zones = before_zones - changed_zones

        if within_zones:
            esper.add_component(entity_id, ecs_comps_zone.WithinZones(zone_ids=list(within_zones)))
        else:
            try:
                esper.remove_component(entity_id, ecs_comps_zone.WithinZones)
            except KeyError:
                pass

        # Append to log
        log = esper.try_component(entity_id, log_component_type)
        if log is None:
            esper.add_component(entity_id, log_component_type(zone_ids=list(changed_zone_ids)))
        else:
            log.zone_ids.extend(changed_zone_ids)

        # Mark entity as dirty to sync log to database
        esper.add_component(entity_id, ecs_comps_zone.ZoneObjectDirty())

        # Remove temporary component
        try:
            esper.remove_component(entity_id, temp_component_type)
        except KeyError:
            pass



class SyncZonesToDatabase(esper.Processor):
    def __init__(self, session_state: SessionState) -> None:
        super().__init__()
        self.session_state = session_state
        self._cache: dict[int, dict] = {}

    def process(self) -> None:
        zone_by_entity = {entity_id: key for key, entity_id in self.session_state.ZoneEntityIds.items()}
        multi_path_payload: dict = {}

        for entity_id, _ in list(esper.get_component(ecs_comps_zone.ZoneObjectDirty)):
            key = zone_by_entity.get(entity_id)
            if key is None:
                try:
                    esper.remove_component(entity_id, ecs_comps_zone.ZoneObjectDirty)
                except KeyError:
                    pass
                continue

            fields = self._build_properties_payload(entity_id)
            if self._cache.get(entity_id) != fields:
                for field_path, value in fields.items():
                    multi_path_payload[f"{ZONE_NODE}/{key}/{field_path}"] = value
                self._cache[entity_id] = copy.deepcopy(fields)

            try:
                esper.remove_component(entity_id, ecs_comps_zone.ZoneObjectDirty)
            except KeyError:
                pass

        if multi_path_payload: # Only send update if there are changes to the payload
            multi_path_patch(
                self.session_state.database_url,
                self.session_state.session_name,
                multi_path_payload,
            )

    def _build_properties_payload(self, entity_id: int) -> dict:
        payload = {}

        appearance = esper.try_component(entity_id, ecs_comps_zone.Appearance)
        if appearance is not None:
            payload["properties/appearance"] = {
                "fill": appearance.fill,
                "border": appearance.border,
                "shape": appearance.shape,
                "radius": appearance.radius,
                "opacity": appearance.opacity,
                "visibleTo": appearance.visible_to,
            }

        traits = esper.try_component(entity_id, ecs_comps_zone.Traits)
        if traits is not None:
            payload["properties/traits"] = list(traits.traits)

        stats = esper.try_component(entity_id, ecs_comps_zone.Stats)
        if stats is not None and stats.items:
            payload["properties/stats"] = dict(stats.items)

        messages = esper.try_component(entity_id, ecs_comps_zone.Messages)
        payload["properties/messages"] = list(messages.messages) if (messages is not None and messages.messages) else None

        zone_entry_log = esper.try_component(entity_id, ecs_comps_zone.ZoneEntryLog)
        if zone_entry_log is not None and zone_entry_log.zone_ids:
            payload["properties/zoneEntryLog"] = list(zone_entry_log.zone_ids)

        zone_exit_log = esper.try_component(entity_id, ecs_comps_zone.ZoneExitLog)
        if zone_exit_log is not None and zone_exit_log.zone_ids:
            payload["properties/zoneExitLog"] = list(zone_exit_log.zone_ids)

        return payload


