import { useApp } from "../AppContext";

// The GPS/Sim toggle button - lives in the zones drawer header, matching the
// prototype's #gps-toggle placement.
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

// The floating four-direction d-pad shown only in Sim mode - matches the
// prototype's #sim-controls, which floats over the map (not inside a drawer).
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
