import esper
import ecs_comps_zone
import ecs_comps_event
from session_db_state import SessionState


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

    def _set_radius(self, target_entity_id: int, component: ecs_comps_event.ResultSetRadius) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.radius = component.radius

    def _change_radius(self, target_entity_id: int, component: ecs_comps_event.ResultChangeRadius) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.radius += component.change

    def _set_fill(self, target_entity_id: int, component: ecs_comps_event.ResultSetFill) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.fill = component.fill

    def _set_opacity(self, target_entity_id: int, component: ecs_comps_event.ResultSetOpacity) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.opacity = component.opacity

    def _change_opacity(self, target_entity_id: int, component: ecs_comps_event.ResultChangeOpacity) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.opacity += component.change

    def _set_border(self, target_entity_id: int, component: ecs_comps_event.ResultSetBorder) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.border = component.border

    def _set_dash(self, target_entity_id: int, component: ecs_comps_event.ResultSetDash) -> None:
        if appearance := esper.try_component(target_entity_id, ecs_comps_zone.Appearance):
            appearance.dash = component.dash

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


