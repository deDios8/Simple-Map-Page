import { useEffect, useState } from "react";
import { useApp } from "../AppContext";
import { normalizeStats, parseVisibleList, collectStats, createDefaultStat } from "../zoneUtils";
import { submitEditedZoneRequest, submitDeletedZoneRequest, submitClearLogsRequest } from "../requests";
import StatsEditor from "./StatsEditor";

export default function ZoneEditor() {
  const {
    zones,
    selectedZoneId,
    selectZone,
    isAdmin,
    sessionName,
    userId,
    coordPickMode,
    setCoordPickMode,
    pickedCoordinates,
  } = useApp();

  const selectedFeature = selectedZoneId ? zones[selectedZoneId] : null;

  const [name, setName] = useState("");
  const [fill, setFill] = useState("#ffffff");
  const [border, setBorder] = useState("#ffffff");
  const [radius, setRadius] = useState("");
  const [opacity, setOpacity] = useState("0.5");
  const [visibleTo, setVisibleTo] = useState("");
  const [traits, setTraits] = useState("");
  const [lat, setLat] = useState(null);
  const [lng, setLng] = useState(null);
  const [statsRows, setStatsRows] = useState([]);
  const [saveStatus, setSaveStatus] = useState("");

  // Populate the form when the selected zone changes - but only then. The
  // `zones` snapshot is re-delivered every couple seconds (e.g. any player's
  // GPS ping patches the shared zones node), which would otherwise give
  // `selectedFeature` a new reference on a timer and wipe out any edit the
  // user hasn't saved yet (including a stat row they just removed).
  useEffect(() => {
    if (!selectedFeature) return;
    setName(selectedFeature.properties?.displayName || "");
    setFill(selectedFeature.properties?.appearance?.fill || "#ffffff");
    setBorder(selectedFeature.properties?.appearance?.border || "#ffffff");
    setRadius(
      Number.isFinite(selectedFeature.properties?.appearance?.radius)
        ? String(selectedFeature.properties.appearance.radius)
        : "",
    );
    setOpacity(Number.isFinite(selectedFeature.properties?.appearance?.opacity) ? String(selectedFeature.properties.appearance.opacity) : "");
    setVisibleTo((selectedFeature.properties?.appearance?.visibleTo || []).join(", "));
    setTraits((selectedFeature.properties?.traits || []).join(", "));
    const coordinates = selectedFeature.geometry?.coordinates;
    setLat(Array.isArray(coordinates) ? coordinates[1] : null);
    setLng(Array.isArray(coordinates) ? coordinates[0] : null);
    const stats = normalizeStats(selectedFeature.properties);
    setStatsRows(Object.entries(stats).map(([key, stat]) => ({ key, ...stat })));
  }, [selectedZoneId]);

  // Only clear the save-status message when the selection itself changes -
  // not on every snapshot refresh of the same zone (which would otherwise
  // wipe out a "Save request sent" message the moment the server echoes back).
  useEffect(() => {
    setSaveStatus("");
  }, [selectedZoneId]);

  // Consume a coordinate picked on the map (see MapView's click-to-pick mode).
  useEffect(() => {
    if (!pickedCoordinates || !selectedFeature) return;
    setLat(pickedCoordinates.lat);
    setLng(pickedCoordinates.lng);
  }, [pickedCoordinates]);

  useEffect(() => {
    if (!selectedZoneId && coordPickMode) {
      setCoordPickMode(false);
    }
  }, [selectedZoneId]);

  if (!selectedZoneId || !selectedFeature) {
    return (
      <div className="editor-panel">
        <div className="editor-panel-header">
          <h2>Select a zone to edit.</h2>
        </div>
      </div>
    );
  }

  function addStatRow() {
    setStatsRows((prev) => {
      const usedKeys = new Set(prev.map((row) => row.key));
      let index = prev.length + 1;
      let key = `stat-${index}`;
      while (usedKeys.has(key)) {
        index += 1;
        key = `stat-${index}`;
      }
      return [...prev, { key, ...createDefaultStat() }];
    });
  }

  function removeStatRow(index) {
    setStatsRows((prev) => prev.filter((_, i) => i !== index));
  }

  function updateStatRow(index, field, value) {
    setStatsRows((prev) => prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!isAdmin) {
      setSaveStatus("Read-only mode: editing requires gm password.");
      return;
    }

    const { stats, error } = collectStats(statsRows);
    if (error) {
      setSaveStatus(error);
      return;
    }

    const parsedRadius = Number.parseFloat(radius);
    const nextRadius = Number.isFinite(parsedRadius) ? parsedRadius : null;
    const nextLat = Number.isFinite(lat) ? Math.round(lat * 100000) / 100000 : lat;
    const nextLng = Number.isFinite(lng) ? Math.round(lng * 100000) / 100000 : lng;
    const coordinates = Number.isFinite(nextLng) && Number.isFinite(nextLat) ? [nextLng, nextLat] : null;

    const formData = {
      name: name.trim(),
      fill,
      border,
      opacity,
      visibleTo: parseVisibleList(visibleTo),
      traits: parseVisibleList(traits),
      latitude: String(nextLat ?? ""),
      longitude: String(nextLng ?? ""),
      radius: String(nextRadius ?? ""),
      stats,
    };

    setSaveStatus("Sending edit request...");
    try {
      await submitEditedZoneRequest(sessionName, userId, selectedZoneId, formData, coordinates);
      setSaveStatus("Edit request sent. Server will apply updates shortly.");
    } catch (error) {
      console.error(error);
      setSaveStatus("Edit request failed. Check Firebase configuration and permissions.");
    }
  }

  async function handleDelete() {
    if (!isAdmin) {
      setSaveStatus("Read-only mode: deleting requires gm password.");
      return;
    }
    setSaveStatus("Sending delete request...");
    try {
      await submitDeletedZoneRequest(sessionName, userId, selectedZoneId, selectedFeature.geometry?.coordinates || null);
      setSaveStatus("Delete request sent. Server will remove the zone shortly.");
    } catch (error) {
      console.error(error);
      setSaveStatus("Delete request failed. Check Firebase configuration and permissions.");
    }
  }

  async function handleClearLogs() {
    if (!isAdmin) {
      setSaveStatus("Read-only mode: clearing logs requires gm password.");
      return;
    }
    setSaveStatus("Sending clear logs request...");
    try {
      await submitClearLogsRequest(sessionName, userId, selectedZoneId, selectedFeature.geometry?.coordinates || null);
      setSaveStatus("Clear logs request sent. Server will clear logs shortly.");
    } catch (error) {
      console.error(error);
      setSaveStatus("Clear logs request failed. Check Firebase configuration and permissions.");
    }
  }

  return (
    <div className="editor-panel is-open">
      <div className="editor-panel-header">
        <h2>Editing {name || selectedZoneId}</h2>
        <button className="text-button" type="button" onClick={() => selectZone(null)}>
          Cancel
        </button>
      </div>
      <div className="editor-panel-body">
        <form className="editor-form" onSubmit={handleSubmit}>
          <div className="name-row">
            <label>
              Name
              <input
                type="text"
                placeholder="Object label"
                value={name}
                disabled={!isAdmin}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label>
              Traits
              <input
                type="text"
                placeholder="ZONE, USER, etc."
                value={traits}
                disabled={!isAdmin}
                onChange={(event) => setTraits(event.target.value)}
              />
            </label>
          </div>

          <div className="trait-row">
            <button
              className={`coord-pick-button${coordPickMode ? " is-active" : ""}`}
              type="button"
              disabled={!isAdmin}
              aria-pressed={coordPickMode}
              title="Tap map to set coordinates"
              onClick={() => setCoordPickMode(!coordPickMode)}
            >
            Change Location
              {/* <span>Lat: {Number.isFinite(lat) ? lat : "--"}</span>
              <span>Lng: {Number.isFinite(lng) ? lng : "--"}</span> */}
            </button>
            <label>
              Radius
              <textarea
                rows={1}
                placeholder="5"
                value={radius}
                disabled={!isAdmin}
                onChange={(event) => setRadius(event.target.value)}
              />
            </label>
            <label>
              Visible To
              <input
                type="text"
                placeholder="vision, USER, etc."
                value={visibleTo}
                disabled={!isAdmin}
                onChange={(event) => setVisibleTo(event.target.value)}
              />
            </label>
          </div>

          <div className="appearance-row">
            <label>
              Fill
              <input
                type="color"
                value={fill}
                disabled={!isAdmin}
                onChange={(event) => setFill(event.target.value)}
              />
            </label>
            <label>
              Border
              <input
                type="color"
                value={border}
                disabled={!isAdmin}
                onChange={(event) => setBorder(event.target.value)}
              />
            </label>
            <label>
              Opacity
              <textarea
                rows={1}
                placeholder="0.5"
                value={opacity}
                disabled={!isAdmin}
                onChange={(event) => setOpacity(event.target.value)}
              />
            </label>
          </div>

          <StatsEditor
            rows={statsRows}
            disabled={!isAdmin}
            onAdd={addStatRow}
            onRemove={removeStatRow}
            onChange={updateStatRow}
          />

          <div className="editor-actions">
            <div className="editor-action-buttons">
              <button className="primary-button" type="submit" disabled={!isAdmin}>
                Save changes
              </button>
              <button className="text-button" type="button" disabled={!isAdmin} onClick={handleClearLogs}>
                Clear logs
              </button>
              <button className="danger-button" type="button" disabled={!isAdmin} onClick={handleDelete}>
                Delete
              </button>
            </div>
            <p className="save-status" aria-live="polite">
              {saveStatus}
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
