import { useEffect, useState } from "react";
import { useApp } from "../AppContext";
import EventList from "./EventList";
import EventEditor from "./EventEditor";
import { submitAddEventRequest } from "../requests";

// Only rendered for admins - mirrors the prototype hiding the events-drawer
// toggle entirely for non-admin users.
export default function EventsDrawer() {
  const { isAdmin, sessionName, userId, userLocation, selectedEventId, setStatusText } = useApp();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (selectedEventId) setIsOpen(true);
  }, [selectedEventId]);

  if (!isAdmin) return null;

  function handleAddEvent() {
    submitAddEventRequest(sessionName, userId, userLocation).catch((error) => setStatusText(error.message));
  }

  return (
    <>
      <button
        className="events-drawer-toggle"
        type="button"
        aria-expanded={isOpen}
        aria-controls="events-drawer"
        aria-label="Open event editor"
        onClick={() => setIsOpen((prev) => !prev)}
      >
        E
      </button>

      <aside id="events-drawer" className={`drawer events-drawer${isOpen ? " is-open" : ""}`} aria-label="Event editor">
        <div className="drawer-header">
          <div>
            <p className="eyebrow">Event System</p>
            <h1>Events</h1>
          </div>
          <div className="drawer-header-actions">
            <button className="text-button" type="button" onClick={() => setIsOpen(false)}>
              Close
            </button>
          </div>
        </div>

        <div className="drawer-body">
          <section className="panel-section">
            <EventList />
          </section>

          <section className="panel-section">
            <EventEditor onAddEvent={handleAddEvent} />
          </section>
        </div>
      </aside>
    </>
  );
}
