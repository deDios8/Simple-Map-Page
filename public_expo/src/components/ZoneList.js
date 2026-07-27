import { useApp } from "../AppContext";
import { isVisibleToCurrentUser } from "../zoneUtils";
import { submitAddZoneRequest } from "../requests";

export default function ZoneList({ onAdd }) {
  const { zones, userPass, userId, selectedZoneId, selectZone, sessionName, userLocation, setStatusText } = useApp();
  const visibleFeatures = Object.values(zones).filter((feature) =>
    isVisibleToCurrentUser(feature, { userPass, userId, zones }),
  );

  function duplicateZone(feature) {
    const formData = {
      name: feature.properties?.displayName || "",
      fill: feature.properties?.appearance?.fill || "#ffffff",
      border: feature.properties?.appearance?.border || "#ffffff",
      opacity: String(feature.properties?.appearance?.opacity ?? "0.5"),
      visibleTo: feature.properties?.appearance?.visibleTo || [],
      traits: feature.properties?.traits || [],
      latitude: String(feature.geometry?.coordinates?.[1] ?? ""),
      longitude: String(feature.geometry?.coordinates?.[0] ?? ""),
      radius: String(feature.properties?.appearance?.radius ?? "5"),
      stats: feature.properties?.stats || {},
    };
    submitAddZoneRequest(sessionName, userId, userLocation, formData).catch((error) => setStatusText(error.message));
  }

  if (!visibleFeatures.length) {
    return (
      <ul className="zone-list">
        <li>No zones found.</li>
        <li>
          <button className="is-add" type="button" onClick={onAdd} aria-label="Add new zone at current location">
            Add zone
          </button>
        </li>
      </ul>
    );
  }

  return (
    <ul className="zone-list">
      {visibleFeatures.map((feature) => {
        const id = feature.properties?.id;
        const fill = feature.properties?.appearance?.fill || "#ffffff";
        const name = feature.properties?.displayName || id || "Unnamed zone";
        return (
          <li key={id}>
            <button
              className={selectedZoneId === id ? "is-selected" : ""}
              type="button"
              onClick={() => selectZone(id)}
            >
              <span className="list-color-dot" style={{ background: fill }} />
              <span>{name}</span>
            </button>
            <button
              className="zone-list-duplicate-button"
              type="button"
              aria-label="Duplicate zone"
              onClick={() => duplicateZone(feature)}
            >
              ⧉
            </button>
          </li>
        );
      })}
      <li>
        <button className="is-add" type="button" onClick={onAdd} aria-label="Add new zone at current location">
          Add zone
        </button>
      </li>
    </ul>
  );
}
