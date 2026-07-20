import { initializeApp } from "firebase/app";
import { getDatabase } from "firebase/database";
import onlineConfig from "../config/onlineConfig.json";

const { nodes, defaultSessionName, updateLocationInterval, mapLayer, ...firebaseSdkConfig } = onlineConfig;

const app = initializeApp(firebaseSdkConfig);

export const database = getDatabase(app);
export const NODES = nodes;
export const DEFAULT_SESSION_NAME = defaultSessionName || "testBed";
export const UPDATE_LOCATION_INTERVAL = updateLocationInterval || 2000;
export const MAP_LAYER = mapLayer?.default || {};

export function dbPath(sessionName, node) {
  return `${sessionName}/${node}`;
}

export function normalizeSessionName(rawValue) {
  const trimmed = String(rawValue || "").trim();
  const withoutSlashes = trimmed.replace(/^\/+|\/+$/g, "");
  return withoutSlashes || DEFAULT_SESSION_NAME;
}
