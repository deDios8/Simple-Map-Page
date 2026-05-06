import esper
import ecs_components

class AdjustRadius(esper.Processor):
    def __init__(self, radius_increment: int) -> None:
        super().__init__()
        self.radius_increment = radius_increment
        
    def process(self) -> None:
        for entity_id, (appearance,) in self.world.get_components(ecs_components.Appearance):
            old_radius = appearance.radius
            appearance.radius += self.radius_increment
            print(f"[AdjustRadius] Entity {entity_id}: radius {old_radius} -> {appearance.radius}")

class CheckZoneEntryExit(esper.Processor):
    def __init__(self, zones: dict) -> None:
        super().__init__()
        self.zones = zones
        
    def process(self) -> None:
        for entity_id, (geometry,) in self.world.get_components(ecs_components.Geometry):
            current_zones = set()
            for zone_id, zone in self.zones.items():
                if self.is_within_zone(geometry.coordinates, zone):
                    current_zones.add(zone_id)
            
            previous_within = self.world.try_component(entity_id, ecs_components.WithinZones)
            previous_zones = set(previous_within.zone_ids) if previous_within else set()
            
            entered_zones = current_zones - previous_zones
            exited_zones = previous_zones - current_zones
            
            if entered_zones:
                self.world.add_component(entity_id, ecs_components.EnteredZones(zone_ids=list(entered_zones)))
                print(f"[CheckZoneEntryExit] Entity {entity_id} entered zones: {entered_zones}")
            if exited_zones:
                self.world.add_component(entity_id, ecs_components.ExitedZones(zone_ids=list(exited_zones)))
                print(f"[CheckZoneEntryExit] Entity {entity_id} exited zones: {exited_zones}")
            
            self.world.add_component(entity_id, ecs_components.WithinZones(zone_ids=list(current_zones)))