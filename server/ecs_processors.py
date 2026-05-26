import esper
import ecs_geo_components
import ecs_event_components
import math
from pyproj import CRS, Transformer
from shapely.geometry import Point
from db_stream import GEO_OBJECTS_NODE, CLIENT_REQUESTS_NODE


class ApplyClientRequests(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        for entity_id, _marker in list(esper.get_component(ecs_geo_components.NewLocation)):
            self.session_state.apply_new_location_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_geo_components.AddObject)):
            self.session_state.apply_add_object_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_geo_components.EditedObject)):
            self.session_state.apply_edited_object_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_geo_components.DeletedObject)):
            self.session_state.apply_deleted_object_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_event_components.AddCriteria)):
            self.session_state.apply_add_criteria_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_event_components.EditedCriteria)):
            self.session_state.apply_edited_criteria_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_event_components.DeletedCriteria)):
            self.session_state.apply_deleted_criteria_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_event_components.AddEvent)):
            self.session_state.apply_add_event_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_event_components.EditedEvent)):
            self.session_state.apply_edited_event_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_event_components.DeletedEvent)):
            self.session_state.apply_deleted_event_request(entity_id)

class CheckZoneEntryExit(esper.Processor):
    def __init__(self) -> None:
        super().__init__()
        
    def process(self) -> None:
        all_entities = list(esper.get_components(
            ecs_geo_components.Geometry,
            ecs_geo_components.ID,
            ecs_geo_components.Appearance,
        ))
        transformer_cache: dict = {}

        for entity_id, (geometry, id_component, _) in all_entities:
            current_zones = set()
            for zone_entity_id, (zone_geometry, zone_id_component, zone_appearance) in all_entities:
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
            object_radius_m = float(object_radius_value) * 0.3
            zone_radius_m = float(zone_radius_value) * 0.3
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
            zone_radius_m = max(0.0, float(zone_radius_value) * 0.3)
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

class SyncZoneBordersToDatabase(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        ss = self.session_state
        geo_by_entity = {entity_id: key for key, entity_id in ss.GeoObjectEntityIds.items()}
        req_by_entity = {entity_id: key for key, entity_id in ss.ClientRequestEntityIds.items()}

        for entity_id, _ in list(esper.get_component(ecs_geo_components.ZoneBordersDirty)):
            geo_key = geo_by_entity.get(entity_id)
            req_key = req_by_entity.get(entity_id)

            if geo_key is not None:
                ss._patch_zone_borders(GEO_OBJECTS_NODE, geo_key, entity_id)
            elif req_key is not None:
                ss._patch_zone_borders(CLIENT_REQUESTS_NODE, req_key, entity_id)

            try:
                esper.remove_component(entity_id, ecs_geo_components.ZoneBordersDirty)
            except KeyError:
                pass

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
            if within_zones != before_zones:
                esper.add_component(entity_id, ecs_geo_components.ZoneBordersDirty())

            # NotWithinZones: remove entered zones
            not_within = esper.try_component(entity_id, ecs_geo_components.NotWithinZones)
            if not_within is not None:
                not_within_zones = set(not_within.zone_ids) - entered_set
                if not_within_zones:
                    esper.add_component(entity_id, ecs_geo_components.NotWithinZones(zone_ids=list(not_within_zones)))
                else:
                    try:
                        esper.remove_component(entity_id, ecs_geo_components.NotWithinZones)
                    except KeyError:
                        pass

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

                if within_zones != before_zones:
                    esper.add_component(entity_id, ecs_geo_components.ZoneBordersDirty())

            # NotWithinZones: add exited zones
            not_within = esper.try_component(entity_id, ecs_geo_components.NotWithinZones)
            not_within_zones = (set(not_within.zone_ids) if not_within else set()) | exited_set

            esper.add_component(entity_id, ecs_geo_components.NotWithinZones(zone_ids=list(not_within_zones)))

            try:
                esper.remove_component(entity_id, ecs_geo_components.ExitedZones)
            except KeyError:
                pass

class CriteriaProcessor(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        geo_entity_ids = list(self.session_state.GeoObjectEntityIds.values())

        for criteria_entity_id, (any_criterion, all_criteria, _) in esper.get_components(
            ecs_event_components.ObjectsThatMetAnyCriteria,
            ecs_event_components.ObjectsThatMetAllCriteria,
            ecs_geo_components.ID,
        ):
            any_criterion.object_ids = []
            all_criteria.object_ids = []

            # Collect active criterion for this criteria entity
            criteria_checks = []
            if comp := esper.try_component(criteria_entity_id, ecs_event_components.CriteriaHasTags):
                criteria_checks.append(lambda geo_eid, c=comp: self._check_has_tags(geo_eid, c))
            if comp := esper.try_component(criteria_entity_id, ecs_event_components.CriteriaIsWithin):
                criteria_checks.append(lambda geo_eid, c=comp: self._check_is_within(geo_eid, c))
            if comp := esper.try_component(criteria_entity_id, ecs_event_components.CriteriaJustEntered):
                criteria_checks.append(lambda geo_eid, c=comp: self._check_just_entered(geo_eid, c))
            if comp := esper.try_component(criteria_entity_id, ecs_event_components.CriteriaJustExited):
                criteria_checks.append(lambda geo_eid, c=comp: self._check_just_exited(geo_eid, c))
            if comp := esper.try_component(criteria_entity_id, ecs_event_components.CriteriaIsVisible):
                criteria_checks.append(lambda geo_eid, c=comp: self._check_is_visible(geo_eid, c))
            if comp := esper.try_component(criteria_entity_id, ecs_event_components.CriteriaIsNotVisible):
                criteria_checks.append(lambda geo_eid, c=comp: self._check_is_not_visible(geo_eid, c))
            if comp := esper.try_component(criteria_entity_id, ecs_event_components.CriteriaFirstEntered):
                criteria_checks.append(lambda geo_eid, c=comp: self._check_first_entered(geo_eid, c))

            if not criteria_checks:
                continue

            # passed_any: met at least one criterion; failed_any: failed at least one.
            # met_all = passed_any - failed_any
            passed_any: set[int] = set()
            failed_any: set[int] = set()

            for geo_eid in geo_entity_ids:
                for check in criteria_checks:
                    if check(geo_eid):
                        passed_any.add(geo_eid)
                    else:
                        failed_any.add(geo_eid)

            any_criterion.object_ids = list(passed_any)
            all_criteria.object_ids = list(passed_any - failed_any)

    def _check_has_tags(self, geo_eid: int, component: ecs_event_components.CriteriaHasTags) -> bool:
        geo_tags: set[str] = set()
        if dn := esper.try_component(geo_eid, ecs_geo_components.DisplayName):
            geo_tags.add(dn.display_name)
        if traits := esper.try_component(geo_eid, ecs_geo_components.Traits):
            geo_tags.update(traits.traits)
        if stats := esper.try_component(geo_eid, ecs_geo_components.Stats):
            if stats.items:
                geo_tags.update(stats.items.keys())
        return any(tag in geo_tags for tag in component.tags)

    def _check_is_within(self, geo_eid: int, component: ecs_event_components.CriteriaIsWithin) -> bool:
        # TODO: implement
        return False

    def _check_just_entered(self, geo_eid: int, component: ecs_event_components.CriteriaJustEntered) -> bool:
        # TODO: implement
        return False

    def _check_just_exited(self, geo_eid: int, component: ecs_event_components.CriteriaJustExited) -> bool:
        # TODO: implement
        return False

    def _check_is_visible(self, geo_eid: int, component: ecs_event_components.CriteriaIsVisible) -> bool:
        # TODO: implement
        return False

    def _check_is_not_visible(self, geo_eid: int, component: ecs_event_components.CriteriaIsNotVisible) -> bool:
        # TODO: implement
        return False

    def _check_first_entered(self, geo_eid: int, component: ecs_event_components.CriteriaFirstEntered) -> bool:
        # TODO: implement
        return False
    
class EventProcessor(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        geo_entity_ids = list(self.session_state.GeoObjectEntityIds.values())

        ## For each event, check if any of its triggers have met all trigger criteria, and if so, apply the event's result to its targets that have met all target criteria.
        for event_entity_id, (event_id_comp, event_display_name, event_triggers, event_targets) in esper.get_components(
            ecs_geo_components.ID,
            ecs_geo_components.DisplayName,
            ecs_event_components.EventTriggerNames,
            ecs_event_components.EventTargetNames,
        ):
            
            event_trigger_ids = event_triggers.criteria_ids
            event_target_ids = event_targets.criteria_ids

            # Get the objects that met all criteria for each trigger and target
            trigger_objects_sets = []
            for trigger_id in event_trigger_ids:
                if trigger_comp := esper.try_component(trigger_id, ecs_event_components.ObjectsThatMetAllCriteria):
                    trigger_objects_sets.append(set(trigger_comp.object_ids))
            target_objects_sets = []
            for target_id in event_target_ids:
                if target_comp := esper.try_component(target_id, ecs_event_components.ObjectsThatMetAllCriteria):
                    target_objects_sets.append(set(target_comp.object_ids))

            # Check if any trigger has met all criteria
            trigger_met = any(trigger_objects_sets)

            if trigger_met:
                # If a trigger has met all criteria, apply the event's result to targets that have met all criteria
                for target_objects in target_objects_sets:
                    for target_entity_id in target_objects:

                        results_to_apply = []

                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultSetVisibility):
                            results_to_apply.append(lambda eid, c=comp: self._set_visibility(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultToggleVisibility):
                            results_to_apply.append(lambda eid, c=comp: self._toggle_visibility(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultChangeColor):
                            results_to_apply.append(lambda eid, c=comp: self._change_color(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultChangeRadius):
                            results_to_apply.append(lambda eid, c=comp: self._change_radius(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultAddTraits):
                            results_to_apply.append(lambda eid, c=comp: self._add_traits(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultRemoveTraits):
                            results_to_apply.append(lambda eid, c=comp: self._remove_traits(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultToggleTraits):
                            results_to_apply.append(lambda eid, c=comp: self._toggle_traits(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultAddStats):
                            results_to_apply.append(lambda eid, c=comp: self._add_stats(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultRemoveStats):
                            results_to_apply.append(lambda eid, c=comp: self._remove_stats(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultToggleStats):
                            results_to_apply.append(lambda eid, c=comp: self._toggle_stats(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultSetStatsToValues):
                            results_to_apply.append(lambda eid, c=comp: self._set_stats_to_values(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultIncreaseStatsByValues):
                            results_to_apply.append(lambda eid, c=comp: self._increase_stats_by_values(eid, c))
                        if comp := esper.try_component(event_entity_id, ecs_event_components.ResultDecreaseStatsByValues):
                            results_to_apply.append(lambda eid, c=comp: self._decrease_stats_by_values(eid, c))

                        for result in results_to_apply:
                            result(target_entity_id)

    def _set_visibility(self, target_entity_id: int, component: ecs_event_components.ResultSetVisibility) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_geo_components.Appearance):
            appearance.visible = component.visible

    def _toggle_visibility(self, target_entity_id: int, component: ecs_event_components.ResultToggleVisibility) -> None:
        # TODO: implement — Appearance.visible is a list; define toggle semantics
        pass

    def _change_color(self, target_entity_id: int, component: ecs_event_components.ResultChangeColor) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_geo_components.Appearance):
            appearance.color = component.color

    def _change_radius(self, target_entity_id: int, component: ecs_event_components.ResultChangeRadius) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_geo_components.Appearance):
            appearance.radius = component.radius

    def _add_traits(self, target_entity_id: int, component: ecs_event_components.ResultAddTraits) -> None:
        traits = esper.try_component(target_entity_id, ecs_geo_components.Traits)
        if traits is None:
            esper.add_component(target_entity_id, ecs_geo_components.Traits(traits=list(component.traits)))
        else:
            for trait in component.traits:
                if trait not in traits.traits:
                    traits.traits.append(trait)

    def _remove_traits(self, target_entity_id: int, component: ecs_event_components.ResultRemoveTraits) -> None:
        if traits := esper.try_component(target_entity_id, ecs_geo_components.Traits):
            for trait in component.traits:
                try:
                    traits.traits.remove(trait)
                except ValueError:
                    pass

    def _toggle_traits(self, target_entity_id: int, component: ecs_event_components.ResultToggleTraits) -> None:
        traits = esper.try_component(target_entity_id, ecs_geo_components.Traits)
        if traits is None:
            esper.add_component(target_entity_id, ecs_geo_components.Traits(traits=list(component.traits)))
        else:
            for trait in component.traits:
                if trait in traits.traits:
                    traits.traits.remove(trait)
                else:
                    traits.traits.append(trait)

    def _add_stats(self, target_entity_id: int, component: ecs_event_components.ResultAddStats) -> None:
        # TODO: implement — define the item format in ResultAddStats.stats
        pass

    def _remove_stats(self, target_entity_id: int, component: ecs_event_components.ResultRemoveStats) -> None:
        # TODO: implement — define the item format in ResultRemoveStats.stats
        pass

    def _toggle_stats(self, target_entity_id: int, component: ecs_event_components.ResultToggleStats) -> None:
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

    def _increase_stats_by_values(self, target_entity_id: int, component: ecs_event_components.ResultIncreaseStatsByValues) -> None:
        if stats := esper.try_component(target_entity_id, ecs_geo_components.Stats):
            if stats.items:
                for key, delta in component.stats_to_values.items():
                    if key in stats.items:
                        stats.items[key] += delta

    def _decrease_stats_by_values(self, target_entity_id: int, component: ecs_event_components.ResultDecreaseStatsByValues) -> None:
        if stats := esper.try_component(target_entity_id, ecs_geo_components.Stats):
            if stats.items:
                for key, delta in component.stats_to_values.items():
                    if key in stats.items:
                        stats.items[key] -= delta

