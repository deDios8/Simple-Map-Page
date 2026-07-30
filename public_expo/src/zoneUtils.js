// Pure helper functions for zone (map feature) data - no DOM, no React.

export function nameToKey(name) {
  return String(name).trim().toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_-]/g, "");
}

export function createDefaultStat() {
  return { key: "", name: "", value: 0, max_value: 100, min_value: 0 };
}

// Converts a zone's raw `properties.stats` into { [key]: {name,value,min_value,max_value} }.
export function normalizeStats(properties) {
  const rawStats = properties?.stats;
  if (!rawStats || typeof rawStats !== "object" || Array.isArray(rawStats)) {
    return {};
  }
  const nextStats = {};
  for (const [key, rawStat] of Object.entries(rawStats)) {
    if (!rawStat || typeof rawStat !== "object" || Array.isArray(rawStat)) {
      continue;
    }
    const statKey = String(key || rawStat.name || "").trim();
    if (!statKey) {
      continue;
    }
    nextStats[statKey] = {
      name: String(rawStat.name || ""),
      value: Number.isFinite(rawStat.value) ? rawStat.value : 0,
      max_value: Number.isFinite(rawStat.max_value) ? rawStat.max_value : 100,
      min_value: Number.isFinite(rawStat.min_value) ? rawStat.min_value : 0,
    };
  }
  return nextStats;
}

// Converts the stats-editor's row list (array of {key,name,value,min_value,max_value})
// back into a stats object, validating duplicate keys and min/max ordering.
export function collectStats(rows) {
  const stats = {};
  for (const [index, row] of rows.entries()) {
    const name = String(row.name || "").trim();
    const rawValueText = row.value === undefined || row.value === null ? "" : String(row.value);
    if (!name && !rawValueText.trim()) {
      continue;
    }

    const min = Number.isFinite(row.min_value) ? row.min_value : 0;
    const max = Number.isFinite(row.max_value) ? row.max_value : 100;
    if (max < min) {
      return { stats: {}, error: `Stat ${index + 1}: max must be greater than or equal to min.` };
    }

    const rawValue = Number.parseFloat(rawValueText);
    const value = Number.isFinite(rawValue) ? rawValue : 0;
    const key = nameToKey(name) || row.key || `stat-${index + 1}`;
    if (Object.prototype.hasOwnProperty.call(stats, key)) {
      return { stats: {}, error: `Duplicate stat key: ${key}` };
    }

    stats[key] = {
      name,
      value: Math.min(max, Math.max(min, value)),
      max_value: max,
      min_value: min,
    };
  }
  return { stats, error: null };
}

export function parseVisibleList(value) {
  if (!value || typeof value !== "string") return [];
  return value.split(",").map((s) => s.trim()).filter(Boolean);
}

// Converts the appearance editor's "1, 0" dash-pattern input into an array of
// non-negative numbers for Leaflet's dashArray, dropping any comma-separated
// entries that aren't valid numbers (this is the "correction" - bad entries
// are silently removed rather than blocking the whole field).
export function parseDashArray(value) {
  if (!value || typeof value !== "string") return [];
  return value
    .split(",")
    .map((s) => Number.parseFloat(s.trim()))
    .filter((n) => Number.isFinite(n) && n >= 0);
}

// A zone is visible to the current user if the admin password is used, or if
// the zone's appearance.visibleTo tags intersect the current user's own traits.
export function isVisibleToCurrentUser(feature, { userPass, userId, zones }) {
  if (userPass === "adm1n") return true;

  const visibleTo = feature.properties?.appearance?.visibleTo;
  if (!Array.isArray(visibleTo) || visibleTo.length === 0) return false;

  const userTraits = zones?.[userId]?.properties?.traits;
  const userTraitSet = new Set(
    (Array.isArray(userTraits) ? userTraits : [])
      .map((t) => (typeof t === "string" ? t.toUpperCase() : null))
      .filter(Boolean),
  );
  return visibleTo.some((key) => userTraitSet.has(String(key).toUpperCase()));
}

function inferGeometryType(coordinates) {
  if (!Array.isArray(coordinates) || coordinates.length < 2) {
    return "";
  }
  const first = coordinates[0];
  if (typeof first === "number") return "Point";
  if (Array.isArray(first) && typeof first[0] === "number") return "LineString";
  if (Array.isArray(first) && Array.isArray(first[0]) && typeof first[0][0] === "number") return "Polygon";
  return "";
}

function normalizeFeatureEntry(key, entry) {
  if (!entry || typeof entry !== "object") return null;

  const properties = entry.properties && typeof entry.properties === "object" ? entry.properties : {};
  const geometry = entry.geometry && typeof entry.geometry === "object" ? entry.geometry : {};
  const coordinates = Array.isArray(geometry.coordinates) ? geometry.coordinates : [];
  const geometryType = geometry.type || inferGeometryType(coordinates);
  if (!geometryType) return null;

  return {
    ...entry,
    type: entry.type || "Feature",
    geometry: { ...geometry, type: geometryType, coordinates },
    properties: { ...properties, id: properties.id || key },
  };
}

// Turns a raw Firebase `zones` snapshot value into { [id]: normalizedFeature }.
export function normalizeObjects(rawObjects) {
  if (!rawObjects || typeof rawObjects !== "object") return {};
  return Object.entries(rawObjects).reduce((accumulator, [key, entry]) => {
    const normalizedEntry = normalizeFeatureEntry(key, entry);
    if (normalizedEntry) {
      accumulator[key] = normalizedEntry;
    }
    return accumulator;
  }, {});
}
