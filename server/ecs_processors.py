import esper
import math
import ecs_geo_components
import ecs_event_components
from pyproj import CRS, Transformer
from shapely.geometry import Point
from db_stream import GEO_OBJECTS_NODE, multi_path_patch


class ApplyClientRequests(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        for entity_id, _ in list(esper.get_component(ecs_geo_components.NewLocation)):
            self.session_state.apply_new_location_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_geo_components.AddObject)):
            self.session_state.apply_add_object_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_geo_components.EditedObject)):
            self.session_state.apply_edited_object_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_geo_components.DeletedObject)):
            self.session_state.apply_deleted_object_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_event_components.AddCriteria)):
            self.session_state.apply_add_criteria_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_event_components.EditedCriteria)):
            self.session_state.apply_edited_criteria_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_event_components.DeletedCriteria)):
            self.session_state.apply_deleted_criteria_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_event_components.AddEvent)):
            self.session_state.apply_add_event_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_event_components.EditedEvent)):
            self.session_state.apply_edited_event_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_event_components.DeletedEvent)):
            self.session_state.apply_deleted_event_request(entity_id)

        for entity_id, _ in list(esper.get_component(ecs_geo_components.DismissMessage)):
            self.session_state.apply_dismiss_message_request(entity_id)


class CheckZoneEntryExit(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        all_geo_entities = list(esper.get_components(
            ecs_geo_components.Geometry,
            ecs_geo_components.ID,
            ecs_geo_components.Appearance,
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

            previous_within = esper.try_component(entity_id, ecs_geo_components.WithinZones)
            previous_zones = set(previous_within.zone_ids) if previous_within else set()

            entered_zones = current_zones - previous_zones
            exited_zones = previous_zones - current_zones

            if entered_zones:
                esper.add_component(entity_id, ecs_geo_components.EnteredZones(zone_ids=list(entered_zones)))
                print(f"[CheckZoneEntryExit] Entity {id_component.id} entered zones: {entered_zones}")
            if exited_zones:
                esper.add_component(entity_id, ecs_geo_components.ExitedZones(zone_ids=list(exited_zones)))
                print(f"[CheckZoneEntryExit] Entity {id_component.id} exited zones: {exited_zones}")
                

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
        for entity_id, entered in list(esper.get_component(ecs_geo_components.EnteredZones)):
            entered_set = set(entered.zone_ids)

            # WithinZones: add entered zones
            within = esper.try_component(entity_id, ecs_geo_components.WithinZones)
            before_zones = set(within.zone_ids) if within else set()
            within_zones = before_zones | entered_set

            esper.add_component(entity_id, ecs_geo_components.WithinZones(zone_ids=list(within_zones)))
            try:
                esper.remove_component(entity_id, ecs_geo_components.EnteredZones)
            except KeyError:
                pass

        for entity_id, exited in list(esper.get_component(ecs_geo_components.ExitedZones)):
            exited_set = set(exited.zone_ids)

            # WithinZones: remove exited zones
            within = esper.try_component(entity_id, ecs_geo_components.WithinZones)
            if within is not None:
                before_zones = set(within.zone_ids)
                within_zones = before_zones - exited_set

                if within_zones:
                    esper.add_component(entity_id, ecs_geo_components.WithinZones(zone_ids=list(within_zones)))
                else:
                    try:
                        esper.remove_component(entity_id, ecs_geo_components.WithinZones)
                    except KeyError:
                        pass

            try:
                esper.remove_component(entity_id, ecs_geo_components.ExitedZones)
            except KeyError:
                pass


class CriteriaProcessor(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state
        self._trigger_dispatch: dict = {
            comp_type: getattr(self, ecs_event_components.TRIGGER_COMPONENT_HANDLER_NAMES[name])
            for name, comp_type in ecs_event_components.TRIGGER_COMPONENT_MAP.items()
        }
        self._target_dispatch: dict = {
            comp_type: getattr(self, ecs_event_components.TARGET_COMPONENT_HANDLER_NAMES[name])
            for name, comp_type in ecs_event_components.TARGET_COMPONENT_MAP.items()
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

            all_trigger = esper.try_component(event_entity_id, ecs_event_components.ObjectsThatMetAllTriggerCriteria)
            if all_trigger:
                all_trigger.object_ids = list(trigger_passed_any - trigger_failed_any)
            any_trigger = esper.try_component(event_entity_id, ecs_event_components.ObjectsThatMetAnyTriggerCriteria)
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

            all_target = esper.try_component(event_entity_id, ecs_event_components.ObjectsThatMetAllTargetCriteria)
            if all_target:
                all_target.object_ids = list(target_passed_any - target_failed_any)
            any_target = esper.try_component(event_entity_id, ecs_event_components.ObjectsThatMetAnyTargetCriteria)
            if any_target:
                any_target.object_ids = list(target_passed_any)

    def _get_entity_tags(self, eid: int) -> set[str]:
        tags: set[str] = set()
        if dn := esper.try_component(eid, ecs_geo_components.DisplayName):
            tags.add(dn.display_name)
        if traits := esper.try_component(eid, ecs_geo_components.Traits):
            tags.update(traits.traits)
        if stats := esper.try_component(eid, ecs_geo_components.Stats):
            if stats.items:
                tags.update(stats.items.keys())
        return tags

    def _check_has_tags(self, geo_eid: int, component) -> bool:
        return any(tag in self._get_entity_tags(geo_eid) for tag in component.tags)

    def _check_is_within(self, geo_eid: int, component) -> bool:
        within = esper.try_component(geo_eid, ecs_geo_components.WithinZones)
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
        within = esper.try_component(geo_eid, ecs_geo_components.WithinZones)
        if not within:
            return True  # If the entity has no WithinZones component, it is considered "not within" any zones.
        tag_set = set(component.tags)
        for zone_id in within.zone_ids:
            zone_eid = self.session_state.GeoObjectEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return False
        return True

    def _check_just_entered(self, geo_eid: int, component) -> bool:
        entered = esper.try_component(geo_eid, ecs_geo_components.EnteredZones)
        if not entered:
            return False
        tag_set = set(component.tags)
        for zone_id in entered.zone_ids:
            zone_eid = self.session_state.GeoObjectEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return True
        return False

    def _check_just_exited(self, geo_eid: int, component) -> bool:
        exited = esper.try_component(geo_eid, ecs_geo_components.ExitedZones)
        if not exited:
            return False
        tag_set = set(component.tags)
        for zone_id in exited.zone_ids:
            zone_eid = self.session_state.GeoObjectEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return True
        return False

    def _check_is_visible(self, geo_eid: int, component) -> bool:
        appearance = esper.try_component(geo_eid, ecs_geo_components.Appearance)
        if not appearance:
            return False
        return any(tag in appearance.visible_to for tag in component.tags)

    def _check_is_not_visible(self, geo_eid: int, component) -> bool:
        appearance = esper.try_component(geo_eid, ecs_geo_components.Appearance)
        if not appearance:
            return True  # If the entity has no Appearance component, it is considered "not visible" to any tags.
        return all(tag not in appearance.visible_to for tag in component.tags)

    def _check_first_entered(self, geo_eid: int, component) -> bool:
        # TODO: implement — TriggerFirstEntered / TargetFirstEntered check
        return False


class EventProcessor(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state
        self._result_dispatch: dict = {
            comp_type: getattr(self, ecs_event_components.EVENT_RESULT_COMPONENT_HANDLER_NAMES[name])
            for name, comp_type in ecs_event_components.EVENT_RESULT_COMPONENT_MAP.items()
        }

    def process(self) -> None:
        event_entity_ids = list(self.session_state.EventResultEntityIds.values())

        ## For each event, check if any triggers have met all trigger criteria, and if so, apply results to targets.
        for event_entity_id in event_entity_ids:

            # Read trigger/target results computed by CriteriaProcessor
            trigger_comp = esper.try_component(event_entity_id, ecs_event_components.ObjectsThatMetAllTriggerCriteria)
            if not trigger_comp or not trigger_comp.object_ids:
                continue

            target_comp = esper.try_component(event_entity_id, ecs_event_components.ObjectsThatMetAllTargetCriteria)
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
                    esper.add_component(target_entity_id, ecs_geo_components.GeoObjectDirty())

    def _grant_visibility(self, target_entity_id: int, component: ecs_event_components.ResultGrantVisibility) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_geo_components.Appearance):
            for tag in component.tags:
                if tag not in appearance.visible_to:
                    appearance.visible_to.append(tag)

    def _revoke_visibility(self, target_entity_id: int, component: ecs_event_components.ResultRevokeVisibility) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_geo_components.Appearance):
            for tag in component.tags:
                if tag in appearance.visible_to:
                    appearance.visible_to.remove(tag)

    def _toggle_visibility(self, target_entity_id: int, component: ecs_event_components.ResultToggleVisibility) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_geo_components.Appearance):
            for tag in component.tags:
                if tag in appearance.visible_to:
                    appearance.visible_to.remove(tag)
                else:
                    appearance.visible_to.append(tag)

    def _set_color(self, target_entity_id: int, component: ecs_event_components.ResultSetColor) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_geo_components.Appearance):
            appearance.color = component.color

    def _set_radius(self, target_entity_id: int, component: ecs_event_components.ResultSetRadius) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_geo_components.Appearance):
            appearance.radius = component.radius

    def _change_radius(self, target_entity_id: int, component: ecs_event_components.ResultChangeRadius) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_geo_components.Appearance):
            appearance.radius += component.change

    def _grant_traits(self, target_entity_id: int, component: ecs_event_components.ResultGrantTraits) -> None:
        traits = esper.try_component(target_entity_id, ecs_geo_components.Traits)
        if traits is None:
            esper.add_component(target_entity_id, ecs_geo_components.Traits(traits=list(component.tags)))
        else:
            for trait in component.tags: #preserves order and avoids duplicates
                if trait not in traits.traits:
                    traits.traits.append(trait)

    def _revoke_traits(self, target_entity_id: int, component: ecs_event_components.ResultRevokeTraits) -> None:
        if traits := esper.try_component(target_entity_id, ecs_geo_components.Traits):
            for trait in component.tags:
                if trait in traits.traits:
                    traits.traits.remove(trait)

    def _toggle_traits(self, target_entity_id: int, component: ecs_event_components.ResultToggleTraits) -> None:
        traits = esper.try_component(target_entity_id, ecs_geo_components.Traits)
        if traits is None:
            esper.add_component(target_entity_id, ecs_geo_components.Traits(traits=list(component.tags)))
        else:
            for trait in component.tags:
                if trait in traits.traits:
                    traits.traits.remove(trait)
                else:
                    traits.traits.append(trait)

    def _revoke_stats(self, target_entity_id: int, component: ecs_event_components.ResultRevokeStats) -> None:
        # TODO: implement — define the item format in ResultRevokeStats.stats
        pass

    def _toggle_stats_to_values(self, target_entity_id: int, component: ecs_event_components.ResultToggleStats) -> None:
        # TODO: implement — define the item format in ResultToggleStats.stats
        pass

    def _set_stats_to_values(self, target_entity_id: int, component: ecs_event_components.ResultSetStatsToValues) -> None:
        stats = esper.try_component(target_entity_id, ecs_geo_components.Stats)
        if stats is None:
            esper.add_component(target_entity_id, ecs_geo_components.Stats(items=dict(component.stats_to_values)))
        else:
            if stats.items is None:
                stats.items = {}
            stats.items.update(component.stats_to_values)

    def _change_stats_by_values(self, target_entity_id: int, component: ecs_event_components.ResultChangeStatsByValues) -> None:
        if stats := esper.try_component(target_entity_id, ecs_geo_components.Stats):
            if stats.items:
                for key, delta in component.stats_to_values.items():
                    if key in stats.items:
                        stats.items[key] += delta

    def _popup_message(self, target_entity_id: int, component: ecs_event_components.ResultPopupMessage) -> None:
        messages = esper.try_component(target_entity_id, ecs_geo_components.Messages)
        if messages is None:
            esper.add_component(target_entity_id, ecs_geo_components.Messages(messages=[component.text]))
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

        for entity_id, _ in list(esper.get_component(ecs_geo_components.GeoObjectDirty)):
            key = geo_by_entity.get(entity_id)
            if key is None:
                try:
                    esper.remove_component(entity_id, ecs_geo_components.GeoObjectDirty)
                except KeyError:
                    pass
                continue

            fields = self._build_properties_payload(entity_id)
            if self._cache.get(entity_id) != fields:
                for field_path, value in fields.items():
                    multi_path_payload[f"{GEO_OBJECTS_NODE}/{key}/{field_path}"] = value
                self._cache[entity_id] = fields

            try:
                esper.remove_component(entity_id, ecs_geo_components.GeoObjectDirty)
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

        appearance = esper.try_component(entity_id, ecs_geo_components.Appearance)
        if appearance is not None:
            payload["properties/appearance"] = {
                "color": appearance.color,
                "shape": appearance.shape,
                "radius": appearance.radius,
                "visibleTo": appearance.visible_to,
            }

        traits = esper.try_component(entity_id, ecs_geo_components.Traits)
        if traits is not None:
            payload["properties/traits"] = traits.traits

        stats = esper.try_component(entity_id, ecs_geo_components.Stats)
        if stats is not None and stats.items:
            payload["properties/stats"] = stats.items

        messages = esper.try_component(entity_id, ecs_geo_components.Messages)
        payload["properties/messages"] = messages.messages if (messages is not None and messages.messages) else None

        return payload


