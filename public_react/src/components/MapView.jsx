import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { isVisibleToUser, inferGeometryType } from '../utils/zoneUtils';

export default function MapView({ 
  location, 
  zones = {}, 
  onMapClick,
  coordPickMode = false,
  selectedId = null,
  userId = null,
  userPass = null,
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
      .filter(([_, zone]) => zone && zone.geometry && zone.geometry.coordinates)
      .map(([id, zone]) => {
        const visible = isVisibleToUser(zone, userId, userPass);
        if (!visible) return null;

        return {
          type: 'Feature',
          id: id,
          properties: {
            ...zone.properties,
            id: id,
          },
          geometry: zone.geometry,
        };
      })
      .filter(Boolean);

    if (features.length === 0) return;

    const geoJsonLayer = L.geoJSON(
      { type: 'FeatureCollection', features },
      {
        pointToLayer: (feature, latlng) => {
          const radius = feature.properties?.appearance?.radius || 50;
          const color = feature.properties?.appearance?.color || '#0b8f87';
          return L.circle(latlng, {
            radius: radius,
            fillColor: color,
            fillOpacity: 0.3,
            color: color,
            weight: 2,
          });
        },
        style: (feature) => {
          const color = feature.properties?.appearance?.color || '#0b8f87';
          return {
            fillColor: color,
            fillOpacity: 0.3,
            color: color,
            weight: 2,
          };
        },
        onEachFeature: (feature, layer) => {
          const name = feature.properties?.appearance?.displayName || feature.id;
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
  }, [zones, selectedId, userId, userPass]);

  return <div ref={mapRef} id="map" aria-label="Interactive map" />;
}
