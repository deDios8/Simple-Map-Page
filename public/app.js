import {
  initializeApp,
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js";
import {
  getDatabase,
  onValue,
  ref,
  update,
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-database.js";

const firebaseConfig = {
  apiKey: "AIzaSyC6CGFSfXNnpRwM2TxlTK9imx4wMb9S5Fw",
  authDomain: "geogm-simple-map.firebaseapp.com",
  databaseURL: "https://geogm-simple-map-default-rtdb.firebaseio.com",
  projectId: "geogm-simple-map",
  storageBucket: "geogm-simple-map.firebasestorage.app",
  messagingSenderId: "554186481304",
  appId: "1:554186481304:web:35df4f22e9539a991b3aed"
};

const firebaseCollectionNode = "geoObjects";
const firebaseClientRequestNode = "clientRequests";

const demoGeoObjects = {
  downtown: {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [-101.31304, 48.21224],
    },
    properties: {
      id: "downtown",
      metaData: {
        name: "Downtown Pin",
        description: "Current point of interest.",
        type: "pin",
      },
      appearance: {
        color: "#0b8f87",
        visible: true,
        radius: 5,
      },
      data: {
        category: "pin",
        priority: "high",
      },
    },
  },
  hiddenMarker: {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [-101.31304, 48.21224],
    },
    properties: {
      id: "hiddenMarker",
      metaData: {
        name: "Hidden Marker",
        description: "This stays hidden until visibility is enabled.",
        type: "",
      },
      appearance: {
        color: "#5e718c",
        visible: false,
        radius: 5,
      },
      data: {
        category: "standby",
      },
    },
  },
  stagingZone: {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [[
        [-101.319, 48.217],
        [-101.307, 48.217],
        [-101.307, 48.209],
        [-101.319, 48.209],
        [-101.319, 48.217],
      ]],
    },
    properties: {
      id: "stagingZone",
      metaData: {
        name: "Staging Zone",
        description: "Rectangular work area.",
        type: "zone",
      },
      appearance: {
        color: "#d2603f",
        visible: true,
      },
      data: {
        access: "restricted",
        supervisor: "Ops A",
      },
    },
  },
};

const state = {
  version: "0.1.026",
  updateFrequency: 2000,
  // mapLayer: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  // mapLayerAttribution: "&copy; OpenStreetMap contributors",
  mapLayer: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  mapLayerAttribution: "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
  map: null,
  userMarker: null,
  geoJsonLayer: null,
  database: null,
  firebaseReady: false,
  objects: {},
  selectedId: null,
  userLocation: null,
  userId: null,
  userPass: null,
  sessionName: "testBed",
  trackingInterval: null,
  listenerActive: true,
  listenerUnsubscribe: null,
  pendingUserSetup: false,
  coordPickMode: false,
};

const locationStatus = document.querySelector("#location-status");
const drawer = document.querySelector("#drawer");
const drawerTitle = document.querySelector("#drawer-session-title");
const drawerToggle = document.querySelector("#drawer-toggle");
const drawerClose = document.querySelector("#drawer-close");
const listenerToggle = document.querySelector("#listener-toggle");
const requestAButton = document.querySelector("#request-a-button");
const requestBButton = document.querySelector("#request-b-button");
const requestXButton = document.querySelector("#request-x-button");
const requestYButton = document.querySelector("#request-y-button");
const addObjectButton = document.querySelector("#add-object-button");
const objectList = document.querySelector("#object-list");
const editorForm = document.querySelector("#editor-form");
const editorEmptyState = document.querySelector("#editor-empty-state");
const saveStatus = document.querySelector("#save-status");
const deleteObjectButton = document.querySelector("#delete-object-button");
const fieldName = document.querySelector("#field-name");
const fieldType = document.querySelector("#field-type");
const fieldColor = document.querySelector("#field-color");
const fieldVisible = document.querySelector("#field-visible");
const fieldLatitude = document.querySelector("#field-latitude");
const fieldLongitude = document.querySelector("#field-longitude");
const coordPickButton = document.querySelector("#coord-pick-button");
const fieldRadius = document.querySelector("#field-radius");
const fieldDescription = document.querySelector("#field-description");
const statsList = document.querySelector("#stats-list");
const addStatButton = document.querySelector("#add-stat-button");
const statusesList = document.querySelector("#statuses-list");
const addStatusButton = document.querySelector("#add-status-button");
const editorFormToggle = document.querySelector("#editor-form-toggle");
const statsSectionToggle = document.querySelector("#stats-section-toggle");
const statusesSectionToggle = document.querySelector("#statuses-section-toggle");
const statsSection = document.querySelector(".stats-section");
const statusesSection = document.querySelector(".statuses-section");
const fieldExtra = document.querySelector("#field-extra");
const versionInfo = document.querySelector("#version-info");
const editableFields = [
  fieldName,
  fieldType,
  fieldColor,
  fieldVisible,
  fieldLatitude,
  fieldLongitude,
  fieldRadius,
  fieldDescription,
  fieldExtra,
];

const editorCollapseState = {
  form: true,
  stats: true,
  statuses: true,
};

// Persist collapse state to localStorage
function saveCollapseState() {
  localStorage.setItem("editorCollapseState", JSON.stringify(editorCollapseState));
}

// Restore collapse state from localStorage
function loadCollapseState() {
  const savedState = localStorage.getItem("editorCollapseState");
  if (savedState) {
    try {
      const parsedState = JSON.parse(savedState);
      if (typeof parsedState === "object") {
        Object.assign(editorCollapseState, parsedState);
      }
    } catch (e) {
      console.error("Failed to parse collapse state from localStorage", e);
    }
  }
}

// Apply collapse state on page load
function applyCollapseState() {
  setEditorFormCollapsed(editorCollapseState.form);
  setStatsSectionCollapsed(editorCollapseState.stats);
  setStatusesSectionCollapsed(editorCollapseState.statuses);
}

function setEditorFormCollapsed(isCollapsed) {
  editorCollapseState.form = Boolean(isCollapsed);
  editorForm.classList.toggle("is-collapsed", editorCollapseState.form);
  if (editorFormToggle) {
    editorFormToggle.textContent = editorCollapseState.form ? "Expand editor" : "Collapse editor";
    editorFormToggle.setAttribute("aria-expanded", String(!editorCollapseState.form));
  }
  saveCollapseState();
}

function setStatsSectionCollapsed(isCollapsed) {
  editorCollapseState.stats = Boolean(isCollapsed);
  statsSection?.classList.toggle("is-collapsed", editorCollapseState.stats);
  if (statsSectionToggle) {
    statsSectionToggle.textContent = editorCollapseState.stats ? "Expand" : "Collapse";
    statsSectionToggle.setAttribute("aria-expanded", String(!editorCollapseState.stats));
  }
  saveCollapseState();
}

function setStatusesSectionCollapsed(isCollapsed) {
  editorCollapseState.statuses = Boolean(isCollapsed);
  statusesSection?.classList.toggle("is-collapsed", editorCollapseState.statuses);
  if (statusesSectionToggle) {
    statusesSectionToggle.textContent = editorCollapseState.statuses ? "Expand" : "Collapse";
    statusesSectionToggle.setAttribute("aria-expanded", String(!editorCollapseState.statuses));
  }
  saveCollapseState();
}

function nameToKey(name) {
  return String(name).trim().toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_-]/g, "");
}

function createDefaultStat() {
  return {
    key: "",
    name: "",
    type: "",
    value: 0,
    max_value: 100,
    min_value: 0,
  };
}

function createDefaultStatus() {
  return {
    key: "",
    name: "",
    type: "",
    strength: 0,
    time_until_expire: 5,
  };
}

function normalizeStats(properties) {
  const rawStats = properties?.stats;
  if (rawStats && typeof rawStats === "object" && !Array.isArray(rawStats)) {
    const nextStats = {};
    for (const [key, rawStat] of Object.entries(rawStats)) {
      if (!rawStat || typeof rawStat !== "object" || Array.isArray(rawStat)) {
        continue;
      }
      const statKey = String(key || rawStat.name || "").trim();
      if (!statKey) {
        continue;
      }
      nextStats[statKey] = {
        name: String(rawStat.name || ""),
        type: String(rawStat.type || ""),
        value: Number.isFinite(rawStat.value) ? rawStat.value : 0,
        max_value: Number.isFinite(rawStat.max_value) ? rawStat.max_value : 100,
        min_value: Number.isFinite(rawStat.min_value) ? rawStat.min_value : 0,
      };
    }
    if (Object.keys(nextStats).length > 0) {
      return nextStats;
    }
  }

  return {};
}

function normalizeStatuses(properties) {
  const rawStatuses = properties?.statuses;
  if (rawStatuses && typeof rawStatuses === "object" && !Array.isArray(rawStatuses)) {
    const nextStatuses = {};
    for (const [key, rawStatus] of Object.entries(rawStatuses)) {
      if (!rawStatus || typeof rawStatus !== "object" || Array.isArray(rawStatus)) {
        continue;
      }
      const statusKey = String(key || rawStatus.name || "").trim();
      if (!statusKey) {
        continue;
      }
      nextStatuses[statusKey] = {
        name: String(rawStatus.name || ""),
        type: String(rawStatus.type || ""),
        strength: Number.isFinite(rawStatus.strength) ? rawStatus.strength : 0,
        time_until_expire: Number.isFinite(rawStatus.time_until_expire) ? rawStatus.time_until_expire : 5,
      };
    }
    if (Object.keys(nextStatuses).length > 0) {
      return nextStatuses;
    }
  }

  return {};
}

function renderStatsEditor(stats) {
  if (!statsList) {
    return;
  }

  const entries = Object.entries(stats || {});
  if (!entries.length) {
    statsList.innerHTML = '<div class="stats-empty">No stats yet. Add one to track custom values.</div>';
    return;
  }

  statsList.innerHTML = entries
    .map(([key, stat], index) => {
      const safeStat = stat && typeof stat === "object" ? stat : createDefaultStat();
      const statMin = Number.isFinite(safeStat.min_value) ? safeStat.min_value : 0;
      const statMax = Number.isFinite(safeStat.max_value) ? safeStat.max_value : 100;
      const statValue = Number.isFinite(safeStat.value) ? safeStat.value : 0;
      const rowLabel = index === 0 ? "Primary stat" : `Stat ${index + 1}`;

      return `
        <article class="stat-row" data-stat-index="${index}" data-key="${escapeHtml(String(key || ""))}" data-min="${statMin}" data-max="${statMax}">
          <div class="stat-row-grid">
            <label>
              Name
              <input type="text" data-field="name" value="${escapeHtml(String(safeStat.name || ""))}" placeholder="Health" />
            </label>
            <label>
              Type
              <input type="text" data-field="type" value="${escapeHtml(String(safeStat.type || ""))}" placeholder="resource" />
            </label>
            <label>
              Value
              <input type="number" step="any" data-field="value" value="${escapeHtml(String(statValue))}" title="Valid range: ${statMin} to ${statMax}" />
            </label>
            <button class="stat-remove-button" type="button" data-action="remove-stat" aria-label="Remove stat">✕</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function addEmptyStatRow() {
  const currentStats = collectStatsFromEditor({ allowEmpty: true }).stats;
  const nextStats = { ...currentStats };
  let index = Object.keys(nextStats).length + 1;
  let nextKey = `stat-${index}`;
  while (Object.prototype.hasOwnProperty.call(nextStats, nextKey)) {
    index += 1;
    nextKey = `stat-${index}`;
  }
  nextStats[nextKey] = createDefaultStat();
  renderStatsEditor(nextStats);
  applyEditorPermissions();
}

function renderStatusesEditor(statuses) {
  if (!statusesList) {
    return;
  }

  const entries = Object.entries(statuses || {});
  if (!entries.length) {
    statusesList.innerHTML = '<div class="statuses-empty">No statuses yet. Add one to track temporary effects.</div>';
    return;
  }

  statusesList.innerHTML = entries
    .map(([key, status], index) => {
      const safeStatus = status && typeof status === "object" ? status : createDefaultStatus();
      const strength = Number.isFinite(safeStatus.strength) ? safeStatus.strength : 0;
      const timeUntilExpire = Number.isFinite(safeStatus.time_until_expire) ? safeStatus.time_until_expire : 5;
      const rowLabel = index === 0 ? "Primary status" : `Status ${index + 1}`;

      return `
        <article class="status-row" data-status-index="${index}" data-key="${escapeHtml(String(key || ""))}" data-time-until-expire="${timeUntilExpire}">
          <div class="status-row-grid">
            <label>
              Name
              <input type="text" data-field="name" value="${escapeHtml(String(safeStatus.name || ""))}" placeholder="Burning" />
            </label>
            <label>
              Type
              <input type="text" data-field="type" value="${escapeHtml(String(safeStatus.type || ""))}" placeholder="debuff" />
            </label>
            <label>
              Strength
              <input type="number" step="any" data-field="strength" value="${escapeHtml(String(strength))}" />
            </label>
            <button class="status-remove-button" type="button" data-action="remove-status" aria-label="Remove status">✕</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function addEmptyStatusRow() {
  const currentStatuses = collectStatusesFromEditor({ allowEmpty: true }).statuses;
  const nextStatuses = { ...currentStatuses };
  let index = Object.keys(nextStatuses).length + 1;
  let nextKey = `status-${index}`;
  while (Object.prototype.hasOwnProperty.call(nextStatuses, nextKey)) {
    index += 1;
    nextKey = `status-${index}`;
  }
  nextStatuses[nextKey] = createDefaultStatus();
  renderStatusesEditor(nextStatuses);
  applyEditorPermissions();
}

function collectStatusesFromEditor(options = {}) {
  const allowEmpty = Boolean(options.allowEmpty);
  const rows = Array.from(statusesList?.querySelectorAll(".status-row") || []);
  const statuses = {};
  let primaryStatus = null;

  for (const [index, row] of rows.entries()) {
    const getValue = (field) => row.querySelector(`[data-field="${field}"]`)?.value ?? "";
    const originalKey = row.getAttribute("data-key") || "";
    const name = getValue("name").trim();
    const type = getValue("type").trim();
    const rawStrength = Number.parseFloat(getValue("strength").trim());
    const rawTimeUntilExpire = Number.parseFloat(row.getAttribute("data-time-until-expire") ?? "");

    if (!name && !type && !getValue("strength").trim()) {
      continue;
    }

    const nextKey = nameToKey(name) || originalKey || `status-${index + 1}`;
    if (Object.prototype.hasOwnProperty.call(statuses, nextKey)) {
      return {
        statuses: {},
        primaryStatus: null,
        error: `Duplicate status key: ${nextKey}`,
      };
    }

    const nextStatus = {
      name,
      type,
      strength: Number.isFinite(rawStrength) ? rawStrength : 0,
      time_until_expire: Number.isFinite(rawTimeUntilExpire) ? rawTimeUntilExpire : 5,
    };
    statuses[nextKey] = nextStatus;
    if (primaryStatus === null) {
      primaryStatus = { key: nextKey, status: nextStatus };
    }
  }



  if (!allowEmpty && rows.length > 0 && !Object.keys(statuses).length) {
    return {
      statuses: {},
      primaryStatus,
      error: null,
    };
  }

  return {
    statuses,
    primaryStatus,
    error: null,
  };
}

function collectStatsFromEditor(options = {}) {
  const allowEmpty = Boolean(options.allowEmpty);
  const rows = Array.from(statsList?.querySelectorAll(".stat-row") || []);
  const stats = {};
  let primaryStat = null;

  for (const [index, row] of rows.entries()) {
    const getValue = (field) => row.querySelector(`[data-field="${field}"]`)?.value ?? "";
    const originalKey = row.getAttribute("data-key") || "";
    const name = getValue("name").trim();
    const type = getValue("type").trim();
    const rawValue = Number.parseFloat(getValue("value").trim());
    const rawMin = Number.parseFloat(row.getAttribute("data-min") ?? "");
    const rawMax = Number.parseFloat(row.getAttribute("data-max") ?? "");

    if (!name && !type && !getValue("value").trim()) {
      continue;
    }

    const minValue = Number.isFinite(rawMin) ? rawMin : 0;
    const maxValue = Number.isFinite(rawMax) ? rawMax : 100;
    if (maxValue < minValue) {
      return {
        stats: {},
        primaryStat: null,
        error: `Stat ${index + 1}: max must be greater than or equal to min.`,
      };
    }

    const value = Number.isFinite(rawValue) ? rawValue : 0;
    const nextKey = nameToKey(name) || originalKey || `stat-${index + 1}`;
    if (Object.prototype.hasOwnProperty.call(stats, nextKey)) {
      return {
        stats: {},
        primaryStat: null,
        error: `Duplicate stat key: ${nextKey}`,
      };
    }

    const nextStat = {
      name,
      type,
      value: Math.min(maxValue, Math.max(minValue, value)),
      max_value: maxValue,
      min_value: minValue,
    };
    stats[nextKey] = nextStat;
    if (primaryStat === null) {
      primaryStat = { key: nextKey, stat: nextStat };
    }
  }

  if (!primaryStat) {
    primaryStat = { key: "", stat: createDefaultStat() };
  }

  if (!allowEmpty && rows.length > 0 && !Object.keys(stats).length) {
    return {
      stats: {},
      primaryStat,
      error: null,
    };
  }

  return {
    stats,
    primaryStat,
    error: null,
  };
}

init();

function init() {
  renderVersionInfo();
  loadCollapseState();
  applyCollapseState();
  initMap();
  bindUi();
  locateUser();
  initFirebaseListener();
  promptUserId();
}

function renderVersionInfo() {
  if (versionInfo) {
    versionInfo.textContent = `Version: ${state.version}`;
  }
}

function setCoordPickMode(active) {
  state.coordPickMode = Boolean(active);
  coordPickButton?.classList.toggle("is-active", state.coordPickMode);
  const mapEl = document.querySelector("#map");
  mapEl?.classList.toggle("is-coord-picking", state.coordPickMode);
  if (coordPickButton) {
    coordPickButton.setAttribute("aria-pressed", String(state.coordPickMode));
  }
}

function initMap() {
  state.map = L.map("map", {
    zoomControl: false,
    tap: true,
  }).setView([48.21224, -101.31304], 14);

  L.control.zoom({ position: "topright" }).addTo(state.map);

  state.map.on("click", (event) => {
    if (!state.coordPickMode) {
      return;
    }
    const { lat, lng } = event.latlng;
    if (fieldLatitude) {
      fieldLatitude.value = String(Math.round(lat * 100000) / 100000);
    }
    if (fieldLongitude) {
      fieldLongitude.value = String(Math.round(lng * 100000) / 100000);
    }
    setCoordPickMode(false);
  });


  L.tileLayer(state.mapLayer, {
    attribution: state.mapLayerAttribution,
    maxZoom: 19,
    minZoom: 12,
  }).addTo(state.map);
}

function bindUi() {
  drawerToggle.addEventListener("click", () => setDrawerOpen(!drawer.classList.contains("is-open")));
  drawerClose.addEventListener("click", () => setDrawerOpen(false));
  listenerToggle.addEventListener("click", toggleListener);
  requestAButton.addEventListener("click", () => {
    void submitRequest({ requestId: "request A", requestType: "button_click", successMessage: "request A sent" });
  });
  requestBButton.addEventListener("click", () => {
    void submitRequest({ requestId: "request B", requestType: "button_click", successMessage: "request B sent" });
  });
  requestXButton.addEventListener("click", () => {
    void submitRequest({ requestId: "request X", requestType: "button_click", successMessage: "request X sent" });
  });
  requestYButton.addEventListener("click", () => {
    void submitRequest({ requestId: "request Y", requestType: "button_click", successMessage: "request Y sent" });
  });
  addObjectButton?.addEventListener("click", () => {
    void submitRequest({ requestId: "add object", requestType: "button_click", successMessage: "add object sent" });
  });
  addStatButton?.addEventListener("click", () => {
    addEmptyStatRow();
  });
  addStatusButton?.addEventListener("click", () => {
    addEmptyStatusRow();
  });
  coordPickButton?.addEventListener("click", () => {
    setCoordPickMode(!state.coordPickMode);
  });

  editorFormToggle?.addEventListener("click", () => {
    setEditorFormCollapsed(!editorCollapseState.form);
  });
  statsSectionToggle?.addEventListener("click", () => {
    setStatsSectionCollapsed(!editorCollapseState.stats);
  });
  statusesSectionToggle?.addEventListener("click", () => {
    setStatusesSectionCollapsed(!editorCollapseState.statuses);
  });
  statsList?.addEventListener("click", (event) => {
    const button = event.target.closest('button[data-action="remove-stat"]');
    if (!button) {
      return;
    }
    button.closest(".stat-row")?.remove();
    if (!statsList.querySelector(".stat-row")) {
      renderStatsEditor({});
    }
    applyEditorPermissions();
  });
  statusesList?.addEventListener("click", (event) => {
    const button = event.target.closest('button[data-action="remove-status"]');
    if (!button) {
      return;
    }
    button.closest(".status-row")?.remove();
    if (!statusesList.querySelector(".status-row")) {
      renderStatusesEditor({});
    }
    applyEditorPermissions();
  });

  objectList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-id]");
    if (!button) {
      return;
    }

    selectObject(button.dataset.id, { flyTo: true });
  });

  editorForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!canEditObjects()) {
      saveStatus.textContent = "Read-only mode: editing requires gm password.";
      return;
    }

    if (!state.selectedId) {
      return;
    }

    const objectEntry = state.objects[state.selectedId];
    if (!objectEntry) {
      return;
    }

    let parsedExtra = {};

    try {
      parsedExtra = fieldExtra.value.trim() ? JSON.parse(fieldExtra.value) : {};
    } catch {
      saveStatus.textContent = "Additional data must be valid JSON.";
      return;
    }

    const parsedLatitude = Number.parseFloat(fieldLatitude.value.trim());
    const parsedLongitude = Number.parseFloat(fieldLongitude.value.trim());
    const parsedRadius = Number.parseFloat(fieldRadius.value.trim());
    const collectedStats = collectStatsFromEditor();
    const collectedStatuses = collectStatusesFromEditor();
    if (collectedStats.error) {
      saveStatus.textContent = collectedStats.error;
      return;
    }
    if (collectedStatuses.error) {
      saveStatus.textContent = collectedStatuses.error;
      return;
    }
    
    const currentCoordinates = objectEntry.geometry?.coordinates;
    const fallbackLatitude = Array.isArray(currentCoordinates) ? currentCoordinates[1] : null;
    const fallbackLongitude = Array.isArray(currentCoordinates) ? currentCoordinates[0] : null;
    const fallbackRadius = Number.isFinite(objectEntry.properties?.appearance?.radius)
      ? objectEntry.properties.appearance.radius
      : null;
    const currentMetaData = objectEntry.properties?.metaData || {};
    
    const nextLatitude = Number.isFinite(parsedLatitude) ? Math.round(parsedLatitude * 100000) / 100000 : fallbackLatitude;
    const nextLongitude = Number.isFinite(parsedLongitude) ? Math.round(parsedLongitude * 100000) / 100000 : fallbackLongitude;
    const nextRadius = Number.isFinite(parsedRadius) ? parsedRadius : fallbackRadius;

    let nextGeometry = objectEntry.geometry;
    if (objectEntry.geometry?.type === "Point" && Number.isFinite(nextLatitude) && Number.isFinite(nextLongitude)) {
      nextGeometry = {
        ...objectEntry.geometry,
        coordinates: [nextLongitude, nextLatitude],
      };
    }


    const nextStats = collectedStats.stats;
    const nextStatuses = collectedStatuses.statuses;
    const nextEntry = {
      ...objectEntry,
      geometry: nextGeometry,
      properties: {
        ...objectEntry.properties,
        metaData: {
          ...currentMetaData,
          name: fieldName.value.trim() || currentMetaData.name || state.selectedId,
          description: fieldDescription.value.trim(),
          type: fieldType.value.trim(),
        },
        appearance: {
          ...objectEntry.properties?.appearance,
          color: fieldColor.value,
          visible: fieldVisible.checked,
          radius: nextRadius,
        },
        data: parsedExtra,
        stats: nextStats,
        statuses: nextStatuses,
      },
    };

    saveStatus.textContent = state.firebaseReady ? "Sending edit request..." : "Saving locally...";

    try {
      await submitEditedObjectRequest(state.selectedId, nextEntry);
      saveStatus.textContent = state.firebaseReady
        ? "Edit request sent. Server will apply updates shortly."
        : "Saved locally. Add Firebase config to sync remotely.";
    } catch (error) {
      console.error(error);
      saveStatus.textContent = "Edit request failed. Check Firebase configuration and permissions.";
    }
  });

  deleteObjectButton.addEventListener("click", async () => {
    if (!canEditObjects()) {
      saveStatus.textContent = "Read-only mode: deleting requires gm password.";
      return;
    }

    if (!state.selectedId || !state.objects[state.selectedId]) {
      saveStatus.textContent = "Delete failed: no object selected.";
      return;
    }

    const deletingId = state.selectedId;
    saveStatus.textContent = state.firebaseReady ? "Sending delete request..." : "Deleting locally...";

    try {
      await submitDeletedObjectRequest(deletingId);
      saveStatus.textContent = state.firebaseReady
        ? "Delete request sent. Server will remove the object shortly."
        : "Deleted locally. Add Firebase config to sync remotely.";
    } catch (error) {
      console.error(error);
      saveStatus.textContent = "Delete request failed. Check Firebase configuration and permissions.";
    }
  });
}

function setDrawerOpen(isOpen) {
  drawer.classList.toggle("is-open", isOpen);
  drawerToggle.setAttribute("aria-expanded", String(isOpen));
}

function locateUser() {
  if (!navigator.geolocation) {
    locationStatus.textContent = "Geolocation is not available in this browser.";
    return;
  }

  locationStatus.textContent = "Waiting for location fix...";

  navigator.geolocation.watchPosition(
    ({ coords }) => {
      const latLng = [
        Math.round(coords.latitude * 100000) / 100000,
        Math.round(coords.longitude * 100000) / 100000,
      ];
      state.userLocation = latLng;

      if (state.userId && !state.objects[state.userId] && !state.pendingUserSetup) {
        createUserObject();
      }
      if (state.userId && !state.trackingInterval && !state.pendingUserSetup) {
        startCoordinateTracking();
      }

      if (!state.userMarker) {
        state.userMarker = L.circleMarker(latLng, {
          radius: 2,
          color: "#12413a",
          weight: 2,
          fillColor: "#f9fffd",
          fillOpacity: 0.95,
        }).addTo(state.map);

        state.map.setView(latLng, 16);
      } else {
        state.userMarker.setLatLng(latLng);
      }

      locationStatus.textContent = `${coords.latitude.toFixed(5)}, ${coords.longitude.toFixed(5)}`;
    },
    (error) => {
      locationStatus.textContent = `Location unavailable: ${error.message}`;
    },
    {
      enableHighAccuracy: true,
      maximumAge: 5000,
      timeout: 15000,
    },
  );
}

function promptUserId() {
  const modal = document.querySelector("#user-id-modal");
  const form = document.querySelector("#user-id-form");
  const sessionInput = document.querySelector("#session-name-input");
  const passwordInput = document.querySelector("#user-pass-input");
  const statusNote = document.querySelector("#user-id-status");


  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.querySelector("#user-id-input");
    const sessionName = normalizeSessionName(sessionInput?.value.trim() || "testBed");
    const id = input.value.trim();
    const password = passwordInput?.value.trim() || "";

    if (statusNote) {
      statusNote.textContent = "";
    }

    if (!id) {
      return;
    }

    const normalizedPassword = password.toLowerCase();
    const acceptedPasswords = new Set(["user", "adm1n"]);
    if (!acceptedPasswords.has(normalizedPassword)) {
      if (statusNote) {
        statusNote.textContent = "password rejected";
      }
      return;
    }

    state.userId = id;
    state.userPass = normalizedPassword;
    state.sessionName = sessionName;

    if (sessionInput) {
      sessionInput.value = sessionName;
    }

    if (drawerTitle) {
      drawerTitle.textContent = `${state.userId}'s ${sessionName}`;
    }

    reconnectObjectListener();
    modal.hidden = true;

    // Defer createUserObject/startCoordinateTracking until the first Firebase
    // snapshot arrives in applyObjects, so existing data is not overwritten.
    state.pendingUserSetup = true;
  });
}

function createUserObject() {
  if (!state.userId || !state.userLocation) {
    return;
  }
  const [lat, lng] = state.userLocation;
  void submitRequest({
    requestId: state.userId,
    requestType: "new_location",
    coordinates: [lng, lat],
    quiet: true,
  });
  startCoordinateTracking();
}

function startCoordinateTracking() {
  if (state.trackingInterval) {
    clearInterval(state.trackingInterval);
  }

  state.trackingInterval = setInterval(() => {
    if (!state.userId || !state.userLocation) {
      return;
    }

    const [lat, lng] = state.userLocation;

    const existing = state.objects[state.userId];
    if (existing) {
      const updated = {
        ...existing,
        geometry: {
          ...existing.geometry,
          coordinates: [lng, lat],
        },
      };

      if (updated.properties && Object.prototype.hasOwnProperty.call(updated.properties, "zoneBorders")) {
        delete updated.properties.zoneBorders;
      }

      state.objects[state.userId] = updated;
      renderLayer();
    }

    void submitRequest({
      requestId: state.userId,
      requestType: "new_location",
      coordinates: [lng, lat],
      quiet: true,
    });
  }, state.updateFrequency);
}

function initFirebaseListener() {
  const configReady = Object.values(firebaseConfig).every(Boolean);

  if (!configReady) {
    locationStatus.textContent = `${locationStatus.textContent} Demo data loaded until Firebase is configured.`;
    applyObjects(demoGeoObjects);
    return;
  }

  const app = initializeApp(firebaseConfig);
  state.database = getDatabase(app);

  state.firebaseReady = true;
  reconnectObjectListener();
}

function toggleListener() {
  state.listenerActive = !state.listenerActive;
  listenerToggle.setAttribute("data-state", state.listenerActive ? "active" : "paused");
  listenerToggle.textContent = state.listenerActive ? "pause db" : "resume db";
  listenerToggle.setAttribute("title", state.listenerActive ? "Pause Firebase listener" : "Resume Firebase listener");
}

async function submitRequest({
  requestId,
  requestType,
  coordinates = null,
  clientRequestProperties = {},
  properties = {},
  successMessage = "Request sent",
  quiet = false,
}) {
  if (!state.firebaseReady || !state.database) {
    if (!quiet) {
      locationStatus.textContent = "Request unavailable: Firebase is not ready.";
    }
    return;
  }

  if (!state.userId) {
    if (!quiet) {
      locationStatus.textContent = "Request unavailable: enter your ID first.";
    }
    return;
  }

  if (!coordinates) {
    if (!state.userLocation) {
      if (!quiet) {
        locationStatus.textContent = "Request unavailable: waiting for location fix.";
      }
      return;
    }
    const [lat, lng] = state.userLocation;
    coordinates = [lng, lat];
  }

  if (!Array.isArray(coordinates) || coordinates.length < 2) {
    if (!quiet) {
      locationStatus.textContent = "Request unavailable: invalid coordinates.";
    }
    return;
  }

  const timestamp = new Date().toISOString();
  const requestKey = `${Date.now()}-${state.userId}-${String(requestId).replace(/\s+/g, "-")}`;
  const requestFeature = {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates,
    },
    properties: {
      id: requestKey,
      ...properties,
      clientRequestProperties: {
        requesterId: state.userId,
        timestamp,
        type: requestType,
        requestedAction: requestId,
        ...clientRequestProperties,
      },
    },
  };

  try {
    await update(ref(state.database, getFirebaseClientRequestPath()), {
      [requestKey]: requestFeature,
    });
    if (!quiet) {
      locationStatus.textContent = `${successMessage} at ${timestamp}`;
    }
  } catch (error) {
    console.error(error);
    if (!quiet) {
      locationStatus.textContent = "Request failed. Check Firebase permissions and connection.";
    }
    throw error;
  }
}

async function submitEditedObjectRequest(targetId, nextEntry) {
  const coordinates = Array.isArray(nextEntry?.geometry?.coordinates)
    ? nextEntry.geometry.coordinates
    : (Array.isArray(state.userLocation) ? [state.userLocation[1], state.userLocation[0]] : null);

  const formData = {
    name: fieldName.value.trim(),
    type: fieldType.value.trim(),
    color: fieldColor.value,
    visible: fieldVisible.checked,
    latitude: fieldLatitude.value.trim(),
    longitude: fieldLongitude.value.trim(),
    radius: fieldRadius.value.trim(),
    description: fieldDescription.value.trim(),
    stats: nextEntry?.properties?.stats || {},
    statuses: nextEntry?.properties?.statuses || {},
    extraData: nextEntry?.properties?.data || {},
  };

  await submitRequest({
    requestId: `edit-${targetId}`,
    requestType: "edited_object",
    coordinates,
    clientRequestProperties: {
      targetId,
      targetPath: `${getFirebaseCollectionPath()}/${targetId}`,
    },
    properties: {
      formData,
    },
    successMessage: `Edit request for ${targetId} sent`,
  });
}

async function submitDeletedObjectRequest(targetId) {
  const selected = state.objects[targetId];
  const coordinates = Array.isArray(selected?.geometry?.coordinates)
    ? selected.geometry.coordinates
    : (Array.isArray(state.userLocation) ? [state.userLocation[1], state.userLocation[0]] : null);

  await submitRequest({
    requestId: `delete-${targetId}`,
    requestType: "deleted_object",
    coordinates,
    clientRequestProperties: {
      targetId,
      targetPath: `${getFirebaseCollectionPath()}/${targetId}`,
    },
    successMessage: `Delete request for ${targetId} sent`,
  });
}

function applyObjects(nextObjects) {
  state.objects = normalizeObjects(nextObjects);
  renderLayer();
  renderObjectList();

  if (state.pendingUserSetup && state.userId && state.userLocation) {
    state.pendingUserSetup = false;
    if (!state.objects[state.userId]) {
      createUserObject();
    } else {
      startCoordinateTracking();
    }
  }

  if (state.selectedId && !state.objects[state.selectedId]) {
    state.selectedId = null;
  }

  if (state.selectedId) {
    populateEditor(state.selectedId);
  } else {
    showEmptyEditor();
  }

  // Reapply collapse state after editor updates
  applyCollapseState();
}

function normalizeIsUserValue(value) {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "number") {
    return value !== 0;
  }

  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "1", "yes", "y", "on"].includes(normalized)) {
      return true;
    }
    if (["false", "0", "no", "n", "off", ""].includes(normalized)) {
      return false;
    }
  }

  return false;
}

function inferGeometryType(coordinates) {
  if (!Array.isArray(coordinates) || coordinates.length < 2) {
    return "";
  }

  const first = coordinates[0];
  if (typeof first === "number") {
    return "Point";
  }
  if (Array.isArray(first) && typeof first[0] === "number") {
    return "LineString";
  }
  if (Array.isArray(first) && Array.isArray(first[0]) && typeof first[0][0] === "number") {
    return "Polygon";
  }
  return "";
}

function normalizeFeatureEntry(key, entry, fallbackId) {
  if (!entry || typeof entry !== "object") {
    return null;
  }

  const properties = entry.properties && typeof entry.properties === "object" ? entry.properties : {};
  const geometry = entry.geometry && typeof entry.geometry === "object" ? entry.geometry : {};
  const coordinates = Array.isArray(geometry.coordinates) ? geometry.coordinates : [];
  const geometryType = geometry.type || inferGeometryType(coordinates);
  if (!geometryType) {
    return null;
  }

  return {
    ...entry,
    type: entry.type || "Feature",
    geometry: {
      ...geometry,
      type: geometryType,
      coordinates,
    },
    properties: {
      ...properties,
      id: properties.id || key || fallbackId,
      is_user: normalizeIsUserValue(properties.is_user),
    },
  };
}

function normalizeObjects(rawObjects) {
  if (Array.isArray(rawObjects)) {
    return rawObjects.reduce((accumulator, entry, index) => {
      const normalizedEntry = normalizeFeatureEntry(`item-${index}`, entry, `item-${index}`);
      if (!normalizedEntry) {
        return accumulator;
      }

      accumulator[normalizedEntry.properties.id] = normalizedEntry;
      return accumulator;
    }, {});
  }

  return Object.entries(rawObjects).reduce((accumulator, [key, entry]) => {
    const normalizedEntry = normalizeFeatureEntry(key, entry, key);
    if (!normalizedEntry) {
      return accumulator;
    }

    accumulator[key] = normalizedEntry;
    return accumulator;
  }, {});
}

function renderLayer() {
  if (state.geoJsonLayer) {
    state.geoJsonLayer.remove();
  }

  const visibleFeatures = Object.values(state.objects).filter((feature) => feature.properties?.appearance?.visible);

  state.geoJsonLayer = L.geoJSON(visibleFeatures, {
    pointToLayer: (feature, latlng) => L.circle(latlng, pointStyle(feature)),
    style: polygonStyle,
    onEachFeature: (feature, layer) => {
      layer.bindPopup(buildPopupMarkup(feature));
      layer.on("click", () => {
        const id = feature.properties?.id;
        if (id) {
          selectObject(id, { flyTo: false });
        }
      });
    },
  }).addTo(state.map);
}

function pointStyle(feature) {
  const color = feature.properties?.appearance?.color || "#0b8f87";
  const radius = Number.isFinite(feature.properties?.appearance?.radius) ? feature.properties.appearance.radius : 5;
  return {
    radius,
    color,
    fillColor: color,
    fillOpacity: 0.85,
    weight: 2,
  };
}

function polygonStyle(feature) {
  const color = feature.properties?.appearance?.color || "#0b8f87";
  return {
    color,
    fillColor: color,
    fillOpacity: 0.22,
    weight: 2,
  };
}

function buildPopupMarkup(feature) {
  const properties = feature.properties || {};
  const metaData = properties.metaData || {};
  const extraData = properties.data || {};
  const extraItems = Object.entries(extraData)
    .map(([key, value]) => `<li><strong>${escapeHtml(key)}:</strong> ${escapeHtml(String(value))}</li>`)
    .join("");

  return `
    <div>
      <strong>${escapeHtml(metaData.name || properties.id || "Untitled object")}</strong>
      <p>${escapeHtml(metaData.description || "No description available.")}</p>
      ${extraItems ? `<ul class="popup-details">${extraItems}</ul>` : ""}
    </div>
  `;
}

function renderObjectList() {
  const entries = Object.values(state.objects);

  objectList.innerHTML = entries.length
    ? entries
        .map((feature) => {
          const id = feature.properties?.id;
          const color = feature.properties?.appearance?.color || "#0b8f87";
          const visible = feature.properties?.appearance?.visible ? "Visible" : "Hidden";
          const selectedClass = state.selectedId === id ? "is-selected" : "";
          const name = escapeHtml(feature.properties?.metaData?.name || id || "Unnamed object");
          const type = escapeHtml(feature.geometry?.type || "Unknown");

          return `
            <li>
              <button class="${selectedClass}" type="button" data-id="${escapeHtml(id)}">
                <span>
                  <strong style="color: ${escapeHtml(color)};">${name}</strong>
                  <span class="list-meta">${type} • ${visible}</span>
                </span>
                  <span aria-hidden="true">Edit</span>
              </button>
            </li>
          `;
        })
        .join("")
    : "<li>No GeoJSON objects found.</li>";
}

function selectObject(id, options = {}) {
  const feature = state.objects[id];
  if (!feature) {
    return;
  }

  state.selectedId = id;
  populateEditor(id);
  renderObjectList();
  setDrawerOpen(true);

  if (options.flyTo !== false) {
    focusFeature(feature);
  }
}

function focusFeature(feature) {
  const geometry = feature.geometry || {};

  if (geometry.type === "Point") {
    const [lng, lat] = geometry.coordinates;
    state.map.flyTo([lat, lng], 17, { duration: 0.6 });
    return;
  }

  const boundsLayer = L.geoJSON(feature);
  const bounds = boundsLayer.getBounds();

  if (bounds.isValid()) {
    state.map.flyToBounds(bounds, {
      padding: [24, 24],
      duration: 0.6,
    });
  }
}

function populateEditor(id) {
  const feature = state.objects[id];
  if (!feature) {
    showEmptyEditor();
    return;
  }

  const metaData = feature.properties?.metaData || {};
  const stats = normalizeStats(feature.properties);
  const statuses = normalizeStatuses(feature.properties);
  editorForm.hidden = false;
  editorEmptyState.textContent = `Editing ${metaData.name || id}`;
  fieldName.value = metaData.name || "";
  fieldType.value = metaData.type || "";
  fieldColor.value = feature.properties?.appearance?.color || "#0b8f87";
  fieldVisible.checked = Boolean(feature.properties?.appearance?.visible);
  fieldLatitude.value = feature.geometry?.coordinates ? String(feature.geometry.coordinates[1]) : "";
  fieldLongitude.value = feature.geometry?.coordinates ? String(feature.geometry.coordinates[0]) : "";
  fieldRadius.value = Number.isFinite(feature.properties?.appearance?.radius) ? String(feature.properties.appearance.radius) : "";
  fieldDescription.value = metaData.description || "";
  renderStatsEditor(stats);
  renderStatusesEditor(statuses);

  fieldExtra.value = JSON.stringify(feature.properties?.data || {}, null, 2);
  applyEditorPermissions();
}

function showEmptyEditor() {
  editorForm.hidden = true;
  editorEmptyState.textContent = "Select an object from the list.";
  saveStatus.textContent = "";
  renderStatsEditor({});
  renderStatusesEditor({});
  applyEditorPermissions();
}

function canEditObjects() {
  return state.userPass === "adm1n";
}

function applyEditorPermissions() {
  const isEditable = canEditObjects();

  editableFields.forEach((field) => {
    field.disabled = !isEditable;
  });

  const isFormVisible = !editorForm.hidden;
  if (coordPickButton) {
    coordPickButton.disabled = !isEditable || !isFormVisible;
    if (!isEditable || !isFormVisible) {
      setCoordPickMode(false);
    }
  }
  deleteObjectButton.disabled = !isEditable || !isFormVisible;
  const saveButton = editorForm.querySelector('button[type="submit"]');
  if (saveButton) {
    saveButton.disabled = !isEditable || !isFormVisible;
  }

  addStatButton.disabled = !isEditable || !isFormVisible;
  statsList.querySelectorAll("input, button").forEach((element) => {
    element.disabled = !isEditable || !isFormVisible;
  });
  addStatusButton.disabled = !isEditable || !isFormVisible;
  statusesList.querySelectorAll("input, button").forEach((element) => {
    element.disabled = !isEditable || !isFormVisible;
  });
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalizeSessionName(rawValue) {
  const trimmed = rawValue.trim();
  const withoutSlashes = trimmed.replace(/^\/+|\/+$/g, "");
  return withoutSlashes || "testBed";
}

function getFirebaseCollectionPath() {
  return `${state.sessionName}/${firebaseCollectionNode}`;
}

function getFirebaseClientRequestPath() {
  return `${state.sessionName}/${firebaseClientRequestNode}`;
}

function reconnectObjectListener() {
  if (!state.firebaseReady || !state.database) {
    return;
  }

  if (typeof state.listenerUnsubscribe === "function") {
    state.listenerUnsubscribe();
    applyObjects({});
  }

  const objectRef = ref(state.database, getFirebaseCollectionPath());
  state.listenerUnsubscribe = onValue(objectRef, (snapshot) => {
    if (state.listenerActive) {
      applyObjects(snapshot.val() || {});
      // Reapply collapse state after objects are updated
      applyCollapseState();
    }
  });
}