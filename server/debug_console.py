"""Debug command handling for SessionState.

This module isolates the interactive debug console so SessionState can stay
focused on stream synchronization and ECS updates.
"""

import queue
import threading
from typing import Protocol

import ecs_components
import esper


class DebugState(Protocol):
    GeoObjects: dict[str, ecs_components.GeoObject]
    ClientRequests: dict[str, ecs_components.ClientRequest]
    GeoObjectEntityIds: dict[str, int]
    ClientRequestEntityIds: dict[str, int]


class SessionDebugConsole:
    def __init__(self, state: DebugState) -> None:
        self._state = state
        self._command_queue: queue.Queue[str] = queue.Queue()

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
            "help | stats | world | list [geo|req] [count] | "
            "dump <key> | dumpgeo <key> | dumpreq <key>"
        )

    def _print_debug_stats(self) -> None:
        print(
            "[DEBUG] "
            f"geoObjects={len(self._state.GeoObjects)} "
            f"geoEntityIds={len(self._state.GeoObjectEntityIds)} "
            f"clientRequests={len(self._state.ClientRequests)} "
            f"requestEntityIds={len(self._state.ClientRequestEntityIds)}"
        )

    def _print_world_stats(self) -> None:
        id_count = len(list(esper.get_component(ecs_components.ID)))
        metadata_count = len(list(esper.get_component(ecs_components.MetaData)))
        appearance_count = len(list(esper.get_component(ecs_components.Appearance)))
        geometry_count = len(list(esper.get_component(ecs_components.Geometry)))
        request_count = len(list(esper.get_component(ecs_components.ClientRequestProperties)))

        geo_entities = {entity_id for entity_id, _ in esper.get_component(ecs_components.ID)}
        request_entities = {
            entity_id for entity_id, _ in esper.get_component(ecs_components.ClientRequestProperties)
        }
        all_entities = geo_entities | request_entities

        print(
            "[DEBUG][world] "
            f"entities={len(all_entities)} "
            f"id={id_count} meta={metadata_count} appearance={appearance_count} geometry={geometry_count} "
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
        print("[DEBUG] list usage: list [geo|req] [count]")

    def _print_geo_dump(self, key: str) -> bool:
        entity_id = self._state.GeoObjectEntityIds.get(key)
        if entity_id is None:
            return False
        id_component = esper.component_for_entity(entity_id, ecs_components.ID)
        metadata = esper.component_for_entity(entity_id, ecs_components.MetaData)
        appearance = esper.component_for_entity(entity_id, ecs_components.Appearance)
        geometry = esper.component_for_entity(entity_id, ecs_components.Geometry)
        try:
            stat_a = esper.component_for_entity(entity_id, ecs_components.StatA)
        except Exception:
            stat_a = None
        print(
            "[DEBUG][geo] "
            f"key={key} entity={entity_id} "
            f"id={id_component.id} name={metadata.name!r} type={metadata.type!r} "
            f"description={metadata.description!r} color={appearance.color!r} "
            f"shape={appearance.shape!r} radius={appearance.radius} "
            f"coordinates={geometry.coordinates} "
            f"statA_name={stat_a.name!r} statA_type={stat_a.type!r} statA_value={stat_a.value} statA_max={stat_a.max_value} statA_min={stat_a.min_value}"
        )
        return True

    def _print_request_dump(self, key: str) -> bool:
        entity_id = self._state.ClientRequestEntityIds.get(key)
        if entity_id is None:
            return False
        request = esper.component_for_entity(entity_id, ecs_components.ClientRequestProperties)
        print(
            "[DEBUG][req] "
            f"key={key} entity={entity_id} requester_id={request.requester_id!r} "
            f"timestamp={request.timestamp!r}"
        )
        return True

    def _process_command(self, raw_command: str) -> None:
        parts = raw_command.split()
        if not parts:
            return

        command = parts[0].lower()

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
        if command == "dump":
            if len(parts) < 2:
                print("[DEBUG] dump usage: dump <key>")
                return
            key = parts[1]
            if self._print_geo_dump(key):
                return
            if self._print_request_dump(key):
                return
            print(f"[DEBUG] key not found in geo or req maps: {key}")
            return

        print(f"[DEBUG] Unknown command: {raw_command}")

    def drain_commands(self) -> None:
        while True:
            try:
                command = self._command_queue.get_nowait()
            except queue.Empty:
                return
            self._process_command(command)
