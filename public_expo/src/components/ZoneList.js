import { useApp } from "../AppContext";
import { isVisibleToCurrentUser } from "../zoneUtils";

export default function ZoneList() {
  const { zones, userPass, userId, selectedZoneId, selectZone } = useApp();
  const visibleFeatures = Object.values(zones).filter((feature) =>
    isVisibleToCurrentUser(feature, { userPass, userId, zones }),
  );

  if (!visibleFeatures.length) {
    return (
      <ul className="zone-list">
        <li>No zones found.</li>
      </ul>
    );
  }

  return (
    <ul className="zone-list">
      {visibleFeatures.map((feature) => {
        const id = feature.properties?.id;
        const color = feature.properties?.appearance?.color || "#0b8f87";
        const name = feature.properties?.displayName || id || "Unnamed zone";
        return (
          <li key={id}>
            <button
              className={selectedZoneId === id ? "is-selected" : ""}
              type="button"
              onClick={() => selectZone(id)}
            >
              <span className="list-color-dot" style={{ background: color }} />
              <span>{name}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
