import { initializeApp } from "firebase/app";
import { getAuth, signInAnonymously } from "firebase/auth";
import { getDatabase } from "firebase/database";
import onlineConfig from "../config/onlineConfig.json";

const { nodes, defaultSessionName, updateLocationInterval, mapLayer, ...firebaseSdkConfig } = onlineConfig;

const app = initializeApp(firebaseSdkConfig);

export const database = getDatabase(app);
export const auth = getAuth(app);

// Every client needs to be signed in (even anonymously) before the database
// rules will let it write to zzz_clientRequests. This kicks off right away
// so sign-in has finished long before a user submits their first request.
signInAnonymously(auth).catch((error) => {
  console.error("Anonymous sign-in failed:", error);
});

export const NODES = nodes;
export const DEFAULT_SESSION_NAME = defaultSessionName || "testBed";
export const UPDATE_LOCATION_INTERVAL = updateLocationInterval || 2000;
export const MAP_LAYERS = {
  satellite: mapLayer?.default || {},
  street: mapLayer?.alternative || {},
};

export function dbPath(sessionName, node) {
  return `${sessionName}/${node}`;
}

export function normalizeSessionName(rawValue) {
  const trimmed = String(rawValue || "").trim();
  const withoutSlashes = trimmed.replace(/^\/+|\/+$/g, "");
  return withoutSlashes || DEFAULT_SESSION_NAME;
}
