import { useState, useEffect, useCallback } from 'react';
import { ref, update } from 'firebase/database';
import { initializeFirebase, getFirebasePath } from './firebase';
import { useFirebaseData } from './hooks/useFirebaseData';
import { useGeolocation } from './hooks/useGeolocation';
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
  const { data: zones } = useFirebaseData(database, zonesPath, listenerActive);
  const { data: events } = useFirebaseData(database, eventsPath, listenerActive);

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
    const requestData = {
      type: requestType,
      timestamp: Date.now(),
      location: currentLocation,
      userId: userId,
    };

    try {
      await update(ref(database, requestPath), {
        [Date.now()]: requestData,
      });
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
      name: 'New Zone',
      color: '#0b8f87',
      visible: '*',
      coordinates: [currentLocation.lng, currentLocation.lat],
      radius: 50,
      traits: '',
      stats: {},
    };

    setSelectedZoneId(newZoneId);
    handleEditZone(newZoneId, newZone);
  };

  const handleEditZone = async (zoneId, zoneData) => {
    if (!database || !zonesPath) return;

    try {
      await update(ref(database, `${zonesPath}/${zoneId}`), zoneData);
      console.log('Zone updated:', zoneId);
    } catch (error) {
      console.error('Failed to update zone:', error);
      alert('Failed to update zone');
    }
  };

  const handleDeleteZone = async (zoneId) => {
    if (!database || !zonesPath) return;

    try {
      await update(ref(database, `${zonesPath}/${zoneId}`), null);
      console.log('Zone deleted:', zoneId);
    } catch (error) {
      console.error('Failed to delete zone:', error);
      alert('Failed to delete zone');
    }
  };

  const handleClearLogs = async (zoneId) => {
    if (!database || !zonesPath) return;

    try {
      await update(ref(database, `${zonesPath}/${zoneId}/logs`), null);
      console.log('Logs cleared for zone:', zoneId);
    } catch (error) {
      console.error('Failed to clear logs:', error);
    }
  };

  const handleClearAllLogs = async () => {
    if (!database || !zonesPath || !zones) return;

    try {
      const updates = {};
      Object.keys(zones).forEach(zoneId => {
        updates[`${zoneId}/logs`] = null;
      });
      await update(ref(database, zonesPath), updates);
      console.log('All logs cleared');
    } catch (error) {
      console.error('Failed to clear all logs:', error);
    }
  };

  const handleMapClick = (latlng) => {
    if (coordPickMode) {
      // Handle coordinate picking for zone editor
      console.log('Picked coordinates:', latlng);
    }
  };

  return (
    <main className="app-shell">
      <MapView
        location={currentLocation}
        zones={zones || {}}
        onMapClick={handleMapClick}
        coordPickMode={coordPickMode}
        selectedId={selectedZoneId}
        userId={userId}
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
        zones={zones || {}}
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
