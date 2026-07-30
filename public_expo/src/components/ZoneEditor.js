import { useEffect, useRef, useState } from "react";
import { useApp } from "../AppContext";
import { normalizeStats, parseVisibleList, parseDashArray, collectStats, createDefaultStat } from "../zoneUtils";
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

  // Builds a stable, order-independent snapshot string for isDirty comparison
  // - JSON.stringify preserves key insertion order, so the three call sites
  // below (load, isDirty, and post-save reset) must always list fields in
  // this exact order or the comparison silently breaks.
  function formSnapshot(values) {
    return JSON.stringify({
      name: values.name,
      traits: values.traits,
      visibleTo: values.visibleTo,
      radius: values.radius,
      fill: values.fill,
      opacity: values.opacity,
      border: values.border,
      dashArray: values.dashArray,
      lat: values.lat,
      lng: values.lng,
      statsRows: values.statsRows,
    });
  }

  const [name, setName] = useState("");
  const [traits, setTraits] = useState("");
  const [visibleTo, setVisibleTo] = useState("");
  const [radius, setRadius] = useState("");
  const [fill, setFill] = useState("#ffffff");
  const [opacity, setOpacity] = useState("0.5");
  const [border, setBorder] = useState("#ffffff");
  const [dashArray, setDashArray] = useState("1, 0");
  const [lat, setLat] = useState(null);
  const [lng, setLng] = useState(null);
  const [statsRows, setStatsRows] = useState([]);
  const [saveStatus, setSaveStatus] = useState("");

  // Snapshot of the form's values right after loading a zone, used to tell
  // whether the user has changed anything yet (see isDirty below).
  const initialFormRef = useRef("");

  // Populate the form when the selected zone changes - but only then. The
  // `zones` snapshot is re-delivered every couple seconds (e.g. any player's
  // GPS ping patches the shared zones node), which would otherwise give
  // `selectedFeature` a new reference on a timer and wipe out any edit the
  // user hasn't saved yet (including a stat row they just removed).
  useEffect(() => {
    if (!selectedFeature) return;
    const nextName = selectedFeature.properties?.displayName || "";
    const nextFill = selectedFeature.properties?.appearance?.fill || "#ffffff";
    const nextBorder = selectedFeature.properties?.appearance?.border || "#ffffff";
    const rawDashArray = selectedFeature.properties?.appearance?.dash;
    const nextDashArray = Array.isArray(rawDashArray) ? rawDashArray.join(", ") : rawDashArray || "1, 0";
    const nextRadius = Number.isFinite(selectedFeature.properties?.appearance?.radius)
      ? String(selectedFeature.properties.appearance.radius)
      : "";
    const nextOpacity = Number.isFinite(selectedFeature.properties?.appearance?.opacity)
      ? String(selectedFeature.properties.appearance.opacity)
      : "";
    const nextVisibleTo = (selectedFeature.properties?.appearance?.visibleTo || []).join(", ");
    const nextTraits = (selectedFeature.properties?.traits || []).join(", ");
    const coordinates = selectedFeature.geometry?.coordinates;
    const nextLat = Array.isArray(coordinates) ? coordinates[1] : null;
    const nextLng = Array.isArray(coordinates) ? coordinates[0] : null;
    const stats = normalizeStats(selectedFeature.properties);
    const nextStatsRows = Object.entries(stats).map(([key, stat]) => ({ key, ...stat }));

    setName(nextName);
    setTraits(nextTraits);
    setVisibleTo(nextVisibleTo);
    setRadius(nextRadius);
    setFill(nextFill);
    setOpacity(nextOpacity);
    setBorder(nextBorder);
    setDashArray(nextDashArray);
    setLat(nextLat);
    setLng(nextLng);
    setStatsRows(nextStatsRows);

    initialFormRef.current = formSnapshot({
      name: nextName,
      fill: nextFill,
      border: nextBorder,
      dashArray: nextDashArray,
      radius: nextRadius,
      opacity: nextOpacity,
      visibleTo: nextVisibleTo,
      traits: nextTraits,
      lat: nextLat,
      lng: nextLng,
      statsRows: nextStatsRows,
    });
  }, [selectedZoneId]);

  // True once anything in the form differs from what it loaded with - drives
  // the Save button's styling (see the render below).
  const isDirty =
    initialFormRef.current !==
    formSnapshot({ name, fill, border, dashArray, radius, opacity, visibleTo, traits, lat, lng, statsRows });

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

  function duplicateStatRow(index) {
    setStatsRows((prev) => {
      const usedKeys = new Set(prev.map((row) => row.key));
      let nextIndex = prev.length + 1;
      let key = `stat-${nextIndex}`;
      while (usedKeys.has(key)) {
        nextIndex += 1;
        key = `stat-${nextIndex}`;
      }
      return [...prev, { ...prev[index], key }];
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
    const parsedDashArray = parseDashArray(dashArray);

    const formData = {
      name: name.trim(),
      traits: parseVisibleList(traits),
      radius: String(nextRadius ?? ""),
      visibleTo: parseVisibleList(visibleTo),
      fill,
      opacity,
      border,
      dash: parsedDashArray.length ? parsedDashArray : [1, 0],
      latitude: String(nextLat ?? ""),
      longitude: String(nextLng ?? ""),
      stats,
    };

    setSaveStatus("Sending edit request...");
    try {
      await submitEditedZoneRequest(sessionName, userId, selectedZoneId, formData, coordinates);
      // The zones snapshot refreshes on a timer independent of this save (see
      // the load effect above), so isDirty would never clear on its own -
      // reset the snapshot here instead of waiting for the server to echo back.
      initialFormRef.current = formSnapshot({
        name,
        traits,
        visibleTo,
        radius,
        fill,
        opacity,
        border,
        dashArray,
        lat,
        lng,
        statsRows,
      });
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
        <label>
          <input
            type="text"
            placeholder="Zone Name"
            value={name}
            disabled={!isAdmin}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <div className="editor-panel-header-actions">
          <div className="editor-panel-header-buttons">
            <button
              className={isDirty ? "primary-button is-unsaved" : "primary-button disabled"}
              type="submit"
              form="zone-editor-form"
              disabled={!isAdmin}
            >
              Save
            </button>
            <button className="danger-button" type="button" disabled={!isAdmin} onClick={handleDelete}>
              Delete
            </button>
            <button className="text-button" type="button" onClick={() => selectZone(null)}>
              Cancel
            </button>
          </div>
          <p className="save-status" aria-live="polite">
            {saveStatus}
          </p>
        </div>
      </div>
      <div className="editor-panel-body">
        <form id="zone-editor-form" className="editor-form" onSubmit={handleSubmit}>
          <div className="traits-row">
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

          <div className="radius-row">
            <label>
              Radius
              <input
                type="text"
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
              Opacity
              <input
                type="text"
                placeholder="0.5"
                value={opacity}
                disabled={!isAdmin}
                onChange={(event) => setOpacity(event.target.value)}
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
              Dash
              <input
                type="text"
                placeholder="1, 0"
                value={dashArray}
                disabled={!isAdmin}
                onChange={(event) => setDashArray(event.target.value)}
              />
            </label>
          </div>

          <StatsEditor
            rows={statsRows}
            disabled={!isAdmin}
            onAdd={addStatRow}
            onDuplicate={duplicateStatRow}
            onRemove={removeStatRow}
            onChange={updateStatRow}
          />

          <div className="editor-action-buttons justify-end">
            <button className="text-button" type="button" disabled={!isAdmin} onClick={handleClearLogs}>
              Clear logs
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
