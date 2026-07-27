import { useApp } from "../AppContext";

// The satellite/street map toggle button - floats directly above the GPS/Sim
// toggle button.
export function MapLayerToggleButton() {
  const { satelliteView, toggleMapLayer } = useApp();
  return (
    <button
      className="map-layer-toggle"
      type="button"
      aria-label="Toggle satellite/street map"
      title="Toggle between satellite and street map"
      data-mode={satelliteView ? "satellite" : "street"}
      onClick={toggleMapLayer}
    >
      {satelliteView ? "Sat" : "Map"}
    </button>
  );
}
