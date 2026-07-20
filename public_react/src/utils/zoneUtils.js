// Normalize zone data from Firebase to GeoJSON format
export function normalizeZones(rawZones) {
  if (!rawZones || typeof rawZones !== 'object') return {};

  const normalized = {};
  
  for (const [key, entry] of Object.entries(rawZones)) {
    if (!entry || typeof entry !== 'object') continue;

    // If it's already a GeoJSON feature, use it as-is
    if (entry.type === 'Feature') {
      normalized[key] = {
        ...entry,
        properties: {
          ...entry.properties,
          id: entry.properties?.id || key,
        },
      };
      continue;
    }

    // Otherwise, try to construct a GeoJSON feature
    const properties = entry.properties || entry;
    const coordinates = entry.geometry?.coordinates || entry.coordinates;

    if (!coordinates) continue;

    normalized[key] = {
      type: 'Feature',
      geometry: {
        type: inferGeometryType(coordinates),
        coordinates,
      },
      properties: {
        ...properties,
        id: properties.id || key,
      },
    };
  }

  return normalized;
}

export function inferGeometryType(coordinates) {
  if (!Array.isArray(coordinates) || coordinates.length === 0) {
    return 'Point';
  }
  
  // Check if it's a simple [lng, lat] point
  if (typeof coordinates[0] === 'number' && typeof coordinates[1] === 'number') {
    return 'Point';
  }
  
  // If first element is an array, it's likely a Polygon
  if (Array.isArray(coordinates[0])) {
    return 'Polygon';
  }
  
  return 'Point';
}

export function isVisibleToUser(zone, userId, userPass) {
  // Admins can see everything
  if (userPass === 'adm1n') return true;

  const visibleTo = zone.properties?.appearance?.visibleTo;
  
  // If no visibility set, check if it's the user's own zone
  if (!visibleTo) {
    return zone.properties?.id === userId;
  }

  if (Array.isArray(visibleTo)) {
    return visibleTo.includes('*') || visibleTo.includes(userId);
  }

  return false;
}

export function parseVisibleList(value) {
  if (!value || typeof value !== 'string') return [];
  return value.split(',').map(s => s.trim()).filter(Boolean);
}
