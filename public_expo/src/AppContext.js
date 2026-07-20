import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { NODES, DEFAULT_SESSION_NAME, UPDATE_LOCATION_INTERVAL, normalizeSessionName } from "./firebase";
import { normalizeObjects } from "./zoneUtils";
import { normalizeEvents } from "./eventUtils";
import { useFirebaseCollection } from "./hooks/useFirebaseCollection";
import { useUserLocation } from "./hooks/useUserLocation";
import { submitNewLocationRequest } from "./requests";

const AppContext = createContext(null);

const ACCEPTED_PASSWORDS = new Set(["user", "adm1n"]);

export function AppProvider({ children }) {
  const [sessionName, setSessionName] = useState(DEFAULT_SESSION_NAME);
  const [userId, setUserId] = useState(null);
  const [userPass, setUserPass] = useState(null);
  const [selectedZoneId, setSelectedZoneId] = useState(null);
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [listenerActive, setListenerActive] = useState(true);
  const [dismissedMessages, setDismissedMessages] = useState(() => new Set());
  const [coordPickMode, setCoordPickMode] = useState(false);
  const [pickedCoordinates, setPickedCoordinates] = useState(null);

  const [zones, setZones] = useFirebaseCollection(sessionName, NODES.zones, normalizeObjects, listenerActive);
  const [events] = useFirebaseCollection(sessionName, NODES.events, normalizeEvents, listenerActive);

  const location = useUserLocation();
  const { userLocation } = location;

  const isAdmin = userPass === "adm1n";

  // If the selected zone/event disappears from a new snapshot (e.g. deleted
  // server-side), clear the selection instead of pointing at stale data.
  useEffect(() => {
    setSelectedZoneId((prev) => (prev && !zones[prev] ? null : prev));
  }, [zones]);
  useEffect(() => {
    setSelectedEventId((prev) => (prev && !events[prev] ? null : prev));
  }, [events]);

  // Forget dismissed messages once they're actually gone from the DB, so a
  // message re-added later (same text) can pop up again.
  useEffect(() => {
    if (!userId) return;
    const currentMessages = new Set(zones[userId]?.properties?.messages ?? []);
    setDismissedMessages((prev) => {
      let changed = false;
      const next = new Set();
      for (const message of prev) {
        if (currentMessages.has(message)) {
          next.add(message);
        } else {
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [zones, userId]);

  const pendingMessage = useMemo(() => {
    const messages = zones[userId]?.properties?.messages;
    if (!Array.isArray(messages)) return null;
    return messages.find((message) => !dismissedMessages.has(message)) ?? null;
  }, [zones, userId, dismissedMessages]);

  function dismissMessage(message) {
    setDismissedMessages((prev) => new Set(prev).add(message));
  }

  // Periodically push the user's current location to the backend, and
  // optimistically move their own marker locally between server echoes.
  const userLocationRef = useRef(userLocation);
  useEffect(() => {
    userLocationRef.current = userLocation;
  }, [userLocation]);

  useEffect(() => {
    if (!userId) return undefined;
    const intervalId = setInterval(() => {
      const currentLocation = userLocationRef.current;
      if (!currentLocation) return;

      setZones((prev) => {
        const existing = prev[userId];
        if (!existing) return prev;
        return {
          ...prev,
          [userId]: {
            ...existing,
            geometry: { ...existing.geometry, coordinates: [currentLocation[1], currentLocation[0]] },
          },
        };
      });

      submitNewLocationRequest(sessionName, userId, currentLocation).catch((error) => {
        console.error(error);
      });
    }, UPDATE_LOCATION_INTERVAL);
    return () => clearInterval(intervalId);
  }, [userId, sessionName, setZones]);

  function login(rawSessionName, rawUserId, rawPassword) {
    const id = String(rawUserId || "").trim();
    const password = String(rawPassword || "").trim().toLowerCase();
    if (!id) return { ok: false, error: "" };
    if (!ACCEPTED_PASSWORDS.has(password)) {
      return { ok: false, error: "password rejected" };
    }
    setSessionName(normalizeSessionName(rawSessionName));
    setUserId(id);
    setUserPass(password);
    return { ok: true };
  }

  function toggleListener() {
    setListenerActive((prev) => !prev);
  }

  // Map click-to-pick-coordinates: MapView reads coordPickMode/pickCoordinates;
  // ZoneEditor starts pick mode and consumes pickedCoordinates when they land.
  function pickCoordinates(lat, lng) {
    setPickedCoordinates({ lat, lng });
    setCoordPickMode(false);
  }

  const value = {
    sessionName,
    userId,
    userPass,
    isAdmin,
    login,

    zones,
    events,

    selectedZoneId,
    selectZone: setSelectedZoneId,
    selectedEventId,
    selectEvent: setSelectedEventId,

    listenerActive,
    toggleListener,

    userLocation: location.userLocation,
    gpsMode: location.gpsMode,
    statusText: location.statusText,
    setStatusText: location.setStatusText,
    toggleGpsMode: location.toggleGpsMode,
    moveSimulatedLocation: location.moveSimulatedLocation,

    pendingMessage,
    dismissMessage,

    coordPickMode,
    setCoordPickMode,
    pickedCoordinates,
    pickCoordinates,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp() must be used inside an <AppProvider>");
  }
  return context;
}
