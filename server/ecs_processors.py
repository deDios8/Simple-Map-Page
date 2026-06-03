import esper
import math
import ecs_comps_geo as ecs_comps_geo
import ecs_comps_event as ecs_comps_event
import ecs_comps_client_request
from pyproj import CRS, Transformer
from shapely.geometry import Point
from session_db_state import GEO_OBJECTS_NODE, multi_path_patch


class ApplyClientRequests(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.NewLocation)):
            self.session_state.apply_new_location_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.AddObject)):
            self.session_state.apply_add_object_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.EditedObject)):
            self.session_state.apply_edited_object_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.DeletedObject)):
            self.session_state.apply_deleted_object_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.AddEvent)):
            self.session_state.apply_add_event_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.EditedEvent)):
            self.session_state.apply_edited_event_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.DeletedEvent)):
            self.session_state.apply_deleted_event_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_comps_client_request.DismissMessage)):
            self.session_state.apply_dismiss_message_request(entity_id)


class CheckZoneEntryExit(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        all_geo_entities = list(esper.get_components(
            ecs_comps_geo.Geometry,
            ecs_comps_geo.ID,
            ecs_comps_geo.Appearance,
        ))
        transformer_cache: dict = {}

        for entity_id, (geometry, id_component, _) in all_geo_entities:
            current_zones = set()
            for zone_entity_id, (zone_geometry, zone_id_component, zone_appearance) in all_geo_entities:
                if zone_entity_id == entity_id:
                    continue
                if id_component.id == zone_id_component.id:
                    continue

                zone_radius = zone_appearance.radius if zone_appearance is not None else 0

                if self.is_within_zone_intersect(
                    geometry.coordinates,
                    zone_geometry.coordinates,
                    zone_radius,
                    transformer_cache,
                ):
                    current_zones.add(str(zone_id_component.id))

            previous_within = esper.try_component(entity_id, ecs_comps_geo.WithinZones)
            previous_zones = set(previous_within.zone_ids) if previous_within else set()

            entered_zones = current_zones - previous_zones
            exited_zones = previous_zones - current_zones

            if entered_zones or exited_zones:
                display_name_comp = esper.try_component(entity_id, ecs_comps_geo.DisplayName)
                entity_display_name = display_name_comp.display_name if display_name_comp else id_component.id

            if entered_zones:
                zone_names = self._get_zone_names(entered_zones)
                esper.add_component(entity_id, ecs_comps_geo.EnteredZones(zone_ids=list(entered_zones)))
                print(f"[CheckZoneEntryExit] Entity '{entity_display_name}' entered zones: {zone_names}")
            if exited_zones:
                zone_names = self._get_zone_names(exited_zones)
                esper.add_component(entity_id, ecs_comps_geo.ExitedZones(zone_ids=list(exited_zones)))
                print(f"[CheckZoneEntryExit] Entity '{entity_display_name}' exited zones: {zone_names}")

    def _get_zone_names(self, zone_ids: set[str]) -> list[str]:
        """Convert zone IDs to display names for logging."""
        names = []
        for zone_id in zone_ids:
            zone_eid = self.session_state.GeoObjectEntityIds.get(zone_id)
            if zone_eid is not None:
                display_name_comp = esper.try_component(zone_eid, ecs_comps_geo.DisplayName)
                if display_name_comp:
                    names.append(display_name_comp.display_name)
                else:
                    names.append(zone_id)
            else:
                names.append(zone_id)
        return names

    def is_within_zone_distance(self, object_coordinates: list, zone: dict) -> bool:
        # Expected format for Point coordinates is [longitude, latitude].
        if not isinstance(object_coordinates, list) or len(object_coordinates) < 2:
            return False
        geometry = zone.get("geometry") if isinstance(zone, dict) else None
        properties = zone.get("properties") if isinstance(zone, dict) else None
        if not isinstance(geometry, dict) or not isinstance(properties, dict):
            return False

        zone_coordinates = geometry.get("coordinates")
        if not isinstance(zone_coordinates, list) or len(zone_coordinates) < 2:
            return False

        appearance = properties.get("appearance", {})
        if not isinstance(appearance, dict):
            appearance = {}

        object_radius_value = 0
        zone_radius_value = appearance.get("radius", 0)

        try:
            obj_lon = float(object_coordinates[0])
            obj_lat = float(object_coordinates[1])
            zone_lon = float(zone_coordinates[0])
            zone_lat = float(zone_coordinates[1])
            object_radius_m = float(object_radius_value)
            zone_radius_m = float(zone_radius_value)
        except (TypeError, ValueError):
            return False

        # Haversine distance in meters.
        earth_radius_m = 6371000.0
        obj_lat_rad = math.radians(obj_lat)
        zone_lat_rad = math.radians(zone_lat)
        delta_lat = math.radians(zone_lat - obj_lat)
        delta_lon = math.radians(zone_lon - obj_lon)

        a = (
            math.sin(delta_lat / 2.0) ** 2
            + math.cos(obj_lat_rad) * math.cos(zone_lat_rad) * math.sin(delta_lon / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        distance_m = earth_radius_m * c

        combined_radius_m = max(0.0, object_radius_m) + max(0.0, zone_radius_m)
        return distance_m <= combined_radius_m

    def is_within_zone_intersect(self, object_coordinates: list, zone_coordinates: list, zone_radius_value: float, transformer_cache: dict) -> bool:
        if not isinstance(object_coordinates, list) or len(object_coordinates) < 2:
            return False
        if not isinstance(zone_coordinates, list) or len(zone_coordinates) < 2:
            return False

        try:
            obj_lon = float(object_coordinates[0])
            obj_lat = float(object_coordinates[1])
            zone_lon = float(zone_coordinates[0])
            zone_lat = float(zone_coordinates[1])
            object_radius_m = 0.0
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

        object_point = Point(obj_x, obj_y)
        zone_center = Point(zone_x, zone_y)
        zone_area = zone_center.buffer(zone_radius_m)

        if object_radius_m <= 0.0:
            return object_point.within(zone_area) or object_point.touches(zone_area)

        object_area = object_point.buffer(object_radius_m)
        return object_area.intersects(zone_area)


class RemoveZoneEntryExit(esper.Processor):
    def __init__(self) -> None:
        super().__init__()
        
    def process(self) -> None:
        # Dispatcher: (component_type, set_operation, log_component_type)
        zone_updates = [
            (ecs_comps_geo.EnteredZones, lambda before, change: before | change, ecs_comps_geo.ZoneEntryLog),
            (ecs_comps_geo.ExitedZones, lambda before, change: before - change, ecs_comps_geo.ZoneExitLog),
        ]

        for component_type, set_operation, log_component_type in zone_updates:
            for entity_id, zone_component in list(esper.get_component(component_type)):
                zone_set = set(zone_component.zone_ids)

                # Update WithinZones
                within = esper.try_component(entity_id, ecs_comps_geo.WithinZones)
                before_zones = set(within.zone_ids) if within else set()
                within_zones = set_operation(before_zones, zone_set)

                if within_zones:
                    esper.add_component(entity_id, ecs_comps_geo.WithinZones(zone_ids=list(within_zones)))
                else:
                    try:
                        esper.remove_component(entity_id, ecs_comps_geo.WithinZones)
                    except KeyError:
                        pass

                # Append to log
                log = esper.try_component(entity_id, log_component_type)
                if log is None:
                    esper.add_component(entity_id, log_component_type(zone_ids=list(zone_component.zone_ids)))
                else:
                    log.zone_ids.extend(zone_component.zone_ids)

                # Mark entity as dirty to sync log to database
                esper.add_component(entity_id, ecs_comps_geo.GeoObjectDirty())

                # Remove temporary component
                try:
                    esper.remove_component(entity_id, component_type)
                except KeyError:
                    pass


class CriteriaProcessor(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state
        self._trigger_dispatch: dict = {
            comp_type: getattr(self, ecs_comps_event.TRIGGER_COMPONENT_HANDLER_NAMES[name])
            for name, comp_type in ecs_comps_event.TRIGGER_COMPONENT_MAP.items()
        }
        self._target_dispatch: dict = {
            comp_type: getattr(self, ecs_comps_event.TARGET_COMPONENT_HANDLER_NAMES[name])
            for name, comp_type in ecs_comps_event.TARGET_COMPONENT_MAP.items()
        }

    def process(self) -> None:
        geo_entity_ids = list(self.session_state.GeoObjectEntityIds.values())
        event_entity_ids = list(self.session_state.EventResultEntityIds.values())

        for event_entity_id in event_entity_ids:

            # --- Trigger criteria ---
            trigger_checks = []
            for comp_type, handler in self._trigger_dispatch.items():
                if comp := esper.try_component(event_entity_id, comp_type):
                    trigger_checks.append(lambda geo_eid, c=comp, h=handler: h(geo_eid, c))

            trigger_passed_any: set[int] = set()
            trigger_failed_any: set[int] = set()
            for geo_eid in geo_entity_ids:
                for check in trigger_checks:
                    if check(geo_eid):
                        trigger_passed_any.add(geo_eid)
                    else:
                        trigger_failed_any.add(geo_eid)

            all_trigger = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAllTriggerCriteria)
            if all_trigger:
                all_trigger.object_ids = list(trigger_passed_any - trigger_failed_any)
            any_trigger = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAnyTriggerCriteria)
            if any_trigger:
                any_trigger.object_ids = list(trigger_passed_any)

            # --- Target criteria ---
            target_checks = []
            for comp_type, handler in self._target_dispatch.items():
                if comp := esper.try_component(event_entity_id, comp_type):
                    target_checks.append(lambda geo_eid, c=comp, h=handler: h(geo_eid, c))

            target_passed_any: set[int] = set()
            target_failed_any: set[int] = set()
            for geo_eid in geo_entity_ids:
                for check in target_checks:
                    if check(geo_eid):
                        target_passed_any.add(geo_eid)
                    else:
                        target_failed_any.add(geo_eid)

            all_target = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAllTargetCriteria)
            if all_target:
                all_target.object_ids = list(target_passed_any - target_failed_any)
            any_target = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAnyTargetCriteria)
            if any_target:
                any_target.object_ids = list(target_passed_any)

    def _get_entity_tags(self, eid: int) -> set[str]:
        tags: set[str] = set()
        if dn := esper.try_component(eid, ecs_comps_geo.DisplayName):
            tags.add(dn.display_name)
        if traits := esper.try_component(eid, ecs_comps_geo.Traits):
            tags.update(traits.traits)
        if stats := esper.try_component(eid, ecs_comps_geo.Stats):
            if stats.items:
                tags.update(stats.items.keys())
        return tags


    def _check_has_tags(self, geo_eid: int, component) -> bool:
        return any(tag in self._get_entity_tags(geo_eid) for tag in component.tags)

    def _check_lacks_tags(self, geo_eid: int, component) -> bool:
        return not self._check_has_tags(geo_eid, component)


    def _check_is_within(self, geo_eid: int, component) -> bool:
        within = esper.try_component(geo_eid, ecs_comps_geo.WithinZones)
        if not within:
            return False
        tag_set = set(component.tags)
        for zone_id in within.zone_ids:
            zone_eid = self.session_state.GeoObjectEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return True
        return False

    def _check_is_not_within(self, geo_eid: int, component) -> bool:
        return not self._check_is_within(geo_eid, component)


    def _check_just_in_zone(self, geo_eid: int, component, temp_component_type) -> bool:
        """Helper to check if entity is currently entering/exiting a zone matching component.tags."""
        temp_component = esper.try_component(geo_eid, temp_component_type)
        if not temp_component:
            return False
        tag_set = set(component.tags)
        for zone_id in temp_component.zone_ids:
            zone_eid = self.session_state.GeoObjectEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return True
        return False

    def _check_just_entered(self, geo_eid: int, component) -> bool:
        return self._check_just_in_zone(geo_eid, component, ecs_comps_geo.EnteredZones)

    def _check_just_exited(self, geo_eid: int, component) -> bool:
        return self._check_just_in_zone(geo_eid, component, ecs_comps_geo.ExitedZones)


    def _check_first_in_zone(self, geo_eid: int, component, temp_component_type, log_component_type) -> bool:
        """Helper to check if entity is currently entering/exiting a zone for the first time.
        Must run BEFORE RemoveZoneEntryExit appends to the log.
        """
        temp_component = esper.try_component(geo_eid, temp_component_type)
        if not temp_component:
            return False
        
        tag_set = set(component.tags)
        log = esper.try_component(geo_eid, log_component_type)
        existing_zones = set(log.zone_ids) if log else set()
        
        # Check if any currently changed zone matches tags and is NOT in the historical log
        for zone_id in temp_component.zone_ids:
            if zone_id in existing_zones:
                continue  # Already in log (not first time)
            zone_eid = self.session_state.GeoObjectEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return True
        return False

    def _check_first_entered(self, geo_eid: int, component) -> bool:
        return self._check_first_in_zone(geo_eid, component, ecs_comps_geo.EnteredZones, ecs_comps_geo.ZoneEntryLog)

    def _check_first_exited(self, geo_eid: int, component) -> bool:
        return self._check_first_in_zone(geo_eid, component, ecs_comps_geo.ExitedZones, ecs_comps_geo.ZoneExitLog)


    def _check_ever_in_log(self, geo_eid: int, component, log_component_type) -> bool:
        """Helper to check if any zone in historical log matches component.tags."""
        log = esper.try_component(geo_eid, log_component_type)
        if not log or not log.zone_ids:
            return False
        
        tag_set = set(component.tags)
        for zone_id in log.zone_ids:
            zone_eid = self.session_state.GeoObjectEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return True
        return False

    def _check_ever_entered(self, geo_eid: int, component) -> bool:
        return self._check_ever_in_log(geo_eid, component, ecs_comps_geo.ZoneEntryLog)

    def _check_ever_exited(self, geo_eid: int, component) -> bool:
        return self._check_ever_in_log(geo_eid, component, ecs_comps_geo.ZoneExitLog)


    def _check_recently_in_log(self, geo_eid: int, component, log_component_type) -> bool:
        """Helper to check if the last zone in a log matches component.tags."""
        log = esper.try_component(geo_eid, log_component_type)
        if not log or not log.zone_ids:
            return False
        
        # Validate component has tags attribute
        if not hasattr(component, 'tags') or not component.tags:
            return False
        
        tag_set = set(component.tags)
        # Get the most recent zone (last item in the log)
        last_zone_id = log.zone_ids[-1]
        
        zone_eid = self.session_state.GeoObjectEntityIds.get(last_zone_id)
        if zone_eid is None:
            return False  # Zone was deleted or doesn't exist
        
        return bool(self._get_entity_tags(zone_eid) & tag_set)

    def _check_recently_entered(self, geo_eid: int, component) -> bool:
        return self._check_recently_in_log(geo_eid, component, ecs_comps_geo.ZoneEntryLog)

    def _check_recently_exited(self, geo_eid: int, component) -> bool:
        return self._check_recently_in_log(geo_eid, component, ecs_comps_geo.ZoneExitLog)


    def _check_is_visible(self, geo_eid: int, component) -> bool:
        appearance = esper.try_component(geo_eid, ecs_comps_geo.Appearance)
        if not appearance:
            return False
        return any(tag in appearance.visible_to for tag in component.tags)

    def _check_is_not_visible(self, geo_eid: int, component) -> bool:
        return not self._check_is_visible(geo_eid, component)



class EventProcessor(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state
        self._result_dispatch: dict = {
            comp_type: getattr(self, ecs_comps_event.EVENT_RESULT_COMPONENT_HANDLER_NAMES[name])
            for name, comp_type in ecs_comps_event.EVENT_RESULT_COMPONENT_MAP.items()
        }

    def process(self) -> None:
        event_entity_ids = list(self.session_state.EventResultEntityIds.values())

        ## For each event, check if any triggers have met all trigger criteria, and if so, apply results to targets.
        for event_entity_id in event_entity_ids:

            # Read trigger/target results computed by CriteriaProcessor
            trigger_comp = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAllTriggerCriteria)
            if not trigger_comp or not trigger_comp.object_ids:
                continue

            target_comp = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAllTargetCriteria)
            if not target_comp or not target_comp.object_ids:
                continue

            # Apply this event's result components to each qualifying target geo object
            for target_entity_id in target_comp.object_ids:

                results_to_apply = []
                for comp_type, handler in self._result_dispatch.items():
                    if comp := esper.try_component(event_entity_id, comp_type):
                        results_to_apply.append(lambda eid, c=comp, h=handler: h(eid, c))

                for result in results_to_apply:
                    result(target_entity_id)

                if results_to_apply:
                    esper.add_component(target_entity_id, ecs_comps_geo.GeoObjectDirty())

    def _grant_visibility(self, target_entity_id: int, component: ecs_comps_event.ResultGrantVisibility) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_geo.Appearance):
            for tag in component.tags:
                if tag not in appearance.visible_to:
                    appearance.visible_to.append(tag)

    def _revoke_visibility(self, target_entity_id: int, component: ecs_comps_event.ResultRevokeVisibility) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_geo.Appearance):
            for tag in component.tags:
                if tag in appearance.visible_to:
                    appearance.visible_to.remove(tag)

    def _toggle_visibility(self, target_entity_id: int, component: ecs_comps_event.ResultToggleVisibility) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_geo.Appearance):
            for tag in component.tags:
                if tag in appearance.visible_to:
                    appearance.visible_to.remove(tag)
                else:
                    appearance.visible_to.append(tag)

    def _set_color(self, target_entity_id: int, component: ecs_comps_event.ResultSetColor) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_geo.Appearance):
            appearance.color = component.color

    def _set_radius(self, target_entity_id: int, component: ecs_comps_event.ResultSetRadius) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_geo.Appearance):
            appearance.radius = component.radius

    def _change_radius(self, target_entity_id: int, component: ecs_comps_event.ResultChangeRadius) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_geo.Appearance):
            appearance.radius += component.change

    def _grant_traits(self, target_entity_id: int, component: ecs_comps_event.ResultGrantTraits) -> None:
        traits = esper.try_component(target_entity_id, ecs_comps_geo.Traits)
        if traits is None:
            esper.add_component(target_entity_id, ecs_comps_geo.Traits(traits=list(component.tags)))
        else:
            for trait in component.tags: #preserves order and avoids duplicates
                if trait not in traits.traits:
                    traits.traits.append(trait)

    def _revoke_traits(self, target_entity_id: int, component: ecs_comps_event.ResultRevokeTraits) -> None:
        if traits := esper.try_component(target_entity_id, ecs_comps_geo.Traits):
            for trait in component.tags:
                if trait in traits.traits:
                    traits.traits.remove(trait)

    def _toggle_traits(self, target_entity_id: int, component: ecs_comps_event.ResultToggleTraits) -> None:
        traits = esper.try_component(target_entity_id, ecs_comps_geo.Traits)
        if traits is None:
            esper.add_component(target_entity_id, ecs_comps_geo.Traits(traits=list(component.tags)))
        else:
            for trait in component.tags:
                if trait in traits.traits:
                    traits.traits.remove(trait)
                else:
                    traits.traits.append(trait)

    def _revoke_stats(self, target_entity_id: int, component: ecs_comps_event.ResultRevokeStats) -> None:
        # TODO: implement — define the item format in ResultRevokeStats.stats
        pass

    def _toggle_stats_to_values(self, target_entity_id: int, component: ecs_comps_event.ResultToggleStatsWithValue) -> None:
        # TODO: implement — define the item format in ResultToggleStatsWithValue.stats
        pass

    def _set_stats_to_values(self, target_entity_id: int, component: ecs_comps_event.ResultSetStatsToValues) -> None:
        stats = esper.try_component(target_entity_id, ecs_comps_geo.Stats)
        if stats is None:
            esper.add_component(target_entity_id, ecs_comps_geo.Stats(items=dict(component.stats_to_values)))
        else:
            if stats.items is None:
                stats.items = {}
            stats.items.update(component.stats_to_values)

    def _change_stats_by_values(self, target_entity_id: int, component: ecs_comps_event.ResultChangeStatsByValues) -> None:
        if stats := esper.try_component(target_entity_id, ecs_comps_geo.Stats):
            if stats.items:
                for key, delta in component.stats_to_values.items():
                    if key in stats.items:
                        stats.items[key] += delta

    def _popup_message(self, target_entity_id: int, component: ecs_comps_event.ResultPopupMessage) -> None:
        messages = esper.try_component(target_entity_id, ecs_comps_geo.Messages)
        if messages is None:
            esper.add_component(target_entity_id, ecs_comps_geo.Messages(messages=[component.text]))
        else:
            messages.messages.append(component.text)


class SyncGeoObjectsToDatabase(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state
        self._cache: dict[int, dict] = {}

    def process(self) -> None:
        geo_by_entity = {entity_id: key for key, entity_id in self.session_state.GeoObjectEntityIds.items()}
        multi_path_payload: dict = {}

        for entity_id, _ in list(esper.get_component(ecs_comps_geo.GeoObjectDirty)):
            key = geo_by_entity.get(entity_id)
            if key is None:
                try:
                    esper.remove_component(entity_id, ecs_comps_geo.GeoObjectDirty)
                except KeyError:
                    pass
                continue

            fields = self._build_properties_payload(entity_id)
            if self._cache.get(entity_id) != fields:
                for field_path, value in fields.items():
                    multi_path_payload[f"{GEO_OBJECTS_NODE}/{key}/{field_path}"] = value
                self._cache[entity_id] = fields

            try:
                esper.remove_component(entity_id, ecs_comps_geo.GeoObjectDirty)
            except KeyError:
                pass

        if multi_path_payload:
            multi_path_patch(
                self.session_state.database_url,
                self.session_state.session_name,
                multi_path_payload,
            )

    def _build_properties_payload(self, entity_id: int) -> dict:
        payload = {}

        appearance = esper.try_component(entity_id, ecs_comps_geo.Appearance)
        if appearance is not None:
            payload["properties/appearance"] = {
                "color": appearance.color,
                "shape": appearance.shape,
                "radius": appearance.radius,
                "visibleTo": appearance.visible_to,
            }

        traits = esper.try_component(entity_id, ecs_comps_geo.Traits)
        if traits is not None:
            payload["properties/traits"] = list(traits.traits)

        stats = esper.try_component(entity_id, ecs_comps_geo.Stats)
        if stats is not None and stats.items:
            payload["properties/stats"] = dict(stats.items)

        messages = esper.try_component(entity_id, ecs_comps_geo.Messages)
        payload["properties/messages"] = list(messages.messages) if (messages is not None and messages.messages) else None

        zone_entry_log = esper.try_component(entity_id, ecs_comps_geo.ZoneEntryLog)
        if zone_entry_log is not None and zone_entry_log.zone_ids:
            payload["properties/zoneEntryLog"] = list(zone_entry_log.zone_ids)

        zone_exit_log = esper.try_component(entity_id, ecs_comps_geo.ZoneExitLog)
        if zone_exit_log is not None and zone_exit_log.zone_ids:
            payload["properties/zoneExitLog"] = list(zone_exit_log.zone_ids)

        return payload


