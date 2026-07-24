import { useEffect, useState } from "react";
import { useApp } from "../AppContext";
import ZoneList from "./ZoneList";
import ZoneEditor from "./ZoneEditor";
import { submitAddZoneRequest, submitClearAllLogsRequest } from "../requests";

export default function ZonesDrawer() {
  const {
    sessionName,
    userId,
    isAdmin,
    selectedZoneId,
    selectZone,
    userLocation,
    setStatusText,
  } = useApp();
  const [isOpen, setIsOpen] = useState(false);

  // Selecting a zone (from the list or by tapping its map marker) should
  // reveal the drawer even if it was closed.
  useEffect(() => {
    if (selectedZoneId) setIsOpen(true);
  }, [selectedZoneId]);

  function handleAddZone() {
    submitAddZoneRequest(sessionName, userId, userLocation).catch((error) => setStatusText(error.message));
  }

  function handleClearAllLogs() {
    if (!isAdmin) {
      setStatusText("Read-only mode: clearing logs requires gm password.");
      return;
    }
    submitClearAllLogsRequest(sessionName, userId, userLocation).catch(() =>
      setStatusText("Clear logs request failed. Check Firebase configuration and permissions."),
    );
  }

  return (
    <>
      <button
        className="zone-drawer-toggle"
        type="button"
        aria-expanded={isOpen}
        aria-controls="drawer"
        aria-label="Open zone list"
        onClick={() => setIsOpen((prev) => !prev)}
      >
        Z
      </button>

      <aside id="drawer" className={`drawer${isOpen ? " is-open" : ""}`} aria-label="zones">
        <div className="drawer-header">
          <div>
            <p className="eyebrow">User Session</p>
            <h1>{userId ? `${userId}'s ${sessionName}` : "Session"}</h1>
          </div>
          <div className="drawer-header-actions">
            <button
              className="text-button"
              type="button"
              onClick={() => {
                setIsOpen(false);
                selectZone(null);
              }}
            >
              Close
            </button>
          </div>
        </div>

        <div className="drawer-body">
          <section className="panel-section">
            <div className="editor-header">
              <div className="section-actions">
                <button
                  className="text-button"
                  type="button"
                  aria-label="Add new zone at current location"
                  onClick={handleAddZone}
                >
                  Add zone
                </button>
              </div>
              <button
                className="text-button"
                type="button"
                aria-label="Clear zone logs for all zones"
                onClick={handleClearAllLogs}
              >
                Clear logs
              </button>
            </div>
            <ZoneList />
            <div className="editor-bottom-spacer" aria-hidden="true" />
          </section>
        </div>

        <ZoneEditor />
      </aside>
    </>
  );
}
