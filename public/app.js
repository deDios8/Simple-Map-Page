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
const firebaseEventCriteriaNode = "eventCriteria";

const state = {
  version: "0.1.031",
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
  criteria: {},
  selectedCriteriaId: null,
  criteriaListenerUnsubscribe: null,
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
const fieldColor = document.querySelector("#field-color");
const fieldVisible = document.querySelector("#field-visible");
const fieldTraits = document.querySelector("#field-traits");
const coordDisplayLat = document.querySelector("#coord-display-lat");
const coordDisplayLng = document.querySelector("#coord-display-lng");
const coordPickButton = document.querySelector("#coord-pick-button");
const fieldRadius = document.querySelector("#field-radius");
const fieldDescription = document.querySelector("#field-description");
const statsList = document.querySelector("#stats-list");
const addStatButton = document.querySelector("#add-stat-button");
const editorFormToggle = document.querySelector("#editor-form-toggle");
const statsSectionToggle = document.querySelector("#stats-section-toggle");
const statsSection = document.querySelector(".stats-section");
const versionInfo = document.querySelector("#version-info");

// Events drawer DOM references
const eventsDrawer = document.querySelector("#events-drawer");
const eventsDrawerToggle = document.querySelector("#events-drawer-toggle");
const eventsDrawerClose = document.querySelector("#events-drawer-close");
const criteriaList = document.querySelector("#criteria-list");
const criteriaEditorForm = document.querySelector("#criteria-editor-form");
const criteriaEditorEmptyState = document.querySelector("#criteria-editor-empty-state");
const criteriaSaveStatus = document.querySelector("#criteria-save-status");
const deleteCriteriaButton = document.querySelector("#delete-criteria-button");
const criteriaFieldName = document.querySelector("#criteria-field-name");
const criteriaFieldDescription = document.querySelector("#criteria-field-description");
const criteriaComponentsList = document.querySelector("#criteria-components-list");
const addCriterionButton = document.querySelector("#add-criterion-button");
const addCriteriaButton = document.querySelector("#add-criteria-button");
const criteriaEditorFormToggle = document.querySelector("#criteria-editor-form-toggle");
const criteriaComponentsSectionToggle = document.querySelector("#criteria-components-section-toggle");
const criteriaComponentsSection = document.querySelector(".criteria-components-section");

const criteriaEditableFields = [
  criteriaFieldName,
  criteriaFieldDescription,
];
const editableFields = [
  fieldName,
  fieldColor,
  fieldVisible,
  fieldTraits,
  fieldRadius,
  fieldDescription,
];

const editorCollapseState = {
  editorForm: true,
  stats: true,
};

const criteriaCollapseState = {
  form: true,
  components: true,
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
  setEditorFormCollapsed(editorCollapseState.editorForm);
  setStatsSectionCollapsed(editorCollapseState.stats);
}

function setEditorFormCollapsed(isCollapsed) {
  editorCollapseState.editorForm = Boolean(isCollapsed);
  editorForm.classList.toggle("is-collapsed", editorCollapseState.editorForm);
  if (editorFormToggle) {
    editorFormToggle.textContent = editorCollapseState.editorForm ? "Expand editor" : "Collapse editor";
    editorFormToggle.setAttribute("aria-expanded", String(!editorCollapseState.editorForm));
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

// ---------------------------------------------------------------------------
// Criteria collapse state helpers
// ---------------------------------------------------------------------------

function saveCriteriaCollapseState() {
  localStorage.setItem("criteriaCollapseState", JSON.stringify(criteriaCollapseState));
}

function loadCriteriaCollapseState() {
  const saved = localStorage.getItem("criteriaCollapseState");
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      if (typeof parsed === "object") {
        Object.assign(criteriaCollapseState, parsed);
      }
    } catch (e) {
      console.error("Failed to parse criteria collapse state from localStorage", e);
    }
  }
}

function applyCriteriaCollapseState() {
  setCriteriaFormCollapsed(criteriaCollapseState.form);
  setCriteriaComponentsSectionCollapsed(criteriaCollapseState.components);
}

function setCriteriaFormCollapsed(isCollapsed) {
  criteriaCollapseState.form = Boolean(isCollapsed);
  criteriaEditorForm?.classList.toggle("is-collapsed", criteriaCollapseState.form);
  if (criteriaEditorFormToggle) {
    criteriaEditorFormToggle.textContent = criteriaCollapseState.form ? "Expand editor" : "Collapse editor";
    criteriaEditorFormToggle.setAttribute("aria-expanded", String(!criteriaCollapseState.form));
  }
  saveCriteriaCollapseState();
}

function setCriteriaComponentsSectionCollapsed(isCollapsed) {
  criteriaCollapseState.components = Boolean(isCollapsed);
  criteriaComponentsSection?.classList.toggle("is-collapsed", criteriaCollapseState.components);
  if (criteriaComponentsSectionToggle) {
    criteriaComponentsSectionToggle.textContent = criteriaCollapseState.components ? "Expand" : "Collapse";
    criteriaComponentsSectionToggle.setAttribute("aria-expanded", String(!criteriaCollapseState.components));
  }
  saveCriteriaCollapseState();
}

function nameToKey(name) {
  return String(name).trim().toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_-]/g, "");
}

function createDefaultStat() {
  return {
    key: "",
    name: "",
    value: 0,
    max_value: 100,
    min_value: 0,
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

function collectStatsFromEditor(options = {}) {
  const allowEmpty = Boolean(options.allowEmpty);
  const rows = Array.from(statsList?.querySelectorAll(".stat-row") || []);
  const stats = {};
  let primaryStat = null;

  for (const [index, row] of rows.entries()) {
    const getValue = (field) => row.querySelector(`[data-field="${field}"]`)?.value ?? "";
    const originalKey = row.getAttribute("data-key") || "";
    const name = getValue("name").trim();
    const rawValue = Number.parseFloat(getValue("value").trim());
    const rawMin = Number.parseFloat(row.getAttribute("data-min") ?? "");
    const rawMax = Number.parseFloat(row.getAttribute("data-max") ?? "");

    if (!name && !getValue("value").trim()) {
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

// ---------------------------------------------------------------------------
// Criteria editor functions
// ---------------------------------------------------------------------------

function normalizeCriteriaEntry(key, entry) {
  if (!entry || typeof entry !== "object") return null;
  const properties = entry.properties && typeof entry.properties === "object" ? entry.properties : {};
  return {
    ...entry,
    type: entry.type || "Feature",
    geometry: null,
    properties: {
      ...properties,
      id: properties.id || key,
    },
  };
}

function normalizeCriteria(rawCriteria) {
  if (!rawCriteria || typeof rawCriteria !== "object") return {};
  return Object.entries(rawCriteria).reduce((acc, [key, entry]) => {
    const normalized = normalizeCriteriaEntry(key, entry);
    if (!normalized) return acc;
    acc[key] = normalized;
    return acc;
  }, {});
}

function renderCriteriaList() {
  if (!criteriaList) return;
  const entries = Object.values(state.criteria);
  criteriaList.innerHTML = entries.length
    ? entries
        .map((entry) => {
          const id = entry.properties?.id;
          const name = escapeHtml(entry.properties?.metaData?.name || id || "Unnamed criteria");
          const selectedClass = state.selectedCriteriaId === id ? "is-selected" : "";
          return `
            <li>
              <button class="${selectedClass}" type="button" data-criteria-id="${escapeHtml(id)}">
                <span>
                  <strong>${name}</strong>
                </span>
                <span aria-hidden="true">Edit</span>
              </button>
            </li>
          `;
        })
        .join("")
    : "<li>No event criteria found.</li>";
}

function selectCriteria(id, options = {}) {
  const entry = state.criteria[id];
  if (!entry) return;
  state.selectedCriteriaId = id;
  populateCriteriaEditor(id);
  renderCriteriaList();
  setCriteriaDrawerOpen(true);
}

function setCriteriaDrawerOpen(isOpen) {
  eventsDrawer?.classList.toggle("is-open", isOpen);
  eventsDrawerToggle?.setAttribute("aria-expanded", String(isOpen));
}

function renderCriteriaComponentsEditor(components) {
  if (!criteriaComponentsList) return;
  const entries = Object.entries(components || {});
  if (!entries.length) {
    criteriaComponentsList.innerHTML = '<div class="stats-empty">No criteria yet. Add one to define matching rules.</div>';
    return;
  }

  criteriaComponentsList.innerHTML = entries
    .map(([name, data], index) => {
      const tags = Array.isArray(data?.tags) ? data.tags.join(", ") : "";
      return `
        <article class="stat-row" data-criterion-index="${index}" data-criterion-name="${escapeHtml(name)}">
          <div class="criterion-row-grid">
            <label>
              Name
              <input type="text" data-field="name" value="${escapeHtml(name)}" placeholder="CriteriaHasTags" />
            </label>
            <label>
              Tags
              <input type="text" data-field="tags" value="${escapeHtml(tags)}" placeholder="tag1, tag2" />
            </label>
            <button class="stat-remove-button" type="button" data-action="remove-criterion" aria-label="Remove criterion">✕</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function addEmptyCriterionRow() {
  const currentComponents = collectCriteriaComponentsFromEditor();
  const nextComponents = { ...currentComponents };
  let index = Object.keys(nextComponents).length + 1;
  let nextKey = `criterion_${index}`;
  while (Object.prototype.hasOwnProperty.call(nextComponents, nextKey)) {
    index += 1;
    nextKey = `criterion_${index}`;
  }
  nextComponents[nextKey] = { tags: [] };
  renderCriteriaComponentsEditor(nextComponents);
  applyCriteriaEditorPermissions();
}

function collectCriteriaComponentsFromEditor() {
  const rows = Array.from(criteriaComponentsList?.querySelectorAll(".stat-row") || []);
  const components = {};
  for (const row of rows) {
    const name = row.querySelector('[data-field="name"]')?.value?.trim() || "";
    const tagsRaw = row.querySelector('[data-field="tags"]')?.value?.trim() || "";
    if (!name) continue;
    const tags = tagsRaw.split(",").map((s) => s.trim()).filter(Boolean);
    components[name] = { tags };
  }
  return components;
}

function populateCriteriaEditor(id) {
  const entry = state.criteria[id];
  if (!entry) {
    showEmptyCriteriaEditor();
    return;
  }
  const metaData = entry.properties?.metaData || {};
  const components = extractCriteriaComponents(entry.properties);
  criteriaEditorForm.hidden = false;
  criteriaEditorEmptyState.textContent = `Editing ${metaData.name || id}`;
  criteriaFieldName.value = metaData.name || "";
  criteriaFieldDescription.value = metaData.description || "";
  renderCriteriaComponentsEditor(components);
  applyCriteriaEditorPermissions();
}

function extractCriteriaComponents(properties) {
  if (!properties || typeof properties !== "object") return {};
  const knownNames = new Set([
    "CriteriaHasTags", "CriteriaIsWithin", "CriteriaJustEntered",
    "CriteriaJustExited", "CriteriaIsVisible", "CriteriaIsNotVisible", "CriteriaFirstEntered",
  ]);
  const components = {};
  for (const [key, value] of Object.entries(properties)) {
    if (knownNames.has(key) && value && typeof value === "object") {
      components[key] = value;
    }
  }
  return components;
}

function showEmptyCriteriaEditor() {
  criteriaEditorForm.hidden = true;
  criteriaEditorEmptyState.textContent = "Select a criteria to edit.";
  criteriaSaveStatus.textContent = "";
  renderCriteriaComponentsEditor({});
  applyCriteriaEditorPermissions();
}

function applyCriteriaEditorPermissions() {
  const isEditable = canEditObjects();
  criteriaEditableFields.forEach((field) => {
    if (field) field.disabled = !isEditable;
  });
  const isFormVisible = criteriaEditorForm && !criteriaEditorForm.hidden;
  if (deleteCriteriaButton) {
    deleteCriteriaButton.disabled = !isEditable || !isFormVisible;
  }
  const saveButton = criteriaEditorForm?.querySelector('button[type="submit"]');
  if (saveButton) {
    saveButton.disabled = !isEditable || !isFormVisible;
  }
  if (addCriterionButton) {
    addCriterionButton.disabled = !isEditable || !isFormVisible;
  }
  criteriaComponentsList?.querySelectorAll("input, button").forEach((el) => {
    el.disabled = !isEditable || !isFormVisible;
  });
}

function handleCriteriaSnapshot(nextCriteria) {
  state.criteria = normalizeCriteria(nextCriteria);
  renderCriteriaList();

  if (state.selectedCriteriaId && !state.criteria[state.selectedCriteriaId]) {
    state.selectedCriteriaId = null;
  }

  if (state.selectedCriteriaId) {
    populateCriteriaEditor(state.selectedCriteriaId);
  } else {
    showEmptyCriteriaEditor();
  }

  applyCriteriaCollapseState();
}

function getFirebaseEventCriteriaPath() {
  return `${state.sessionName}/${firebaseEventCriteriaNode}`;
}

function resetCriteriaListener() {
  if (!state.firebaseReady || !state.database) return;

  if (typeof state.criteriaListenerUnsubscribe === "function") {
    state.criteriaListenerUnsubscribe();
    handleCriteriaSnapshot({});
  }

  const criteriaRef = ref(state.database, getFirebaseEventCriteriaPath());
  state.criteriaListenerUnsubscribe = onValue(criteriaRef, (snapshot) => {
    if (state.listenerActive) {
      handleCriteriaSnapshot(snapshot.val() || {});
      applyCriteriaCollapseState();
    }
  });
}

async function submitAddCriteriaRequest() {
  const coordinates = Array.isArray(state.userLocation)
    ? [state.userLocation[1], state.userLocation[0]]
    : [0, 0];
  await submitRequest({
    requestId: "add_criteria",
    requestType: "add_criteria",
    coordinates,
    successMessage: "Add criteria request sent",
  });
}

async function submitEditedCriteriaRequest(targetId, formData) {
  const coordinates = Array.isArray(state.userLocation)
    ? [state.userLocation[1], state.userLocation[0]]
    : [0, 0];
  await submitRequest({
    requestId: `edit-criteria-${targetId}`,
    requestType: "edited_criteria",
    coordinates,
    clientRequestPayload: { targetId },
    properties: { formData },
    successMessage: `Edit criteria request for ${targetId} sent`,
  });
}

async function submitDeletedCriteriaRequest(targetId) {
  const coordinates = Array.isArray(state.userLocation)
    ? [state.userLocation[1], state.userLocation[0]]
    : [0, 0];
  await submitRequest({
    requestId: `delete-criteria-${targetId}`,
    requestType: "deleted_criteria",
    coordinates,
    clientRequestPayload: { targetId },
    successMessage: `Delete criteria request for ${targetId} sent`,
  });
}

function init() {
  renderVersionInfo();
  loadCollapseState();
  applyCollapseState();
  loadCriteriaCollapseState();
  applyCriteriaCollapseState();
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
    if (coordDisplayLat) {
      coordDisplayLat.textContent = `Lat: ${Math.round(lat * 100000) / 100000}`;
    }
    if (coordDisplayLng) {
      coordDisplayLng.textContent = `Lng: ${Math.round(lng * 100000) / 100000}`;
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
    void submitRequest({ requestId: "add_object", requestType: "button_click", successMessage: "add object sent" });
  });
  addStatButton?.addEventListener("click", () => {
    addEmptyStatRow();
  });
  coordPickButton?.addEventListener("click", () => {
    setCoordPickMode(!state.coordPickMode);
  });

  editorFormToggle?.addEventListener("click", () => {
    setEditorFormCollapsed(!editorCollapseState.editorForm);
  });
  statsSectionToggle?.addEventListener("click", () => {
    setStatsSectionCollapsed(!editorCollapseState.stats);
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

  // Events drawer bindings
  eventsDrawerToggle?.addEventListener("click", () => {
    setCriteriaDrawerOpen(!eventsDrawer?.classList.contains("is-open"));
  });
  eventsDrawerClose?.addEventListener("click", () => setCriteriaDrawerOpen(false));
  addCriteriaButton?.addEventListener("click", () => {
    void submitAddCriteriaRequest();
  });
  criteriaEditorFormToggle?.addEventListener("click", () => {
    setCriteriaFormCollapsed(!criteriaCollapseState.form);
  });
  criteriaComponentsSectionToggle?.addEventListener("click", () => {
    setCriteriaComponentsSectionCollapsed(!criteriaCollapseState.components);
  });
  addCriterionButton?.addEventListener("click", () => {
    addEmptyCriterionRow();
  });
  criteriaComponentsList?.addEventListener("click", (event) => {
    const button = event.target.closest('button[data-action="remove-criterion"]');
    if (!button) return;
    button.closest(".stat-row")?.remove();
    if (!criteriaComponentsList.querySelector(".stat-row")) {
      renderCriteriaComponentsEditor({});
    }
    applyCriteriaEditorPermissions();
  });
  criteriaList?.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-criteria-id]");
    if (!button) return;
    selectCriteria(button.dataset.criteriaId);
  });
  criteriaEditorForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canEditObjects()) {
      criteriaSaveStatus.textContent = "Read-only mode: editing requires gm password.";
      return;
    }
    if (!state.selectedCriteriaId) return;
    const criteriaEntry = state.criteria[state.selectedCriteriaId];
    if (!criteriaEntry) return;

    const formData = {
      name: criteriaFieldName.value.trim(),
      description: criteriaFieldDescription.value.trim(),
      criteriaComponents: collectCriteriaComponentsFromEditor(),
    };

    criteriaSaveStatus.textContent = state.firebaseReady ? "Sending edit request..." : "Saving...";
    try {
      await submitEditedCriteriaRequest(state.selectedCriteriaId, formData);
      criteriaSaveStatus.textContent = state.firebaseReady
        ? "Edit request sent. Server will apply updates shortly."
        : "Saved locally.";
    } catch (error) {
      console.error(error);
      criteriaSaveStatus.textContent = "Edit request failed. Check Firebase configuration and permissions.";
    }
  });
  deleteCriteriaButton?.addEventListener("click", async () => {
    if (!canEditObjects()) {
      criteriaSaveStatus.textContent = "Read-only mode: deleting requires gm password.";
      return;
    }
    if (!state.selectedCriteriaId || !state.criteria[state.selectedCriteriaId]) {
      criteriaSaveStatus.textContent = "Delete failed: no criteria selected.";
      return;
    }
    const deletingId = state.selectedCriteriaId;
    criteriaSaveStatus.textContent = state.firebaseReady ? "Sending delete request..." : "Deleting...";
    try {
      await submitDeletedCriteriaRequest(deletingId);
      criteriaSaveStatus.textContent = state.firebaseReady
        ? "Delete request sent. Server will remove the criteria shortly."
        : "Deleted locally.";
    } catch (error) {
      console.error(error);
      criteriaSaveStatus.textContent = "Delete request failed. Check Firebase configuration and permissions.";
    }
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

    const parsedLatitude = Number.parseFloat(coordDisplayLat.textContent.replace(/^Lat:\s*/i, "").trim());
    const parsedLongitude = Number.parseFloat(coordDisplayLng.textContent.replace(/^Lng:\s*/i, "").trim());
    const parsedRadius = Number.parseFloat(fieldRadius.value.trim());
    const collectedStats = collectStatsFromEditor();
    if (collectedStats.error) {
      saveStatus.textContent = collectedStats.error;
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
    const nextEntry = {
      ...objectEntry,
      geometry: nextGeometry,
      properties: {
        ...objectEntry.properties,
        metaData: {
          ...currentMetaData,
          name: fieldName.value.trim() || currentMetaData.name || state.selectedId,
          description: fieldDescription.value.trim(),
        },
        appearance: {
          ...objectEntry.properties?.appearance,
          color: fieldColor.value,
          visible: parseVisibleList(fieldVisible.value),
          radius: nextRadius,
        },
        traits: parseVisibleList(fieldTraits.value),
        stats: nextStats,
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
  const userIdForm = document.querySelector("#user-id-form");
  const sessionInput = document.querySelector("#session-name-input");
  const passwordInput = document.querySelector("#user-pass-input");
  const statusNote = document.querySelector("#user-id-status");


  userIdForm.addEventListener("submit", (event) => {
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

    resetObjectListener();
    resetCriteriaListener();
    modal.hidden = true;

    // Defer createUserObject/startCoordinateTracking until the first Firebase
    // snapshot arrives in handleObjectSnapshot, so existing data is not overwritten.
    state.pendingUserSetup = true;
  });
}

function createUserObject() {
  if (!state.userId || !state.userLocation) {
    return;
  }
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
      requestId: "new_location",
      requestType: "new_location",
      coordinates: [lng, lat],
      quiet: true,
    });
  }, state.updateFrequency);
}

function initFirebaseListener() {
  const configReady = Object.values(firebaseConfig).every(Boolean);

  if (!configReady) {
    locationStatus.textContent = `${locationStatus.textContent} No data loaded until Firebase is configured.`;
    return;
  }

  const app = initializeApp(firebaseConfig);
  state.database = getDatabase(app);

  state.firebaseReady = true;
  resetObjectListener();
  resetCriteriaListener();
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
  clientRequestPayload = {},
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
  const requestKey = `${Date.now()}-${state.userId}-${String(requestType)}`.replace(/\s+/g, "-");
  const requestFeature = {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates,
    },
    properties: {
      id: requestKey,
      ...properties,
      clientRequestPayload: {
        requesterId: state.userId,
        timestamp,
        type: requestType,
        requestedAction: requestId,
        ...clientRequestPayload,
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
    color: fieldColor.value,
    visible: parseVisibleList(fieldVisible.value),
    traits: parseVisibleList(fieldTraits.value),
    latitude: coordDisplayLat.textContent.replace(/^Lat:\s*/i, "").trim(),
    longitude: coordDisplayLng.textContent.replace(/^Lng:\s*/i, "").trim(),
    radius: fieldRadius.value.trim(),
    description: fieldDescription.value.trim(),
    stats: nextEntry?.properties?.stats || {},
  };

  await submitRequest({
    requestId: `edit-${targetId}`,
    requestType: "edited_object",
    coordinates,
    clientRequestPayload: {
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
    clientRequestPayload: {
      targetId,
      targetPath: `${getFirebaseCollectionPath()}/${targetId}`,
    },
    successMessage: `Delete request for ${targetId} sent`,
  });
}

function handleObjectSnapshot(nextObjects) {
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

function parseVisibleList(value) {
  if (!value || typeof value !== "string") return [];
  return value.split(",").map((s) => s.trim()).filter(Boolean);
}

function isVisibleToCurrentUser(feature) {
  const visibleTo = feature.properties?.appearance?.visible;
  if (!Array.isArray(visibleTo) || visibleTo.length === 0) return false;
  const userTraits = state.objects[state.userId]?.properties?.traits || [];
  const userTraitSet = new Set(
    (Array.isArray(userTraits) ? userTraits : [])
      .map((t) => (typeof t === "string" ? t.toUpperCase() : null))
      .filter(Boolean),
  );
  return visibleTo.some((key) => userTraitSet.has(String(key).toUpperCase()));
}

function renderLayer() {
  if (state.geoJsonLayer) {
    state.geoJsonLayer.remove();
  }

  const visibleFeatures = Object.values(state.objects).filter((feature) => isVisibleToCurrentUser(feature));

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

  return `
    <div>
      <strong>${escapeHtml(metaData.name || properties.id || "Untitled object")}</strong>
      <p>${escapeHtml(metaData.description || "No description available.")}</p>
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
          const traitsList = feature.properties?.traits;
          const traits = Array.isArray(traitsList) && traitsList.length > 0 ? traitsList.join(", ") : "--";
          const selectedClass = state.selectedId === id ? "is-selected" : "";
          const name = escapeHtml(feature.properties?.metaData?.name || id || "Unnamed object");

          return `
            <li>
              <button class="${selectedClass}" type="button" data-id="${escapeHtml(id)}">
                <span>
                  <strong style="color: ${escapeHtml(color)};">${name}</strong>
                  <span class="list-meta">${escapeHtml(traits)}</span>
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
    state.map.flyTo([lat, lng], state.map.getZoom(), { duration: 0.6 });
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
  editorForm.hidden = false;
  editorEmptyState.textContent = `Editing ${metaData.name || id}`;
  fieldName.value = metaData.name || "";
  fieldColor.value = feature.properties?.appearance?.color || "#0b8f87";
  const rawVisible = feature.properties?.appearance?.visible;
  fieldVisible.value = Array.isArray(rawVisible) ? rawVisible.join(", ") : "";
  const rawTraits = feature.properties?.traits;
  fieldTraits.value = Array.isArray(rawTraits) ? rawTraits.join(", ") : "";
  coordDisplayLat.textContent = feature.geometry?.coordinates ? `Lat: ${feature.geometry.coordinates[1]}` : "Lat: --";
  coordDisplayLng.textContent = feature.geometry?.coordinates ? `Lng: ${feature.geometry.coordinates[0]}` : "Lng: --";
  fieldRadius.value = Number.isFinite(feature.properties?.appearance?.radius) ? String(feature.properties.appearance.radius) : "";
  fieldDescription.value = metaData.description || "";
  renderStatsEditor(stats);
  applyEditorPermissions();
}

function showEmptyEditor() {
  editorForm.hidden = true;
  editorEmptyState.textContent = "Select an object from the list.";
  saveStatus.textContent = "";
  renderStatsEditor({});
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

function resetObjectListener() {
  if (!state.firebaseReady || !state.database) {
    return;
  }

  if (typeof state.listenerUnsubscribe === "function") {
    state.listenerUnsubscribe();
    handleObjectSnapshot({});
  }

  const objectRef = ref(state.database, getFirebaseCollectionPath());
  state.listenerUnsubscribe = onValue(objectRef, (snapshot) => {
    if (state.listenerActive) {
      handleObjectSnapshot(snapshot.val() || {});
      // Reapply collapse state after objects are updated
      applyCollapseState();
    }
  });
}