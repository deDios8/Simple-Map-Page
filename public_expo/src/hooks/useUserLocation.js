import { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_LOCATION = [48.21224, -101.31304];

// Tracks the user's position, either from the browser's real GPS (default)
// or from a manually-nudged "simulated" position, toggled by the caller.
export function useUserLocation() {
  const [userLocation, setUserLocation] = useState(null);
  const [gpsMode, setGpsMode] = useState(true);
  const [statusText, setStatusText] = useState("Requesting GPS access...");
  const watchIdRef = useRef(null);
  const gpsModeRef = useRef(true);

  useEffect(() => {
    gpsModeRef.current = gpsMode;
  }, [gpsMode]);

  const startWatch = useCallback(() => {
    if (!navigator.geolocation) {
      setStatusText("Geolocation is not available in this browser.");
      return;
    }
    setStatusText("Waiting for location fix...");
    watchIdRef.current = navigator.geolocation.watchPosition(
      ({ coords }) => {
        const latLng = [
          Math.round(coords.latitude * 100000) / 100000,
          Math.round(coords.longitude * 100000) / 100000,
        ];
        setUserLocation(latLng);
        setStatusText(`${coords.latitude.toFixed(5)}, ${coords.longitude.toFixed(5)}`);
      },
      (error) => {
        setStatusText(`Location unavailable: ${error.message}`);
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 },
    );
  }, []);

  // Start watching GPS position once on mount, mirroring the prototype's locateUser().
  useEffect(() => {
    startWatch();
    return () => {
      if (watchIdRef.current != null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
    };
  }, [startWatch]);

  const toggleGpsMode = useCallback(() => {
    setGpsMode((prevGpsMode) => {
      const nextGpsMode = !prevGpsMode;
      if (nextGpsMode) {
        startWatch();
      } else if (watchIdRef.current != null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
      return nextGpsMode;
    });
  }, [startWatch]);

  // When switching into Sim mode, seed a starting point if there isn't one yet.
  useEffect(() => {
    if (gpsMode) return;
    setUserLocation((prevLocation) => {
      const location = prevLocation || DEFAULT_LOCATION;
      setStatusText(`Sim: ${location[0].toFixed(5)}, ${location[1].toFixed(5)}`);
      return location;
    });
  }, [gpsMode]);

  const moveSimulatedLocation = useCallback((deltaLng, deltaLat) => {
    if (gpsModeRef.current) return; // only works in Sim mode
    setUserLocation((prevLocation) => {
      const base = prevLocation || DEFAULT_LOCATION;
      const nextLat = Math.round((base[0] + deltaLat) * 100000) / 100000;
      const nextLng = Math.round((base[1] + deltaLng) * 100000) / 100000;
      setStatusText(`Sim: ${nextLat.toFixed(5)}, ${nextLng.toFixed(5)}`);
      return [nextLat, nextLng];
    });
  }, []);

  return { userLocation, gpsMode, statusText, setStatusText, toggleGpsMode, moveSimulatedLocation };
}
