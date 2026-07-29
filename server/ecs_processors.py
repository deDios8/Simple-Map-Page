import copy
import esper
import math
import ecs_comps_zone
import ecs_comps_event
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



class CriteriaProcessor(esper.Processor):
    def __init__(self, session_state: SessionState) -> None:
        super().__init__()
        self.session_state = session_state
        self._current_event_entity_id: int | None = None
        self._trigger_dispatch: dict = {
            comp_type: getattr(self, ecs_comps_event.TRIGGER_COMPONENT_HANDLER_NAMES[name])
            for name, comp_type in ecs_comps_event.TRIGGER_COMPONENT_MAP.items()
        }
        self._target_dispatch: dict = {
            comp_type: getattr(self, ecs_comps_event.TARGET_COMPONENT_HANDLER_NAMES[name])
            for name, comp_type in ecs_comps_event.TARGET_COMPONENT_MAP.items()
        }

    def process(self) -> None:
        zone_entity_ids = list(self.session_state.ZoneEntityIds.values())
        event_entity_ids = list(self.session_state.EventResultEntityIds.values())

        for event_entity_id in event_entity_ids:

            # --- Trigger criteria ---
            trigger_checks = []
            for comp_type, handler in self._trigger_dispatch.items():
                if comp := esper.try_component(event_entity_id, comp_type):
                    trigger_checks.append(lambda zone_eid, c=comp, h=handler: h(zone_eid, c))

            trigger_passed_any: set[int] = set()
            trigger_failed_any: set[int] = set()
            for zone_eid in zone_entity_ids:
                for check in trigger_checks:
                    if check(zone_eid):
                        trigger_passed_any.add(zone_eid)
                    else:
                        trigger_failed_any.add(zone_eid)

            all_trigger = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAllTriggerCriteria)
            if all_trigger:
                all_trigger.zone_ids = list(trigger_passed_any - trigger_failed_any)
            any_trigger = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAnyTriggerCriteria)
            if any_trigger:
                any_trigger.zone_ids = list(trigger_passed_any)

            # Track current event for target criteria evaluation
            self._current_event_entity_id = event_entity_id

            # --- Target criteria ---
            target_checks = []
            for comp_type, handler in self._target_dispatch.items():
                if comp := esper.try_component(event_entity_id, comp_type):
                    target_checks.append(lambda zone_eid, c=comp, h=handler: h(zone_eid, c))

            target_passed_any: set[int] = set()
            target_failed_any: set[int] = set()
            for zone_eid in zone_entity_ids:
                for check in target_checks:
                    if check(zone_eid):
                        target_passed_any.add(zone_eid)
                    else:
                        target_failed_any.add(zone_eid)

            all_target = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAllTargetCriteria)
            if all_target:
                all_target.zone_ids = list(target_passed_any - target_failed_any)
            any_target = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAnyTargetCriteria)
            if any_target:
                any_target.zone_ids = list(target_passed_any)

    def _get_entity_tags(self, eid: int) -> set[str]:
        tags: set[str] = set()
        if dn := esper.try_component(eid, ecs_comps_zone.DisplayName):
            tags.add(dn.display_name)
        if traits := esper.try_component(eid, ecs_comps_zone.Traits):
            tags.update(traits.traits)
        if stats := esper.try_component(eid, ecs_comps_zone.Stats):
            if stats.items:
                tags.update(stats.items.keys())
        return tags


    def _check_was_trigger(self, zone_eid: int, component) -> bool:
        # Check if this zone was one that met all trigger criteria
        if self._current_event_entity_id is None:
            return False
        trigger_comp = esper.try_component(self._current_event_entity_id, ecs_comps_event.ObjectsThatMetAllTriggerCriteria)
        if not trigger_comp:
            return False
        return zone_eid in trigger_comp.zone_ids
    

    def _check_has_tags(self, zone_eid: int, component) -> bool:
        return any(tag in self._get_entity_tags(zone_eid) for tag in component.tags)

    def _check_lacks_tags(self, zone_eid: int, component) -> bool:
        return not self._check_has_tags(zone_eid, component)


    def _check_is_within(self, zone_eid: int, component) -> bool:
        within = esper.try_component(zone_eid, ecs_comps_zone.WithinZones)
        if not within:
            return False
        tag_set = set(component.tags)
        for zone_id in within.zone_ids:
            zone_eid = self.session_state.ZoneEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return True
        return False

    def _check_is_not_within(self, zone_eid: int, component) -> bool:
        return not self._check_is_within(zone_eid, component)


    def _check_just_in_zone(self, zone_eid: int, component, temp_component_type) -> bool:
        """Helper to check if entity is currently entering/exiting a zone matching component.tags."""
        temp_component = esper.try_component(zone_eid, temp_component_type)
        if not temp_component:
            return False
        tag_set = set(component.tags)
        for zone_id in temp_component.zone_ids:
            zone_eid = self.session_state.ZoneEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return True
        return False

    def _check_just_entered(self, zone_eid: int, component) -> bool:
        return self._check_just_in_zone(zone_eid, component, ecs_comps_zone.EnteredZones)

    def _check_just_exited(self, zone_eid: int, component) -> bool:
        return self._check_just_in_zone(zone_eid, component, ecs_comps_zone.ExitedZones)


    def _check_first_in_zone(self, zone_eid: int, component, temp_component_type, log_component_type) -> bool:
        """Helper to check if entity is currently entering/exiting a zone for the first time.
        Must run BEFORE RemoveZoneEntryExit appends to the log.
        """
        temp_component = esper.try_component(zone_eid, temp_component_type)
        if not temp_component:
            return False
        
        tag_set = set(component.tags)
        log = esper.try_component(zone_eid, log_component_type)
        existing_zones = set(log.zone_ids) if log else set()
        
        # Check if any currently changed zone matches tags and is NOT in the historical log
        for zone_id in temp_component.zone_ids:
            if zone_id in existing_zones:
                continue  # Already in log (not first time)
            zone_eid = self.session_state.ZoneEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return True
        return False

    def _check_first_entered(self, zone_eid: int, component) -> bool:
        return self._check_first_in_zone(zone_eid, component, ecs_comps_zone.EnteredZones, ecs_comps_zone.ZoneEntryLog)

    def _check_first_exited(self, zone_eid: int, component) -> bool:
        return self._check_first_in_zone(zone_eid, component, ecs_comps_zone.ExitedZones, ecs_comps_zone.ZoneExitLog)


    def _check_ever_in_log(self, zone_eid: int, component, log_component_type) -> bool:
        """Helper to check if any zone in historical log matches component.tags."""
        log = esper.try_component(zone_eid, log_component_type)
        if not log or not log.zone_ids:
            return False
        
        tag_set = set(component.tags)
        for zone_id in log.zone_ids:
            zone_eid = self.session_state.ZoneEntityIds.get(zone_id)
            if zone_eid is None:
                continue
            if self._get_entity_tags(zone_eid) & tag_set:
                return True
        return False

    def _check_ever_entered(self, zone_eid: int, component) -> bool:
        return self._check_ever_in_log(zone_eid, component, ecs_comps_zone.ZoneEntryLog)

    def _check_ever_exited(self, zone_eid: int, component) -> bool:
        return self._check_ever_in_log(zone_eid, component, ecs_comps_zone.ZoneExitLog)


    def _check_recently_in_log(self, zone_eid: int, component, log_component_type) -> bool:
        """Helper to check if the last zone in a log matches component.tags."""
        log = esper.try_component(zone_eid, log_component_type)
        if not log or not log.zone_ids:
            return False
        
        # Validate component has tags attribute
        if not hasattr(component, 'tags') or not component.tags:
            return False
        
        tag_set = set(component.tags)
        # Get the most recent zone (last item in the log)
        last_zone_id = log.zone_ids[-1]
        
        zone_eid = self.session_state.ZoneEntityIds.get(last_zone_id)
        if zone_eid is None:
            return False  # Zone was deleted or doesn't exist
        
        return bool(self._get_entity_tags(zone_eid) & tag_set)

    def _check_recently_entered(self, zone_eid: int, component) -> bool:
        return self._check_recently_in_log(zone_eid, component, ecs_comps_zone.ZoneEntryLog)

    def _check_recently_exited(self, zone_eid: int, component) -> bool:
        return self._check_recently_in_log(zone_eid, component, ecs_comps_zone.ZoneExitLog)


    def _check_is_visible(self, zone_eid: int, component) -> bool:
        appearance = esper.try_component(zone_eid, ecs_comps_zone.Appearance)
        if not appearance:
            return False
        return any(tag in appearance.visible_to for tag in component.tags)

    def _check_is_not_visible(self, zone_eid: int, component) -> bool:
        return not self._check_is_visible(zone_eid, component)



class EventProcessor(esper.Processor):
    def __init__(self, session_state: SessionState) -> None:
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
            if not trigger_comp or not trigger_comp.zone_ids:
                continue

            target_comp = esper.try_component(event_entity_id, ecs_comps_event.ObjectsThatMetAllTargetCriteria)
            if not target_comp or not target_comp.zone_ids:
                continue

            # Apply this event's result components to each qualifying target zone
            for target_entity_id in target_comp.zone_ids:

                results_to_apply = []
                for comp_type, handler in self._result_dispatch.items():
                    if comp := esper.try_component(event_entity_id, comp_type):
                        results_to_apply.append(lambda eid, c=comp, h=handler: h(eid, c))

                for result in results_to_apply:
                    result(target_entity_id)

                if results_to_apply:
                    esper.add_component(target_entity_id, ecs_comps_zone.ZoneObjectDirty())

    def _grant_visibility(self, target_entity_id: int, component: ecs_comps_event.ResultGrantVisibility) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            for tag in component.tags:
                if tag not in appearance.visible_to:
                    appearance.visible_to.append(tag)

    def _revoke_visibility(self, target_entity_id: int, component: ecs_comps_event.ResultRevokeVisibility) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            for tag in component.tags:
                if tag in appearance.visible_to:
                    appearance.visible_to.remove(tag)

    def _toggle_visibility(self, target_entity_id: int, component: ecs_comps_event.ResultToggleVisibility) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            for tag in component.tags:
                if tag in appearance.visible_to:
                    appearance.visible_to.remove(tag)
                else:
                    appearance.visible_to.append(tag)

    def _set_fill(self, target_entity_id: int, component: ecs_comps_event.ResultSetFill) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.fill = component.fill

    def _set_border(self, target_entity_id: int, component: ecs_comps_event.ResultSetBorder) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.border = component.border

    def _set_radius(self, target_entity_id: int, component: ecs_comps_event.ResultSetRadius) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.radius = component.radius

    def _change_radius(self, target_entity_id: int, component: ecs_comps_event.ResultChangeRadius) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.radius += component.change

    def _set_opacity(self, target_entity_id: int, component: ecs_comps_event.ResultSetOpacity) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.opacity = component.opacity

    def _change_opacity(self, target_entity_id: int, component: ecs_comps_event.ResultChangeOpacity) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.opacity += component.change

    def _grant_traits(self, target_entity_id: int, component: ecs_comps_event.ResultGrantTraits) -> None:
        traits = esper.try_component(target_entity_id, ecs_comps_zone.Traits)
        if traits is None:
            esper.add_component(target_entity_id, ecs_comps_zone.Traits(traits=list(component.tags)))
        else:
            for trait in component.tags: #preserves order and avoids duplicates
                if trait not in traits.traits:
                    traits.traits.append(trait)

    def _revoke_traits(self, target_entity_id: int, component: ecs_comps_event.ResultRevokeTraits) -> None:
        if traits := esper.try_component(target_entity_id, ecs_comps_zone.Traits):
            for trait in component.tags:
                if trait in traits.traits:
                    traits.traits.remove(trait)

    def _toggle_traits(self, target_entity_id: int, component: ecs_comps_event.ResultToggleTraits) -> None:
        traits = esper.try_component(target_entity_id, ecs_comps_zone.Traits)
        if traits is None:
            esper.add_component(target_entity_id, ecs_comps_zone.Traits(traits=list(component.tags)))
        else:
            for trait in component.tags:
                if trait in traits.traits:
                    traits.traits.remove(trait)
                else:
                    traits.traits.append(trait)

    def _revoke_stats(self, target_entity_id: int, component) -> None:
        if stats := esper.try_component(target_entity_id, ecs_comps_zone.Stats):
            if stats.items:
                for stat_to_remove in component.tags:
                    if stat_to_remove in stats.items:
                        del stats.items[stat_to_remove]

    def _toggle_stats_to_values(self, target_entity_id: int, component: ecs_comps_event.ResultToggleStatsWithValue) -> None:
        '''Toggle stats on/off with a specified value. If stat doesn't exist, add it with the value. If stat exists, remove it regardless of value.'''
        stats = esper.try_component(target_entity_id, ecs_comps_zone.Stats)
        if stats and stats.items and any(key in stats.items for key in component.stats_to_values.keys()):
            self._revoke_stats(target_entity_id, component)
        else:
            self._set_stats_to_values(target_entity_id, component)

    def _set_stats_to_values(self, target_entity_id: int, component) -> None:
        stats = esper.try_component(target_entity_id, ecs_comps_zone.Stats)
        if not stats:
            stats = ecs_comps_zone.Stats(items={})
            esper.add_component(target_entity_id, stats)
        if stats.items is None:
            stats.items = {}
        for key, value in component.stats_to_values.items():
            stat_item = stats.items.get(key, {})
            stat_item["name"] = key
            stat_item["value"] = value
            min_value = float(stat_item.get("min_value", 0))
            max_value = float(stat_item.get("max_value", 100))
            new_value = float(value)
            stat_item["value"] = max(min_value, min(max_value, new_value))
            stats.items[key] = stat_item

    def _change_stats_by_values(self, target_entity_id: int, component: ecs_comps_event.ResultChangeStatsByValues) -> None:
        if stats := esper.try_component(target_entity_id, ecs_comps_zone.Stats):
            if stats.items:
                for key, delta in component.stats_to_values.items():
                    if key in stats.items:
                        stat_item = stats.items[key]
                        current_value = float(stat_item.get("value", 0))
                        min_value = float(stat_item.get("min_value", 0))
                        max_value = float(stat_item.get("max_value", 100))
                        delta_value = float(delta)
                        stat_item["value"] = max(min_value, min(max_value, current_value + delta_value))

    def _popup_message(self, target_entity_id: int, component: ecs_comps_event.ResultPopupMessage) -> None:
        messages = esper.try_component(target_entity_id, ecs_comps_zone.Messages)
        if messages is None:
            esper.add_component(target_entity_id, ecs_comps_zone.Messages(messages=[component.text]))
        else:
            messages.messages.append(component.text)



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


