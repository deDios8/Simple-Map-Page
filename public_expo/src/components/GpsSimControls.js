import { useApp } from "../AppContext";

// Bottom-left cluster: the sim d-pad (only shown in Sim mode) plus the
// GPS/Sim toggle button, sharing one grid so the toggle always has a spot
// in the layout even when the d-pad arrows are hidden.
export function SimControls() {
  const { gpsMode, toggleGpsMode, moveSimulatedLocation } = useApp();
  const STEP = 0.00003;

  return (
    <div className="sim-controls">
      {!gpsMode && (
        <>
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
        </>
      )}
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
    </div>
  );
}
