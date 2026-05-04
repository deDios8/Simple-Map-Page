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