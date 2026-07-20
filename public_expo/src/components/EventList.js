import { useApp } from "../AppContext";

export default function EventList() {
  const { events, selectedEventId, selectEvent } = useApp();
  const entries = Object.values(events);

  if (!entries.length) {
    return (
      <ul className="zone-list">
        <li>No events found.</li>
      </ul>
    );
  }

  return (
    <ul className="zone-list">
      {entries.map((entry) => {
        const id = entry.properties?.id;
        const name = entry.properties?.displayName || id || "Unnamed event";
        return (
          <li key={id}>
            <button
              className={selectedEventId === id ? "is-selected" : ""}
              type="button"
              onClick={() => selectEvent(id)}
            >
              <span>{name}</span>
              <span className="list-meta"> &middot; {id}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
