export default function ZoneList({ zones, selectedId, onSelect }) {
  const zoneEntries = Object.entries(zones || {});

  if (zoneEntries.length === 0) {
    return (
      <div className="zone-list-empty">
        No zones yet. Click "Add zone" to create one.
      </div>
    );
  }

  return (
    <ul id="zone-list" className="zone-list">
      {zoneEntries.map(([id, zone]) => {
        const isSelected = id === selectedId;
        const name = zone.name || id;
        const color = zone.color || '#0b8f87';

        return (
          <li
            key={id}
            className={`zone-list-item ${isSelected ? 'is-selected' : ''}`}
            onClick={() => onSelect(id)}
          >
            <div
              className="zone-color-indicator"
              style={{ backgroundColor: color }}
            />
            <span className="zone-name">{name}</span>
          </li>
        );
      })}
    </ul>
  );
}
