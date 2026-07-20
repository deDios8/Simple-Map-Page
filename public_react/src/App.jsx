import { useState, useEffect, useCallback } from 'react';
import { ref, update } from 'firebase/database';
import { initializeFirebase, getFirebasePath } from './firebase';
import { useFirebaseData } from './hooks/useFirebaseData';
import { useGeolocation } from './hooks/useGeolocation';
import { normalizeZones } from './utils/zoneUtils';
import MapView from './components/MapView';
import StatusCard from './components/StatusCard';
import SimControls from './components/SimControls';
import RequestButtons from './components/RequestButtons';
import ZonesDrawer from './components/ZonesDrawer';
import './styles.css';

function App() {
  // Firebase state
  const [database, setDatabase] = useState(null);
  const [config, setConfig] = useState(null);
  const [userId, setUserId] = useState(null);
  const [userPass, setUserPass] = useState(null);
  const [sessionName, setSessionName] = useState('');

  // UI state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [eventsDrawerOpen, setEventsDrawerOpen] = useState(false);
  const [selectedZoneId, setSelectedZoneId] = useState(null);
  const [gpsMode, setGpsMode] = useState(true);
  const [listenerActive, setListenerActive] = useState(true);
  const [coordPickMode, setCoordPickMode] = useState(false);

  // Location state
  const [simulatedLocation, setSimulatedLocation] = useState(null);
  const { location: gpsLocation, status: gpsStatus } = useGeolocation(
    gpsMode,
    config?.updateLocationInterval || 0
  );

  const currentLocation = gpsMode ? gpsLocation : simulatedLocation;
  const locationStatus = gpsMode ? gpsStatus : `SIM: ${simulatedLocation?.lat.toFixed(6)}, ${simulatedLocation?.lng.toFixed(6)}`;

  // Firebase paths
  const zonesPath = config && userId && sessionName 
    ? getFirebasePath(config.firebaseZoneNode, { userId, sessionName })
    : null;
  
  const eventsPath = config && userId && sessionName
    ? getFirebasePath(config.firebaseEventsNode, { userId, sessionName })
    : null;

  // Firebase data
  const { data: rawZones } = useFirebaseData(database, zonesPath, listenerActive);
  const { data: events } = useFirebaseData(database, eventsPath, listenerActive);

  // Normalize zones from Firebase
  const zones = normalizeZones(rawZones);

  // Initialize Firebase
  useEffect(() => {
    initializeFirebase()
      .then(({ database, config }) => {
        setDatabase(database);
        setConfig(config);
        
        // Prompt for user credentials
        const storedUserId = localStorage.getItem('userId');
        const storedUserPass = localStorage.getItem('userPass');
        const storedSessionName = localStorage.getItem('sessionName');

        if (storedUserId && storedUserPass && storedSessionName) {
          setUserId(storedUserId);
          setUserPass(storedUserPass);
          setSessionName(storedSessionName);
        } else {
          promptUserCredentials();
        }
      })
      .catch((error) => {
        console.error('Failed to initialize Firebase:', error);
        alert('Failed to load configuration. Please check online_config.json');
      });
  }, []);

  // Initialize simulated location with GPS location
  useEffect(() => {
    if (gpsLocation && !simulatedLocation) {
      setSimulatedLocation(gpsLocation);
    }
  }, [gpsLocation]);

  // Start coordinate tracking when user is set and location is available
  useEffect(() => {
    if (!database || !config || !userId || !currentLocation) return;

    const trackingInterval = setInterval(async () => {
      const timestamp = new Date().toISOString();
      const requestKey = `${Date.now()}-${userId}-location_update`;
      const zonePath = getFirebasePath(config.firebaseZoneNode, { userId, sessionName });
      
      const locationFeature = {
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [currentLocation.lng, currentLocation.lat],
        },
        properties: {
          id: userId,
          timestamp,
          traits: [],
        },
      };

      try {
        await update(ref(database, `${zonePath}/${userId}`), locationFeature);
      } catch (error) {
        console.error('Failed to update location:', error);
      }
    }, config.updateLocationInterval || 2000);

    return () => clearInterval(trackingInterval);
  }, [database, config, userId, sessionName, currentLocation]);

  const promptUserCredentials = () => {
    const id = prompt('Enter User ID:');
    const pass = prompt('Enter Password:');
    const session = prompt('Enter Session Name:');

    if (id && pass && session) {
      setUserId(id);
      setUserPass(pass);
      setSessionName(session);
      localStorage.setItem('userId', id);
      localStorage.setItem('userPass', pass);
      localStorage.setItem('sessionName', session);
    }
  };

  const handleToggleGps = () => {
    setGpsMode(!gpsMode);
    if (!gpsMode && gpsLocation) {
      setSimulatedLocation(gpsLocation);
    }
  };

  const handleSimMove = (deltaLng, deltaLat) => {
    if (simulatedLocation) {
      setSimulatedLocation({
        lat: simulatedLocation.lat + deltaLat,
        lng: simulatedLocation.lng + deltaLng,
      });
    }
  };

  const handleRequest = async (requestType) => {
    if (!database || !config || !userId || !sessionName || !currentLocation) {
      alert('System not ready');
      return;
    }

    const requestPath = getFirebasePath(config.firebaseClientRequestNode, { userId, sessionName });
    const timestamp = new Date().toISOString();
    const requestKey = `${Date.now()}-${userId}-${requestType}`.replace(/\s+/g, '-');
    
    const requestFeature = {
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [currentLocation.lng, currentLocation.lat],
      },
      properties: {
        id: requestKey,
        clientRequestPayload: {
          requesterId: userId,
          timestamp,
          type: requestType,
          requestedAction: requestType,
        },
      },
    };

    try {
      await update(ref(database, `${requestPath}/${requestKey}`), requestFeature);
      console.log('Request sent:', requestType);
    } catch (error) {
      console.error('Failed to send request:', error);
      alert('Failed to send request');
    }
  };

  const handleAddZone = () => {
    if (!currentLocation) {
      alert('Location not available');
      return;
    }

    const newZoneId = `zone-${Date.now()}`;
    const newZone = {
      appearance: {
        displayName: 'New Zone',
        color: '#0b8f87',
        visibleTo: ['*'],
        radius: 50,
      },
      traits: [],
      stats: {},
    };

    setSelectedZoneId(newZoneId);
    handleEditZone(newZoneId, newZone);
  };

  const handleEditZone = async (zoneId, zoneData) => {
    if (!database || !config || !userId || !sessionName || !currentLocation) return;

    const requestPath = getFirebasePath(config.firebaseClientRequestNode, { userId, sessionName });
    const timestamp = new Date().toISOString();
    const requestKey = `${Date.now()}-${userId}-edit-${zoneId}`;
    
    const requestFeature = {
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [currentLocation.lng, currentLocation.lat],
      },
      properties: {
        id: requestKey,
        clientRequestPayload: {
          requesterId: userId,
          timestamp,
          type: 'edited_zone',
          requestedAction: `edit-${zoneId}`,
          targetId: zoneId,
          targetPath: `${zonesPath}/${zoneId}`,
        },
        formData: zoneData,
      },
    };

    try {
      await update(ref(database, `${requestPath}/${requestKey}`), requestFeature);
      console.log('Edit request sent for zone:', zoneId);
    } catch (error) {
      console.error('Failed to send edit request:', error);
      alert('Failed to send edit request');
    }
  };

  const handleDeleteZone = async (zoneId) => {
    if (!database || !config || !userId || !sessionName || !currentLocation) return;

    const requestPath = getFirebasePath(config.firebaseClientRequestNode, { userId, sessionName });
    const timestamp = new Date().toISOString();
    const requestKey = `${Date.now()}-${userId}-delete-${zoneId}`;
    
    const requestFeature = {
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [currentLocation.lng, currentLocation.lat],
      },
      properties: {
        id: requestKey,
        clientRequestPayload: {
          requesterId: userId,
          timestamp,
          type: 'deleted_zone',
          requestedAction: `delete-${zoneId}`,
          targetId: zoneId,
          targetPath: `${zonesPath}/${zoneId}`,
        },
      },
    };

    try {
      await update(ref(database, `${requestPath}/${requestKey}`), requestFeature);
      console.log('Delete request sent for zone:', zoneId);
    } catch (error) {
      console.error('Failed to send delete request:', error);
      alert('Failed to send delete request');
    }
  };

  const handleClearLogs = async (zoneId) => {
    if (!database || !config || !userId || !sessionName || !currentLocation) return;

    const requestPath = getFirebasePath(config.firebaseClientRequestNode, { userId, sessionName });
    const timestamp = new Date().toISOString();
    const requestKey = `${Date.now()}-${userId}-clear-logs-${zoneId}`;
    
    const requestFeature = {
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [currentLocation.lng, currentLocation.lat],
      },
      properties: {
        id: requestKey,
        clientRequestPayload: {
          requesterId: userId,
          timestamp,
          type: 'clear_logs',
          requestedAction: `clear-logs-${zoneId}`,
          targetId: zoneId,
          targetPath: `${zonesPath}/${zoneId}`,
        },
      },
    };

    try {
      await update(ref(database, `${requestPath}/${requestKey}`), requestFeature);
      console.log('Clear logs request sent for zone:', zoneId);
    } catch (error) {
      console.error('Failed to send clear logs request:', error);
    }
  };

  const handleClearAllLogs = async () => {
    if (!database || !config || !userId || !sessionName || !currentLocation) return;

    const requestPath = getFirebasePath(config.firebaseClientRequestNode, { userId, sessionName });
    const timestamp = new Date().toISOString();
    const requestKey = `${Date.now()}-${userId}-clear-logs-all`;
    
    const requestFeature = {
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [currentLocation.lng, currentLocation.lat],
      },
      properties: {
        id: requestKey,
        clientRequestPayload: {
          requesterId: userId,
          timestamp,
          type: 'clear_logs_all',
          requestedAction: 'clear-logs-all',
        },
      },
    };

    try {
      await update(ref(database, `${requestPath}/${requestKey}`), requestFeature);
      console.log('Clear all logs request sent');
    } catch (error) {
      console.error('Failed to send clear all logs request:', error);
    }
  };

  const handleMapClick = (latlng) => {
    if (coordPickMode) {
      // Handle coordinate picking for zone editor
      console.log('Picked coordinates:', latlng);
    }
  };

  return (
    <main className="app">
      <MapView
        location={currentLocation}
        zones={zones}
        onMapClick={handleMapClick}
        coordPickMode={coordPickMode}
        selectedId={selectedZoneId}
        userId={userId}
        userPass={userPass}
        mapLayer={config?.mapLayer || ''}
        mapLayerAttribution={config?.mapLayerAttribution || ''}
      />

      <StatusCard status={locationStatus} />

      <SimControls visible={!gpsMode} onMove={handleSimMove} />

      <RequestButtons onRequest={handleRequest} />

      <button
        id="drawer-toggle"
        className="drawer-toggle"
        type="button"
        aria-expanded={drawerOpen}
        aria-controls="drawer"
        aria-label="Open zone list"
        onClick={() => setDrawerOpen(!drawerOpen)}
      >
        <span></span>
        <span></span>
        <span></span>
      </button>

      <ZonesDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        sessionName={sessionName}
        zones={zones}
        selectedId={selectedZoneId}
        onSelectZone={setSelectedZoneId}
        onAddZone={handleAddZone}
        onEditZone={handleEditZone}
        onDeleteZone={handleDeleteZone}
        onClearLogs={handleClearLogs}
        onClearAllLogs={handleClearAllLogs}
        gpsMode={gpsMode}
        onToggleGps={handleToggleGps}
        listenerActive={listenerActive}
        onToggleListener={() => setListenerActive(!listenerActive)}
        currentLocation={currentLocation}
      />
    </main>
  );
}

export default App;
