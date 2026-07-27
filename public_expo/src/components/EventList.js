import { useApp } from "../AppContext";
import { submitAddEventRequest } from "../requests";

export default function EventList({ onAdd }) {
  const { events, selectedEventId, selectEvent, sessionName, userId, userLocation, setStatusText } = useApp();
  const entries = Object.values(events);

  function duplicateEvent(entry) {
    const formData = {
      name: entry.properties?.displayName || "",
      triggerComponents: entry.properties?.Triggers || {},
      targetComponents: entry.properties?.Targets || {},
      results: entry.properties?.Results || {},
    };
    submitAddEventRequest(sessionName, userId, userLocation, formData).catch((error) => setStatusText(error.message));
  }

  if (!entries.length) {
    return (
      <ul className="zone-list">
        <li>No events found.</li>
        <li>
          <button className="is-add" type="button" onClick={onAdd} aria-label="Add new event">
            Add event
          </button>
        </li>
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
            <button
              className="zone-list-duplicate-button"
              type="button"
              aria-label="Duplicate event"
              onClick={() => duplicateEvent(entry)}
            >
              ⧉
            </button>
          </li>
        );
      })}
      <li>
        <button className="is-add" type="button" onClick={onAdd} aria-label="Add new event">
          Add event
        </button>
      </li>
    </ul>
  );
}
