import { useApp } from "../AppContext";
import { isVisibleToCurrentUser } from "../zoneUtils";

export default function ZoneList({ onAdd }) {
  const { zones, userPass, userId, selectedZoneId, selectZone } = useApp();
  const visibleFeatures = Object.values(zones).filter((feature) =>
    isVisibleToCurrentUser(feature, { userPass, userId, zones }),
  );

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
