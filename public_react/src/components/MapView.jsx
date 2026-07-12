import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export default function MapView({ 
  location, 
  zones = {}, 
  onMapClick,
  coordPickMode = false,
  selectedId = null,
  userId = null,
  mapLayer = '',
  mapLayerAttribution = ''
}) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const userMarkerRef = useRef(null);
  const geoJsonLayerRef = useRef(null);

  // Initialize map
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    const defaultCenter = [38.8977, -77.0365]; // DC
    const map = L.map(mapRef.current, {
      center: defaultCenter,
      zoom: 13,
      zoomControl: true,
    });

    const tileUrl = mapLayer || 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    const attribution = mapLayerAttribution || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
    
    L.tileLayer(tileUrl, { attribution }).addTo(map);

    if (onMapClick) {
      map.on('click', (e) => {
        if (coordPickMode) {
          onMapClick(e.latlng);
        }
      });
    }

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update map cursor based on coordPickMode
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const container = map.getContainer();
    if (coordPickMode) {
      container.style.cursor = 'crosshair';
    } else {
      container.style.cursor = '';
    }
  }, [coordPickMode]);

  // Update user marker
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !location) return;

    if (userMarkerRef.current) {
      userMarkerRef.current.setLatLng([location.lat, location.lng]);
    } else {
      const marker = L.marker([location.lat, location.lng], {
        icon: L.divIcon({
          className: 'user-marker',
          html: '<div style="width: 16px; height: 16px; border-radius: 50%; background: #0b8f87; border: 3px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.3);"></div>',
          iconSize: [16, 16],
          iconAnchor: [8, 8],
        }),
      }).addTo(map);
      userMarkerRef.current = marker;
    }

    map.setView([location.lat, location.lng], map.getZoom());
  }, [location]);

  // Render zones as GeoJSON
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Remove existing layer
    if (geoJsonLayerRef.current) {
      map.removeLayer(geoJsonLayerRef.current);
      geoJsonLayerRef.current = null;
    }

    // Convert zones to GeoJSON features
    const features = Object.entries(zones)
      .filter(([_, zone]) => zone && zone.coordinates)
      .map(([id, zone]) => {
        const visible = isVisibleToUser(zone, userId);
        if (!visible) return null;

        return {
          type: 'Feature',
          id: id,
          properties: {
            ...zone,
            id: id,
          },
          geometry: {
            type: inferGeometryType(zone.coordinates),
            coordinates: zone.coordinates,
          },
        };
      })
      .filter(Boolean);

    if (features.length === 0) return;

    const geoJsonLayer = L.geoJSON(
      { type: 'FeatureCollection', features },
      {
        pointToLayer: (feature, latlng) => {
          const radius = feature.properties.radius || 50;
          return L.circle(latlng, {
            radius: radius,
            fillColor: feature.properties.color || '#0b8f87',
            fillOpacity: 0.3,
            color: feature.properties.color || '#0b8f87',
            weight: 2,
          });
        },
        style: (feature) => {
          return {
            fillColor: feature.properties.color || '#0b8f87',
            fillOpacity: 0.3,
            color: feature.properties.color || '#0b8f87',
            weight: 2,
          };
        },
        onEachFeature: (feature, layer) => {
          const name = feature.properties.name || feature.id;
          layer.bindPopup(`<strong>${name}</strong>`);
          
          layer.on('click', () => {
            // Handle zone selection if needed
          });

          // Highlight selected zone
          if (feature.id === selectedId) {
            layer.setStyle({
              weight: 4,
              color: '#ff6b00',
            });
          }
        },
      }
    ).addTo(map);

    geoJsonLayerRef.current = geoJsonLayer;
  }, [zones, selectedId, userId]);

  return <div ref={mapRef} id="map" aria-label="Interactive map" />;
}

function inferGeometryType(coordinates) {
  if (!Array.isArray(coordinates) || coordinates.length === 0) {
    return 'Point';
  }
  if (typeof coordinates[0] === 'number') {
    return 'Point';
  }
  if (coordinates.length === 2 && typeof coordinates[0] === 'number') {
    return 'Point';
  }
  return 'Polygon';
}

function isVisibleToUser(zone, userId) {
  if (!zone.visible) return false;
  
  const visibleList = parseVisibleList(zone.visible);
  if (visibleList.includes('*')) return true;
  if (userId && visibleList.includes(userId)) return true;
  
  return false;
}

function parseVisibleList(value) {
  if (!value) return [];
  return String(value)
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
}
