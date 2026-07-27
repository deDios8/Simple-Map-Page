import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, Circle, CircleMarker, Popup, ZoomControl, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useApp } from "../AppContext";
import { isVisibleToCurrentUser } from "../zoneUtils";
import { MAP_LAYERS } from "../firebase";

const DEFAULT_CENTER = [48.21224, -101.31304];
const DEFAULT_ZOOM = 14;

export default function MapView() {
  const { zones, userPass, userId, selectedZoneId, selectZone, userLocation, satelliteView } = useApp();

  const visibleFeatures = Object.values(zones).filter((feature) =>
    isVisibleToCurrentUser(feature, { userPass, userId, zones }),
  );

  const mapLayer = satelliteView ? MAP_LAYERS.satellite : MAP_LAYERS.street;

  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={DEFAULT_ZOOM}
      zoomControl={false}
      style={{ height: "100%", width: "100%" }}
    >
      <ZoomControl position="topright" />
      <TileLayer url={mapLayer.url} attribution={mapLayer.attribution} maxZoom={19} minZoom={12} />

      {visibleFeatures.map((feature) => (
        <ZoneMarker
          key={feature.properties.id}
          feature={feature}
          onSelect={() => selectZone(feature.properties.id)}
        />
      ))}

      {userLocation && (
        <CircleMarker
          center={userLocation}
          radius={2}
          pathOptions={{ color: "#12413a", weight: 2, fillColor: "#f9fffd", fillOpacity: 0.95 }}
        />
      )}

      <MapClickHandler />
      <FlyToSelection selectedZoneId={selectedZoneId} zones={zones} />
      <CenterOnFirstFix userLocation={userLocation} />
    </MapContainer>
  );
}

// Zones render as Circles (radius in meters), matching the prototype's
// L.circle usage - distinct from the user's own dot, which is a pixel-radius
// CircleMarker.
function ZoneMarker({ feature, onSelect }) {
  const fill = feature.properties?.appearance?.fill || "#ffffff";
  const border = feature.properties?.appearance?.border || "#ffffff";
  const radius = Number.isFinite(feature.properties?.appearance?.radius) ? feature.properties.appearance.radius : 5;
  const opacity = Number.isFinite(feature.properties?.appearance?.opacity) ? feature.properties.appearance.opacity : 0.5;
  const coordinates = feature.geometry?.coordinates;
  if (!Array.isArray(coordinates)) return null;
  const [lng, lat] = coordinates;

  return (
    <Circle
      center={[lat, lng]}
      radius={radius}
      pathOptions={{ color: border, fillColor: fill, fillOpacity: opacity, weight: 2 }}
      eventHandlers={{ click: onSelect }}
    >
      <Popup>{feature.properties?.displayName || feature.properties?.id || "Untitled zone"}</Popup>
    </Circle>
  );
}

function MapClickHandler() {
  const { coordPickMode, pickCoordinates } = useApp();
  useMapEvents({
    click(event) {
      if (!coordPickMode) return;
      pickCoordinates(event.latlng.lat, event.latlng.lng);
    },
  });
  return null;
}

// Flies to the selected zone whenever the selection changes (e.g. picked from
// the zone list).
function FlyToSelection({ selectedZoneId, zones }) {
  const map = useMap();
  useEffect(() => {
    if (!selectedZoneId) return;
    const feature = zones[selectedZoneId];
    const coordinates = feature?.geometry?.coordinates;
    if (feature?.geometry?.type !== "Point" || !Array.isArray(coordinates)) return;
    const [lng, lat] = coordinates;
    map.flyTo([lat, lng], map.getZoom(), { duration: 0.6 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedZoneId]);
  return null;
}

// Centers the map on the user's own position only once, the first time a fix
// arrives - subsequent updates just move the marker, they don't recenter.
function CenterOnFirstFix({ userLocation }) {
  const map = useMap();
  const hasCenteredRef = useRef(false);
  useEffect(() => {
    if (!userLocation || hasCenteredRef.current) return;
    hasCenteredRef.current = true;
    map.setView(userLocation, 16);
  }, [userLocation, map]);
  return null;
}
