import "./styles.css";
import { AppProvider, useApp } from "./src/AppContext";
import MapView from "./src/components/MapView";
import StatusCard from "./src/components/StatusCard";
import { SimControls } from "./src/components/GpsSimControls";
import { MapLayerToggleButton } from "./src/components/MapLayerToggle";
import RequestButtons from "./src/components/RequestButtons";
import ZonesDrawer from "./src/components/ZonesDrawer";
import EventsDrawer from "./src/components/EventsDrawer";
import LoginModal from "./src/components/LoginModal";
import MessageModal from "./src/components/MessageModal";

export default function App() {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  );
}

function AppShell() {
  const { userId, coordPickMode } = useApp();

  return (
    <main className={`app-shell${coordPickMode ? " is-picking-coords" : ""}`}>
      <div id="map" aria-label="Interactive map">
        <MapView />
      </div>

      <StatusCard />
      {/* <MapLayerToggleButton /> */}
      <SimControls />
      <RequestButtons />

      <ZonesDrawer />
      <EventsDrawer />

      {!userId && <LoginModal />}
      <MessageModal />
    </main>
  );
}
