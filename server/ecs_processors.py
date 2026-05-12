import esper
import ecs_components
import math
from pyproj import CRS, Transformer
from shapely.geometry import Point


class ApplyClientRequests(esper.Processor):
    def __init__(self, session_state) -> None:
        super().__init__()
        self.session_state = session_state

    def process(self) -> None:
        for entity_id, _marker in list(esper.get_component(ecs_components.NewLocation)):
            self.session_state.apply_new_location_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_components.AddObject)):
            self.session_state.apply_add_object_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_components.EditedObject)):
            self.session_state.apply_edited_object_request(entity_id)

        for entity_id, _marker in list(esper.get_component(ecs_components.DeletedObject)):
            self.session_state.apply_deleted_object_request(entity_id)

class AdjustRadius(esper.Processor):
    def __init__(self, radius_increment: int) -> None:
        super().__init__()
        self.radius_increment = radius_increment
        
    def process(self) -> None:
        for entity_id, (appearance,) in esper.get_components(ecs_components.Appearance):
            old_radius = appearance.radius
            appearance.radius += self.radius_increment
            print(f"[AdjustRadius] Entity {entity_id}: radius {old_radius} -> {appearance.radius}")

class CheckZoneEntryExit(esper.Processor):
    def __init__(self) -> None:
        super().__init__()
        
    def process(self) -> None:
        for entity_id, (geometry, id_component) in esper.get_components(ecs_components.Geometry, ecs_components.ID):
            current_zones = set()
            for zone_entity_id, (zone_geometry, zone_appearance, zone_id_component) in esper.get_components(
                    ecs_components.Geometry,
                    ecs_components.Appearance,
                    ecs_components.ID,
                ):
                # print(f"[CheckZoneEntryExit] Checking entity {id_component.id} against zone {zone_id_component.id}")
                if zone_entity_id == entity_id:
                    continue
                if id_component.id == zone_id_component.id:
                    continue

                zone_payload = {
                    "geometry": {"coordinates": zone_geometry.coordinates},
                    "properties": {
                        "appearance": {
                            "radius": zone_appearance.radius if zone_appearance is not None else 0,
                        }
                    },
                }

                if self.is_within_zone_intersect(geometry.coordinates, zone_payload):
                    current_zones.add(str(zone_id_component.id))
            
            previous_within = esper.try_component(entity_id, ecs_components.WithinZones)
            previous_zones = set(previous_within.zone_ids) if previous_within else set()
            
            entered_zones = current_zones - previous_zones
            exited_zones = previous_zones - current_zones
            
            if entered_zones:
                esper.add_component(entity_id, ecs_components.EnteredZones(zone_ids=list(entered_zones)))
                print(f"[CheckZoneEntryExit] Entity {id_component.id} entered zones: {entered_zones}")
            if exited_zones:
                esper.add_component(entity_id, ecs_components.ExitedZones(zone_ids=list(exited_zones)))
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

    def is_within_zone_intersect(self, object_coordinates: list, zone: dict) -> bool:
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
            object_radius_m = max(0.0, float(object_radius_value) * 0.3)
            zone_radius_m = max(0.0, float(zone_radius_value) * 0.3)
        except (TypeError, ValueError):
            return False

        # Local azimuthal-equidistant CRS keeps distances in meters near the zone center.
        local_crs = CRS.from_proj4(
            f"+proj=aeqd +lat_0={zone_lat} +lon_0={zone_lon} +datum=WGS84 +units=m +no_defs"
        )
        transformer = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True)

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
        for entity_id, entered in list(esper.get_component(ecs_components.EnteredZones)):
            # WithinZones: add entered zones
            within = esper.try_component(entity_id, ecs_components.WithinZones)
            before_zones = set(within.zone_ids) if within else set()
            within_zones = set(before_zones)
            within_zones.update(entered.zone_ids)

            esper.add_component(entity_id, ecs_components.WithinZones(zone_ids=list(within_zones)))
            if within_zones != before_zones:
                esper.add_component(entity_id, ecs_components.ZoneBordersDirty())

            # NotWithinZones: remove entered zones
            not_within = esper.try_component(entity_id, ecs_components.NotWithinZones)
            if not_within is not None:
                before_not = set(not_within.zone_ids)
                not_within_zones = set(before_not)
                not_within_zones.difference_update(entered.zone_ids)

                if not_within_zones:
                    esper.add_component(entity_id, ecs_components.NotWithinZones(zone_ids=list(not_within_zones)))
                else:
                    try:
                        esper.remove_component(entity_id, ecs_components.NotWithinZones)
                    except KeyError:
                        pass

            try:
                esper.remove_component(entity_id, ecs_components.EnteredZones)
            except KeyError:
                pass

        for entity_id, exited in list(esper.get_component(ecs_components.ExitedZones)):
            # WithinZones: remove exited zones
            within = esper.try_component(entity_id, ecs_components.WithinZones)
            if within is not None:
                before_zones = set(within.zone_ids)
                within_zones = set(before_zones)
                within_zones.difference_update(exited.zone_ids)

                if within_zones:
                    esper.add_component(entity_id, ecs_components.WithinZones(zone_ids=list(within_zones)))
                else:
                    try:
                        esper.remove_component(entity_id, ecs_components.WithinZones)
                    except KeyError:
                        pass

                if within_zones != before_zones:
                    esper.add_component(entity_id, ecs_components.ZoneBordersDirty())

            # NotWithinZones: add exited zones
            not_within = esper.try_component(entity_id, ecs_components.NotWithinZones)
            before_not = set(not_within.zone_ids) if not_within else set()
            not_within_zones = set(before_not)
            not_within_zones.update(exited.zone_ids)

            esper.add_component(entity_id, ecs_components.NotWithinZones(zone_ids=list(not_within_zones)))

            try:
                esper.remove_component(entity_id, ecs_components.ExitedZones)
            except KeyError:
                pass

