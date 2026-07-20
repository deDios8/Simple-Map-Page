"""
Debug command handling for SessionState.

This module isolates the interactive debug console so SessionState can stay
focused on stream synchronization and ECS updates.
"""

import esper
import queue
import threading
from typing import Protocol
import ecs_comps_zone
import ecs_comps_event
import ecs_comps_client_request
from ecs_comps_event import EVENT_RESULT_COMPONENT_MAP


class DebugState(Protocol):
    Zones: dict[str, ecs_comps_zone.Zone]
    ClientRequests: dict[str, ecs_comps_client_request.ClientRequest]
    ZoneEntityIds: dict[str, int]
    ClientRequestEntityIds: dict[str, int]
    Events: dict[str, ecs_comps_event.Event]
    EventResultEntityIds: dict[str, int]


class SessionDebugConsole:
    def __init__(self, state: DebugState) -> None:
        self._state = state
        self._command_queue: queue.Queue[str] = queue.Queue()
        self._exit_requested: bool = False

    def start(self) -> None:
        def _read_commands() -> None:
            while True:
                try:
                    raw = input()
                except EOFError:
                    return
                except KeyboardInterrupt:
                    return

                command = raw.strip()
                if not command:
                    continue
                self._command_queue.put(command)

        thread = threading.Thread(target=_read_commands, daemon=True)
        thread.start()

    def print_help(self) -> None:
        print(
            "[DEBUG] Commands: "
            "help | stats | world | list [zones|req|criteria|events] [count] | "
            "dump <key> | dumpzones <key> | dumpreq <key> | dumpcriteria <key> | dumpevent <key> | "
            "zoneborders [key] | exit"
        )

    def _zone_borders_payload(self, entity_id: int) -> dict[str, dict[str, list[str]]]:
        payload: dict[str, dict[str, list[str]]] = {}

        within = esper.try_component(entity_id, ecs_comps_zone.WithinZones)
        if within is not None:
            payload["withinZones"] = {"zone_names": self._get_display_names_for_ids(within.zone_ids)}

        entered = esper.try_component(entity_id, ecs_comps_zone.EnteredZones)
        if entered is not None:
            payload["enteredZones"] = {"zone_names": self._get_display_names_for_ids(entered.zone_ids)}

        exited = esper.try_component(entity_id, ecs_comps_zone.ExitedZones)
        if exited is not None:
            payload["exitedZones"] = {"zone_names": self._get_display_names_for_ids(exited.zone_ids)}

        return payload

    def _get_display_names_for_ids(self, zone_ids: list[str]) -> list[str]:
        """Convert zone IDs to display names for debug output."""
        names = []
        for zone_id in zone_ids:
            zone_eid = self._state.ZoneEntityIds.get(zone_id)
            if zone_eid is not None:
                display_name_comp = esper.try_component(zone_eid, ecs_comps_zone.DisplayName)
                if display_name_comp:
                    names.append(display_name_comp.display_name)
                else:
                    names.append(zone_id)
            else:
                names.append(zone_id)
        return names

    def _print_zone_borders_for_key(self, key: str) -> bool:
        if key in self._state.ZoneEntityIds:
            entity_id = self._state.ZoneEntityIds[key]
            display_name_comp = esper.try_component(entity_id, ecs_comps_zone.DisplayName)
            display_name = display_name_comp.display_name if display_name_comp else key
            payload = self._zone_borders_payload(entity_id)
            print(f"[DEBUG][zoneBorders][zones] key={key} name='{display_name}' entity={entity_id} payload={payload}")
            return True

        if key in self._state.ClientRequestEntityIds:
            entity_id = self._state.ClientRequestEntityIds[key]
            display_name_comp = esper.try_component(entity_id, ecs_comps_zone.DisplayName)
            display_name = display_name_comp.display_name if display_name_comp else key
            payload = self._zone_borders_payload(entity_id)
            print(f"[DEBUG][zoneBorders][req] key={key} name='{display_name}' entity={entity_id} payload={payload}")
            return True

        return False

    def _print_zone_borders_all(self) -> None:
        for key in sorted(self._state.ZoneEntityIds.keys()):
            entity_id = self._state.ZoneEntityIds[key]
            display_name_comp = esper.try_component(entity_id, ecs_comps_zone.DisplayName)
            display_name = display_name_comp.display_name if display_name_comp else key
            payload = self._zone_borders_payload(entity_id)
            print(f"[DEBUG][zoneBorders][zones] key={key} name='{display_name}' entity={entity_id} payload={payload}")

        for key in sorted(self._state.ClientRequestEntityIds.keys()):
            entity_id = self._state.ClientRequestEntityIds[key]
            display_name_comp = esper.try_component(entity_id, ecs_comps_zone.DisplayName)
            display_name = display_name_comp.display_name if display_name_comp else key
            payload = self._zone_borders_payload(entity_id)
            print(f"[DEBUG][zoneBorders][req] key={key} name='{display_name}' entity={entity_id} payload={payload}")

    def _print_debug_stats(self) -> None:
        print(
            "[DEBUG] "
            f"Zones={len(self._state.Zones)} "
            f"zoneEntityIds={len(self._state.ZoneEntityIds)} "
            f"clientRequests={len(self._state.ClientRequests)} "
            f"requestEntityIds={len(self._state.ClientRequestEntityIds)} "
            f"events={len(self._state.Events)} "
            f"eventResultEntityIds={len(self._state.EventResultEntityIds)}"
        )

    def _print_world_stats(self) -> None:
        id_count = len(list(esper.get_component(ecs_comps_zone.ID)))
        display_name_count = len(list(esper.get_component(ecs_comps_zone.DisplayName)))
        appearance_count = len(list(esper.get_component(ecs_comps_zone.Appearance)))
        geometry_count = len(list(esper.get_component(ecs_comps_zone.zonemetry)))
        request_count = len(list(esper.get_component(ecs_comps_client_request.ClientRequestPayload)))

        zone_entities = {entity_id for entity_id, _ in esper.get_component(ecs_comps_zone.ID)}
        request_entities = {
            entity_id for entity_id, _ in esper.get_component(ecs_comps_client_request.ClientRequestPayload)
        }
        all_entities = zone_entities | request_entities

        print(
            "[DEBUG][world] "
            f"entities={len(all_entities)} "
            f"id={id_count} display_name={display_name_count} appearance={appearance_count} geometry={geometry_count} "
            f"requestParameters={request_count}"
        )

    def _print_debug_list(self, subject: str, count: int) -> None:
        if subject == "zone":
            keys = sorted(self._state.ZoneEntityIds.keys())
            print(f"[DEBUG] zone keys ({len(keys)} total): {keys[:count]}")
            return
        if subject == "req":
            keys = sorted(self._state.ClientRequestEntityIds.keys())
            print(f"[DEBUG] req keys ({len(keys)} total): {keys[:count]}")
            return
        if subject == "events":
            keys = sorted(self._state.EventResultEntityIds.keys())
            print(f"[DEBUG] events keys ({len(keys)} total): {keys[:count]}")
            return
        print("[DEBUG] list usage: list [zone|req|criteria|events] [count]")

    def _print_zone_dump(self, key: str) -> bool:
        entity_id = self._state.ZoneEntityIds.get(key)
        if entity_id is None:
            return False
        id_component = esper.component_for_entity(entity_id, ecs_comps_zone.ID)
        display_name_comp = esper.component_for_entity(entity_id, ecs_comps_zone.DisplayName)
        appearance = esper.component_for_entity(entity_id, ecs_comps_zone.Appearance)
        geometry = esper.component_for_entity(entity_id, ecs_comps_zone.Geometry)
        traits = esper.try_component(entity_id, ecs_comps_zone.Traits)
        stats = esper.try_component(entity_id, ecs_comps_zone.Stats)
        zone_entry_log = esper.try_component(entity_id, ecs_comps_zone.ZoneEntryLog)
        zone_exit_log = esper.try_component(entity_id, ecs_comps_zone.ZoneExitLog)
        print(
            "[DEBUG][zone] "
            f"key={key} entity={entity_id} "
            f"id={id_component.id} display_name={display_name_comp.display_name!r} "
            f"color={appearance.color!r} "
            f"shape={appearance.shape!r} radius={appearance.radius} "
            f"coordinates={geometry.coordinates} "
            f"traits={traits.traits if traits is not None else []} "
            f"stats={stats.items if stats is not None else {}} "
            f"entry_log={zone_entry_log.zone_ids if zone_entry_log is not None else []} "
            f"exit_log={zone_exit_log.zone_ids if zone_exit_log is not None else []}"
        )
        return True

    def _print_request_dump(self, key: str) -> bool:
        entity_id = self._state.ClientRequestEntityIds.get(key)
        if entity_id is None:
            return False
        request = esper.component_for_entity(entity_id, ecs_comps_client_request.ClientRequestPayload)
        print(
            "[DEBUG][req] "
            f"key={key} entity={entity_id} requester_id={request.requester_id!r} "
            f"timestamp={request.timestamp!r}"
        )
        return True

    def _print_event_dump(self, key: str) -> bool:
        entity_id = self._state.EventResultEntityIds.get(key)
        if entity_id is None:
            return False
        id_component = esper.component_for_entity(entity_id, ecs_comps_zone.ID)
        display_name_comp = esper.component_for_entity(entity_id, ecs_comps_zone.DisplayName)
        # Get tracking components
        trigger_all = esper.try_component(entity_id, ecs_comps_event.ObjectsThatMetAllTriggerCriteria)
        target_all = esper.try_component(entity_id, ecs_comps_event.ObjectsThatMetAllTargetCriteria)
        
        active_events: dict[str, object] = {}
        for comp_name, comp_type in EVENT_RESULT_COMPONENT_MAP.items():
            comp = esper.try_component(entity_id, comp_type)
            if comp is not None:
                active_events[comp_name] = comp
        print(
            "[DEBUG][event] "
            f"key={key} entity={entity_id} "
            f"id={id_component.id} display_name={display_name_comp.display_name!r} "
            f"triggerObjectsAll={trigger_all.zone_ids if trigger_all is not None else []} "
            f"targetObjectsAll={target_all.zone_ids if target_all is not None else []} "
            f"events={active_events}"
        )
        return True

    def _process_command(self, raw_command: str) -> None:
        parts = raw_command.split()
        if not parts:
            return

        command = parts[0].lower()

        if command == "exit":
            self._exit_requested = True
            return
        if command == "help":
            self.print_help()
            return
        if command == "stats":
            self._print_debug_stats()
            return
        if command == "world":
            self._print_world_stats()
            return
        if command == "list":
            count = 10
            if len(parts) >= 2:
                # Check if first arg is a count (no subject) or a subject name
                if parts[1].lower() in ("zone", "req", "criteria", "events"):
                    subject = parts[1].lower()
                    if len(parts) >= 3:
                        try:
                            count = max(1, int(parts[2]))
                        except ValueError:
                            print("[DEBUG] count must be an integer")
                            return
                    self._print_debug_list(subject, count)
                else:
                    try:
                        count = max(1, int(parts[1]))
                    except ValueError:
                        print("[DEBUG] list usage: list [zone|req|criteria|events] [count]")
                        return
                    for subject in ("zone", "req", "criteria", "events"):
                        self._print_debug_list(subject, count)
            else:
                for subject in ("zone", "req", "criteria", "events"):
                    self._print_debug_list(subject, count)
            return
        if command == "dumpzone":
            if len(parts) < 2:
                print("[DEBUG] dumpzone usage: dumpzone <key>")
                return
            if not self._print_zone_dump(parts[1]):
                print(f"[DEBUG] zone key not found: {parts[1]}")
            return
        if command == "dumpreq":
            if len(parts) < 2:
                print("[DEBUG] dumpreq usage: dumpreq <key>")
                return
            if not self._print_request_dump(parts[1]):
                print(f"[DEBUG] req key not found: {parts[1]}")
            return
        if command == "dumpevent" or command == "de":
            if len(parts) < 2:
                print("[DEBUG] dumpevent usage: dumpevent <key>")
                return
            if not self._print_event_dump(parts[1]):
                print(f"[DEBUG] event key not found: {parts[1]}")
            return
        if command == "dump":
            if len(parts) < 2:
                print("[DEBUG] dump usage: dump <key>")
                return
            key = parts[1]
            if self._print_zone_dump(key):
                return
            if self._print_request_dump(key):
                return
            if self._print_event_dump(key):
                return
            print(f"[DEBUG] key not found in zone, req, or event maps: {key}")
            return
        if command == "zoneborders":
            if len(parts) >= 2:
                if not self._print_zone_borders_for_key(parts[1]):
                    print(f"[DEBUG] key not found in zone or req maps: {parts[1]}")
                return
            self._print_zone_borders_all()
            return

        print(f"[DEBUG] Unknown command: {raw_command}")

    def drain_commands(self) -> bool:
        while True:
            try:
                command = self._command_queue.get_nowait()
            except queue.Empty:
                return self._exit_requested
            self._process_command(command)
            if self._exit_requested:
                return True
