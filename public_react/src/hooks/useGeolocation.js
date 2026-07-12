import { useState, useEffect, useCallback } from 'react';

export function useGeolocation(gpsMode = true, updateInterval = 0) {
  const [location, setLocation] = useState(null);
  const [status, setStatus] = useState('Requesting GPS access...');
  const [error, setError] = useState(null);
  const [watchId, setWatchId] = useState(null);

  const stopWatching = useCallback(() => {
    if (watchId !== null) {
      navigator.geolocation.clearWatch(watchId);
      setWatchId(null);
    }
  }, [watchId]);

  useEffect(() => {
    if (!gpsMode) {
      stopWatching();
      return;
    }

    if (!navigator.geolocation) {
      setStatus('Geolocation not supported');
      setError(new Error('Geolocation not supported'));
      return;
    }

    const options = {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: updateInterval,
    };

    const handleSuccess = (position) => {
      const { latitude, longitude } = position.coords;
      setLocation({ lat: latitude, lng: longitude });
      setStatus(`${latitude.toFixed(6)}, ${longitude.toFixed(6)}`);
      setError(null);
    };

    const handleError = (err) => {
      console.error('Geolocation error:', err);
      setError(err);
      
      switch (err.code) {
        case err.PERMISSION_DENIED:
          setStatus('GPS permission denied');
          break;
        case err.POSITION_UNAVAILABLE:
          setStatus('Location unavailable');
          break;
        case err.TIMEOUT:
          setStatus('GPS request timed out');
          break;
        default:
          setStatus('GPS error occurred');
      }
    };

    const id = navigator.geolocation.watchPosition(
      handleSuccess,
      handleError,
      options
    );
    
    setWatchId(id);

    return () => {
      if (id !== null) {
        navigator.geolocation.clearWatch(id);
      }
    };
  }, [gpsMode, updateInterval]);

  return { location, status, error, stopWatching };
}
