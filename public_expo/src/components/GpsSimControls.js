import { useApp } from "../AppContext";

// The GPS/Sim toggle button - floats next to the zone/event drawer toggles.
export function GpsToggleButton() {
  const { gpsMode, toggleGpsMode } = useApp();
  return (
    <button
      className="gps-toggle"
      type="button"
      aria-label="Toggle GPS/Sim mode"
      title="Toggle between GPS and Simulation mode"
      data-mode={gpsMode ? "gps" : "sim"}
      onClick={toggleGpsMode}
    >
      {gpsMode ? "GPS" : "Sim"}
    </button>
  );
}

export function SimControls() {
  const { gpsMode, moveSimulatedLocation } = useApp();
  if (gpsMode) return null;

  const STEP = 0.00003;
  return (
    <div className="sim-controls">
      <button className="sim-button sim-up-right" type="button" aria-label="Move up" onClick={() => moveSimulatedLocation(STEP, STEP)}>
        ↗
      </button>
      <button className="sim-button sim-up-left" type="button" aria-label="Move left" onClick={() => moveSimulatedLocation(-STEP, STEP)}>
        ↖
      </button>
      <button className="sim-button sim-down-right" type="button" aria-label="Move right" onClick={() => moveSimulatedLocation(STEP, -STEP)}>
        ↘
      </button>
      <button className="sim-button sim-down-left" type="button" aria-label="Move down" onClick={() => moveSimulatedLocation(-STEP, -STEP)}>
        ↙
      </button>
    </div>
  );
}
