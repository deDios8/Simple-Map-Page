import mapCriteriaComponents from "../config/mapCriteriaComponents.json";
import mapResultComponents from "../config/mapResultComponents.json";

export const CRITERIA_COMPONENT_OPTIONS = Object.keys(mapCriteriaComponents);

export const TRIGGER_COMPONENT_OPTIONS = Object.entries(mapCriteriaComponents)
  .filter(([, meta]) => meta.role === "trigger")
  .map(([name]) => name);

export const TARGET_COMPONENT_OPTIONS = Object.entries(mapCriteriaComponents)
  .filter(([, meta]) => meta.role === "target")
  .map(([name]) => name);

export const RESULT_COMPONENT_FIELD_CONFIG = mapResultComponents;

export const RESULT_COMPONENT_OPTIONS = Object.keys(mapResultComponents);

