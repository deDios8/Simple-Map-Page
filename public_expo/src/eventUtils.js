// Pure helper functions for event (trigger/target/result rule) data - no DOM, no React.

function normalizeEventEntry(key, entry) {
  if (!entry || typeof entry !== "object") return null;
  const properties = entry.properties && typeof entry.properties === "object" ? entry.properties : {};
  return {
    type: entry.type || "Feature",
    geometry: null,
    properties: { ...properties, id: properties.id || key },
  };
}

// Turns a raw Firebase `events` snapshot value into { [id]: normalizedEvent }.
export function normalizeEvents(rawEvents) {
  if (!rawEvents || typeof rawEvents !== "object") return {};
  return Object.entries(rawEvents).reduce((accumulator, [key, entry]) => {
    const normalized = normalizeEventEntry(key, entry);
    if (normalized) {
      accumulator[key] = normalized;
    }
    return accumulator;
  }, {});
}

// Filters an event's Triggers/Targets bucket down to only recognized component names.
export function extractCriteriaComponents(properties, allowedNames) {
  if (!properties || typeof properties !== "object") return {};
  const knownNames = new Set(allowedNames);
  const components = {};
  for (const [key, value] of Object.entries(properties)) {
    if (knownNames.has(key) && value && typeof value === "object") {
      components[key] = value;
    }
  }
  return components;
}

// Filters an event's Results bucket down to only recognized component names.
export function extractResults(properties, resultComponentOptions) {
  const results = properties?.Results;
  if (!results || typeof results !== "object") return {};
  const knownNames = new Set(resultComponentOptions);
  const out = {};
  for (const [key, value] of Object.entries(results)) {
    if (knownNames.has(key) && value && typeof value === "object") {
      out[key] = value;
    }
  }
  return out;
}

// Converts a criterion/result row's free-text "tag1, tag2" input into an array.
export function parseCsv(value) {
  return String(value || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}
