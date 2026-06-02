"""Debug command handling for SessionState.

This module isolates the interactive debug console so SessionState can stay
focused on stream synchronization and ECS updates.
"""

import queue
import threading
from typing import Protocol

import ecs_event_components
import ecs_geo_components
import esper
from ecs_event_components import EVENT_RESULT_COMPONENT_MAP, CRITERIA_COMPONENT_MAP, CRITERIA_TRACKING_COMPONENT_MAP


class DebugState(Protocol):
    GeoObjects: dict[str, ecs_geo_components.GeoObject]
    ClientRequests: dict[str, ecs_geo_components.ClientRequest]
    GeoObjectEntityIds: dict[str, int]
    ClientRequestEntityIds: dict[str, int]
    EventResults: dict[str, ecs_event_components.Event]
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
            "help | stats | world | list [geo|req|criteria|events] [count] | "
            "dump <key> | dumpgeo <key> | dumpreq <key> | dumpcriteria <key> | dumpevent <key> | "
            "zoneborders [key] | exit"
        )

    def _zone_borders_payload(self, entity_id: int) -> dict[str, dict[str, list[str]]]:
        payload: dict[str, dict[str, list[str]]] = {}

        within = esper.try_component(entity_id, ecs_geo_components.WithinZones)
        if within is not None:
            payload["withinZones"] = {"zone_ids": [str(zone_id) for zone_id in within.zone_ids]}

        entered = esper.try_component(entity_id, ecs_geo_components.EnteredZones)
        if entered is not None:
            payload["enteredZones"] = {"zone_ids": [str(zone_id) for zone_id in entered.zone_ids]}

        exited = esper.try_component(entity_id, ecs_geo_components.ExitedZones)
        if exited is not None:
            payload["exitedZones"] = {"zone_ids": [str(zone_id) for zone_id in exited.zone_ids]}

        return payload

    def _print_zone_borders_for_key(self, key: str) -> bool:
        if key in self._state.GeoObjectEntityIds:
            entity_id = self._state.GeoObjectEntityIds[key]
            payload = self._zone_borders_payload(entity_id)
            print(f"[DEBUG][zoneBorders][geo] key={key} entity={entity_id} payload={payload}")
            return True

        if key in self._state.ClientRequestEntityIds:
            entity_id = self._state.ClientRequestEntityIds[key]
            payload = self._zone_borders_payload(entity_id)
            print(f"[DEBUG][zoneBorders][req] key={key} entity={entity_id} payload={payload}")
            return True

        return False

    def _print_zone_borders_all(self) -> None:
        for key in sorted(self._state.GeoObjectEntityIds.keys()):
            entity_id = self._state.GeoObjectEntityIds[key]
            payload = self._zone_borders_payload(entity_id)
            print(f"[DEBUG][zoneBorders][geo] key={key} entity={entity_id} payload={payload}")

        for key in sorted(self._state.ClientRequestEntityIds.keys()):
            entity_id = self._state.ClientRequestEntityIds[key]
            payload = self._zone_borders_payload(entity_id)
            print(f"[DEBUG][zoneBorders][req] key={key} entity={entity_id} payload={payload}")

    def _print_debug_stats(self) -> None:
        print(
            "[DEBUG] "
            f"geoObjects={len(self._state.GeoObjects)} "
            f"geoEntityIds={len(self._state.GeoObjectEntityIds)} "
            f"clientRequests={len(self._state.ClientRequests)} "
            f"requestEntityIds={len(self._state.ClientRequestEntityIds)} "
            f"eventResults={len(self._state.EventResults)} "
            f"eventResultEntityIds={len(self._state.EventResultEntityIds)}"
        )

    def _print_world_stats(self) -> None:
        id_count = len(list(esper.get_component(ecs_geo_components.ID)))
        display_name_count = len(list(esper.get_component(ecs_geo_components.DisplayName)))
        appearance_count = len(list(esper.get_component(ecs_geo_components.Appearance)))
        geometry_count = len(list(esper.get_component(ecs_geo_components.Geometry)))
        request_count = len(list(esper.get_component(ecs_geo_components.ClientRequestPayload)))

        geo_entities = {entity_id for entity_id, _ in esper.get_component(ecs_geo_components.ID)}
        request_entities = {
            entity_id for entity_id, _ in esper.get_component(ecs_geo_components.ClientRequestPayload)
        }
        all_entities = geo_entities | request_entities

        print(
            "[DEBUG][world] "
            f"entities={len(all_entities)} "
            f"id={id_count} display_name={display_name_count} appearance={appearance_count} geometry={geometry_count} "
            f"requestParameters={request_count}"
        )

    def _print_debug_list(self, subject: str, count: int) -> None:
        if subject == "geo":
            keys = sorted(self._state.GeoObjectEntityIds.keys())
            print(f"[DEBUG] geo keys ({len(keys)} total): {keys[:count]}")
            return
        if subject == "req":
            keys = sorted(self._state.ClientRequestEntityIds.keys())
            print(f"[DEBUG] req keys ({len(keys)} total): {keys[:count]}")
            return
        if subject == "events":
            keys = sorted(self._state.EventResultEntityIds.keys())
            print(f"[DEBUG] events keys ({len(keys)} total): {keys[:count]}")
            return
        print("[DEBUG] list usage: list [geo|req|criteria|events] [count]")

    def _print_geo_dump(self, key: str) -> bool:
        entity_id = self._state.GeoObjectEntityIds.get(key)
        if entity_id is None:
            return False
        id_component = esper.component_for_entity(entity_id, ecs_geo_components.ID)
        display_name_comp = esper.component_for_entity(entity_id, ecs_geo_components.DisplayName)
        appearance = esper.component_for_entity(entity_id, ecs_geo_components.Appearance)
        geometry = esper.component_for_entity(entity_id, ecs_geo_components.Geometry)
        traits = esper.try_component(entity_id, ecs_geo_components.Traits)
        stats = esper.try_component(entity_id, ecs_geo_components.Stats)
        print(
            "[DEBUG][geo] "
            f"key={key} entity={entity_id} "
            f"id={id_component.id} display_name={display_name_comp.display_name!r} "
            f"color={appearance.color!r} "
            f"shape={appearance.shape!r} radius={appearance.radius} "
            f"coordinates={geometry.coordinates} "
            f"traits={traits.traits if traits is not None else []} "
            f"stats={stats.items if stats is not None else {}}"
        )
        return True

    def _print_request_dump(self, key: str) -> bool:
        entity_id = self._state.ClientRequestEntityIds.get(key)
        if entity_id is None:
            return False
        request = esper.component_for_entity(entity_id, ecs_geo_components.ClientRequestPayload)
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
        id_component = esper.component_for_entity(entity_id, ecs_geo_components.ID)
        display_name_comp = esper.component_for_entity(entity_id, ecs_geo_components.DisplayName)
        trigger = esper.try_component(entity_id, ecs_event_components.EventTriggerNames)
        target = esper.try_component(entity_id, ecs_event_components.EventTargetNames)
        active_results: dict[str, object] = {}
        for comp_name, comp_type in EVENT_RESULT_COMPONENT_MAP.items():
            comp = esper.try_component(entity_id, comp_type)
            if comp is not None:
                active_results[comp_name] = comp
        print(
            "[DEBUG][event] "
            f"key={key} entity={entity_id} "
            f"id={id_component.id} display_name={display_name_comp.display_name!r} "
            f"triggerNames={trigger.names if trigger is not None else []} "
            f"targetNames={target.names if target is not None else []} "
            f"results={active_results}"
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
            subject = "geo"
            count = 10
            if len(parts) >= 2:
                subject = parts[1].lower()
            if len(parts) >= 3:
                try:
                    count = max(1, int(parts[2]))
                except ValueError:
                    print("[DEBUG] count must be an integer")
                    return
            self._print_debug_list(subject, count)
            return
        if command == "dumpgeo":
            if len(parts) < 2:
                print("[DEBUG] dumpgeo usage: dumpgeo <key>")
                return
            if not self._print_geo_dump(parts[1]):
                print(f"[DEBUG] geo key not found: {parts[1]}")
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
            if self._print_geo_dump(key):
                return
            if self._print_request_dump(key):
                return
            if self._print_event_dump(key):
                return
            print(f"[DEBUG] key not found in geo, req, or event maps: {key}")
            return
        if command == "zoneborders":
            if len(parts) >= 2:
                if not self._print_zone_borders_for_key(parts[1]):
                    print(f"[DEBUG] key not found in geo or req maps: {parts[1]}")
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
