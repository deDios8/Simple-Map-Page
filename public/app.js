import {
  initializeApp,
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js";
import {
  getDatabase,
  onValue,
  ref,
  update,
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-database.js";

// Populated at startup by init() from map_criteria_components.json
let CRITERIA_COMPONENT_OPTIONS = [];
let TRIGGER_COMPONENT_OPTIONS = [];
let TARGET_COMPONENT_OPTIONS = [];

// Populated at startup by init() from map_result_components.json
let RESULT_COMPONENT_FIELD_CONFIG = {};
let RESULT_COMPONENT_OPTIONS = [];


let firebaseConfig = {};
let firebaseGeoObjectsNode = "";
let firebaseClientRequestNode = "";
let firebaseEventCriteriaNode = "";
let firebaseEventResultsNode = "";

const state = {
  updateLocationInterval: 0,
  mapLayer: "",
  mapLayerAttribution: "",
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
  sessionName: "",
  trackingInterval: null,
  listenerActive: true,
  listenerUnsubscribe: null,
  pendingUserSetup: false,
  coordPickMode: false,
  criteria: {},
  selectedEventId: null,
  events: {},
  criteriaListenerUnsubscribe: null,
  eventListenerUnsubscribe: null,
  dismissedMessages: new Set(),
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
const editorPanel = document.querySelector("#editor-panel");
const editorCancelButton = document.querySelector("#editor-cancel-button");
const editorCancelBottomButton = document.querySelector("#editor-cancel-bottom-button");
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
const statsList = document.querySelector("#stats-list");
const addStatButton = document.querySelector("#add-stat-button");
const statsSection = document.querySelector(".stats-section");

// Events drawer DOM references
const eventsResultsDrawer = document.querySelector("#events-results-drawer");
const eventsResultsDrawerToggle = document.querySelector("#events-results-drawer-toggle");
const eventsResultsDrawerClose = document.querySelector("#events-results-drawer-close");
const eventsList = document.querySelector("#events-list");
const eventEditorForm = document.querySelector("#event-editor-form");
const eventEditorEmptyState = document.querySelector("#event-editor-empty-state");
const eventSaveStatus = document.querySelector("#event-save-status");
const deleteEventButton = document.querySelector("#delete-event-button");
const eventFieldName = document.querySelector("#event-field-name");
const triggerCriteriaList = document.querySelector("#trigger-criteria-list");
const addTriggerCriterionButton = document.querySelector("#add-trigger-criterion-button");
const targetCriteriaList = document.querySelector("#target-criteria-list");
const addTargetCriterionButton = document.querySelector("#add-target-criterion-button");
const eventResultsList = document.querySelector("#event-results-list");
const addResultButton = document.querySelector("#add-result-button");
const addEventButton = document.querySelector("#add-event-button");

// Message modal DOM references
const messageModal = document.querySelector("#message-modal");
const messageModalText = document.querySelector("#message-modal-text");
const messageModalOk = document.querySelector("#message-modal-ok");

const eventEditableFields = [
  eventFieldName,
];
const editableFields = [
  fieldName,
  fieldColor,
  fieldVisible,
  fieldTraits,
  fieldRadius,
];

const editorCollapseState = {
  editorForm: true,
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
}

function setEditorFormCollapsed(isCollapsed) {
  editorCollapseState.editorForm = Boolean(isCollapsed);
  editorForm.classList.toggle("is-collapsed", editorCollapseState.editorForm);
  saveCollapseState();
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
// Message modal functions
// ---------------------------------------------------------------------------

function checkForUserMessages() {
  if (!state.userId || !messageModal) return;
  const userObj = state.objects[state.userId];
  const messages = userObj?.properties?.messages;
  if (!Array.isArray(messages) || messages.length === 0) return;

  // Find the first message not already pending dismissal
  const pending = messages.find((m) => !state.dismissedMessages.has(m));
  if (pending !== undefined) {
    showMessageModal(pending);
  }
}

function showMessageModal(message) {
  if (!messageModal || !messageModalText) return;
  messageModalText.textContent = message;
  messageModal.showModal();
}

async function submitDismissMessageRequest(message) {
  if (!state.userId) return;
  await submitRequest({
    requestId: `dismiss-msg-${state.userId}`,
    requestType: "dismiss_message",
    clientRequestPayload: {
      targetId: state.userId,
    },
    properties: {
      formData: { message },
    },
    quiet: true,
  });
}

// Wire up the OK button once
if (messageModalOk) {
  messageModalOk.addEventListener("click", async () => {
    const message = messageModalText?.textContent ?? "";
    messageModal.close();

    // Optimistically remove from local state so the next check won't re-show it
    // before the DB update echoes back.
    state.dismissedMessages.add(message);
    const userObj = state.objects[state.userId];
    if (userObj?.properties?.messages) {
      const idx = userObj.properties.messages.indexOf(message);
      if (idx !== -1) {
        userObj.properties.messages.splice(idx, 1);
      }
    }

    await submitDismissMessageRequest(message);

    // Show next pending message, if any
    checkForUserMessages();
  });
}

// ---------------------------------------------------------------------------
// Criteria editor functions
// ---------------------------------------------------------------------------

function normalizeNonGeoEntry(key, entry) {
  if (!entry || typeof entry !== "object") return null;
  const properties = entry.properties && typeof entry.properties === "object" ? entry.properties : {};
  return {
    type: entry.type || "Feature",
    geometry: null,
    properties: { ...properties, id: properties.id || key },
  };
}

function normalizeCollection(raw, normFn) {
  if (!raw || typeof raw !== "object") return {};
  return Object.entries(raw).reduce((acc, [key, entry]) => {
    const normalized = normFn(key, entry);
    if (normalized) acc[key] = normalized;
    return acc;
  }, {});
}

function renderCriterionRowsInto(listEl, components, options) {
  if (!listEl) return;
  const entries = Object.entries(components || {});
  if (!entries.length) {
    listEl.innerHTML = '<div class="stats-empty">No criteria yet. Add one to define matching rules.</div>';
    return;
  }

  listEl.innerHTML = entries
    .map(([name, data], index) => {
      const tags = Array.isArray(data?.tags) ? data.tags.join(", ") : "";
      return `
        <article class="stat-row" data-criterion-index="${index}" data-criterion-name="${escapeHtml(name)}">
          <div class="criterion-row-grid">
            <label>
              <select data-field="name">
                ${(options || CRITERIA_COMPONENT_OPTIONS).map((opt) => `<option value="${opt}"${opt === name ? " selected" : ""}>${opt}</option>`).join("")}
              </select>
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

function addEmptyCriterionRowTo(listEl, options) {
  if (!listEl) return;
  const currentComponents = collectCriteriaComponentsFrom(listEl);
  const nextComponents = { ...currentComponents };
  const opts = options || CRITERIA_COMPONENT_OPTIONS;
  const nextKey =
    opts.find((opt) => !Object.prototype.hasOwnProperty.call(nextComponents, opt)) ??
    opts[0];
  nextComponents[nextKey] = { tags: [] };
  renderCriterionRowsInto(listEl, nextComponents, opts);
  applyEventEditorPermissions();
}

function collectCriteriaComponentsFrom(listEl) {
  if (!listEl) return {};
  const rows = Array.from(listEl.querySelectorAll(".stat-row"));
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

function extractCriteriaComponents(properties, allowedNames) {
  if (!properties || typeof properties !== "object") return {};
  const knownNames = new Set(allowedNames || CRITERIA_COMPONENT_OPTIONS);
  const components = {};
  for (const [key, value] of Object.entries(properties)) {
    if (knownNames.has(key) && value && typeof value === "object") {
      components[key] = value;
    }
  }
  return components;
}

function handleCriteriaSnapshot(nextCriteria) {
  state.criteria = normalizeCollection(nextCriteria, normalizeNonGeoEntry);
}

function getRequestCoordinates() {
  return Array.isArray(state.userLocation)
    ? [state.userLocation[1], state.userLocation[0]]
    : [0, 0];
}

// ---------------------------------------------------------------------------
// Event results system
// ---------------------------------------------------------------------------

function buildDefaultResultData(componentName) {
  const config = RESULT_COMPONENT_FIELD_CONFIG[componentName];
  if (!config) return {};
  if (config.fieldType === "bool") return { [config.fieldName]: true };
  if (config.fieldType === "number") return { [config.fieldName]: 0 };
  if (config.fieldType === "csv") return { [config.fieldName]: [] };
  if (config.fieldType === "json") return { [config.fieldName]: {} };
  return { [config.fieldName]: "" };
}

function renderResultValueField(componentName, data) {
  const config = RESULT_COMPONENT_FIELD_CONFIG[componentName];
  if (!config) return '<input type="text" data-field="value" value="" />';
  const { fieldName, fieldType, label, placeholder = "" } = config;
  const rawValue = data != null && typeof data === "object" ? data[fieldName] : undefined;
  if (fieldType === "bool") {
    const val = rawValue === false ? "false" : "true";
    return `
      <label>
        ${escapeHtml(label)}
        <select data-field="value">
          <option value="true"${val === "true" ? " selected" : ""}>true</option>
          <option value="false"${val === "false" ? " selected" : ""}>false</option>
        </select>
      </label>`;
  }
  if (fieldType === "number") {
    const val = rawValue != null ? String(rawValue) : "0";
    return `
      <label>
        ${escapeHtml(label)}
        <input type="number" data-field="value" value="${escapeHtml(val)}" placeholder="${escapeHtml(placeholder)}" />
      </label>`;
  }
  if (fieldType === "csv") {
    const val = Array.isArray(rawValue) ? rawValue.join(", ") : (rawValue != null ? String(rawValue) : "");
    return `
      <label>
        ${escapeHtml(label)}
        <input type="text" data-field="value" value="${escapeHtml(val)}" placeholder="${escapeHtml(placeholder)}" />
      </label>`;
  }
  if (fieldType === "json") {
    let val = "";
    if (rawValue != null && typeof rawValue === "object") {
      try { val = JSON.stringify(rawValue); } catch (e) { val = "{}"; }
    } else if (typeof rawValue === "string") {
      val = rawValue;
    } else {
      val = "{}";
    }
    return `
      <label>
        ${escapeHtml(label)}
        <input type="text" data-field="value" value="${escapeHtml(val)}" placeholder="${escapeHtml(placeholder)}" />
      </label>`;
  }
  const val = rawValue != null ? String(rawValue) : "";
  return `
    <label>
      ${escapeHtml(label)}
      <input type="text" data-field="value" value="${escapeHtml(val)}" placeholder="${escapeHtml(placeholder)}" />
    </label>`;
}

function renderEventResultsEditor(results) {
  if (!eventResultsList) return;
  const entries = Object.entries(results || {});
  if (!entries.length) {
    eventResultsList.innerHTML = '<div class="stats-empty">No results yet. Add one to define actions.</div>';
    return;
  }
  eventResultsList.innerHTML = entries
    .map(([name, data], index) => {
      return `
        <article class="stat-row" data-result-index="${index}" data-result-name="${escapeHtml(name)}">
          <div class="result-row-grid">
            <label>
              <select data-field="name">
                ${RESULT_COMPONENT_OPTIONS.map((opt) => `<option value="${opt}"${opt === name ? " selected" : ""}>${opt}</option>`).join("")}
              </select>
            </label>
            ${renderResultValueField(name, data)}
            <button class="stat-remove-button" type="button" data-action="remove-result" aria-label="Remove result">✕</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function addEmptyResultRow() {
  const currentResults = collectResultsFromEditor();
  const nextResults = { ...currentResults };
  const nextKey =
    RESULT_COMPONENT_OPTIONS.find((opt) => !Object.prototype.hasOwnProperty.call(nextResults, opt)) ??
    RESULT_COMPONENT_OPTIONS[0];
  nextResults[nextKey] = buildDefaultResultData(nextKey);
  renderEventResultsEditor(nextResults);
  applyEventEditorPermissions();
}

function collectResultsFromEditor() {
  const rows = Array.from(eventResultsList?.querySelectorAll(".stat-row") || []);
  const results = {};
  for (const row of rows) {
    const name = row.querySelector('[data-field="name"]')?.value?.trim() || "";
    const valueEl = row.querySelector('[data-field="value"]');
    if (!name || !valueEl) continue;
    const config = RESULT_COMPONENT_FIELD_CONFIG[name];
    if (!config) continue;
    const rawValue = valueEl.value?.trim() ?? "";
    let parsedValue;
    if (config.fieldType === "bool") {
      parsedValue = rawValue === "true";
    } else if (config.fieldType === "number") {
      parsedValue = parseInt(rawValue, 10) || 0;
    } else if (config.fieldType === "csv") {
      parsedValue = rawValue.split(",").map((s) => s.trim()).filter(Boolean);
    } else if (config.fieldType === "json") {
      try { parsedValue = JSON.parse(rawValue); } catch (e) { parsedValue = {}; }
    } else {
      parsedValue = rawValue;
    }
    results[name] = { [config.fieldName]: parsedValue };
  }
  return results;
}

function renderEventList() {
  if (!eventsList) return;
  const entries = Object.values(state.events);
  eventsList.innerHTML = entries.length
    ? entries
        .map((entry) => {
          const id = entry.properties?.id;
          const name = escapeHtml(entry.properties?.displayName || id || "Unnamed event");
          const selectedClass = state.selectedEventId === id ? "is-selected" : "";
          return `
            <li>
              <button class="${selectedClass}" type="button" data-event-id="${escapeHtml(id)}">
                <span>${name}</span><span class="list-meta"> &middot; ${escapeHtml(id)}</span>
              </button>
            </li>
          `;
        })
        .join("")
    : "<li>No events found.</li>";
}

function selectEvent(id) {
  const entry = state.events[id];
  if (!entry) return;
  state.selectedEventId = id;
  populateEventEditor(id);
  renderEventList();
  setDrawerOpen(eventsResultsDrawer, eventsResultsDrawerToggle, true);
}


function extractEventResults(properties) {
  if (!properties || typeof properties !== "object") return {};
  const results = properties.Results;
  if (!results || typeof results !== "object") return {};
  const knownNames = new Set(RESULT_COMPONENT_OPTIONS);
  const out = {};
  for (const [key, value] of Object.entries(results)) {
    if (knownNames.has(key) && value && typeof value === "object") {
      out[key] = value;
    }
  }
  return out;
}

function populateEventEditor(id) {
  const entry = state.events[id];
  if (!entry) {
    showEmptyEventEditor();
    return;
  }
  const displayName = entry.properties?.displayName || "";
  const triggerComponents = extractCriteriaComponents(entry.properties, TRIGGER_COMPONENT_OPTIONS);
  const targetComponents = extractCriteriaComponents(entry.properties, TARGET_COMPONENT_OPTIONS);
  const results = extractEventResults(entry.properties);
  eventEditorForm.hidden = false;
  eventEditorForm.classList.remove("is-collapsed");
  eventEditorEmptyState.textContent = `Editing ${displayName || id}`;
  eventFieldName.value = displayName;
  renderCriterionRowsInto(triggerCriteriaList, triggerComponents, TRIGGER_COMPONENT_OPTIONS);
  renderCriterionRowsInto(targetCriteriaList, targetComponents, TARGET_COMPONENT_OPTIONS);
  renderEventResultsEditor(results);
  applyEventEditorPermissions();
}

function showEmptyEventEditor() {
  if (eventEditorForm) {
    eventEditorForm.hidden = true;
    eventEditorForm.classList.add("is-collapsed");
  }
  if (eventEditorEmptyState) eventEditorEmptyState.textContent = "Select an event to edit.";
  if (eventSaveStatus) eventSaveStatus.textContent = "";
  renderCriterionRowsInto(triggerCriteriaList, {}, TRIGGER_COMPONENT_OPTIONS);
  renderCriterionRowsInto(targetCriteriaList, {}, TARGET_COMPONENT_OPTIONS);
  renderEventResultsEditor({});
  applyEventEditorPermissions();
}

function applyEventEditorPermissions() {
  const isEditable = canEditObjects();
  eventEditableFields.forEach((field) => {
    if (field) field.disabled = !isEditable;
  });
  const isFormVisible = eventEditorForm && !eventEditorForm.hidden;
  if (deleteEventButton) {
    deleteEventButton.disabled = !isEditable || !isFormVisible;
  }
  const saveButton = eventEditorForm?.querySelector('button[type="submit"]');
  if (saveButton) {
    saveButton.disabled = !isEditable || !isFormVisible;
  }
  if (addResultButton) {
    addResultButton.disabled = !isEditable || !isFormVisible;
  }
  if (addTriggerCriterionButton) {
    addTriggerCriterionButton.disabled = !isEditable || !isFormVisible;
  }
  if (addTargetCriterionButton) {
    addTargetCriterionButton.disabled = !isEditable || !isFormVisible;
  }
  eventResultsList?.querySelectorAll("input, select, button").forEach((el) => {
    el.disabled = !isEditable || !isFormVisible;
  });
  triggerCriteriaList?.querySelectorAll("input, select, button").forEach((el) => {
    el.disabled = !isEditable || !isFormVisible;
  });
  targetCriteriaList?.querySelectorAll("input, select, button").forEach((el) => {
    el.disabled = !isEditable || !isFormVisible;
  });
}

function handleEventSnapshot(nextEvents) {
  state.events = normalizeCollection(nextEvents, normalizeNonGeoEntry);
  renderEventList();

  if (state.selectedEventId && !state.events[state.selectedEventId]) {
    state.selectedEventId = null;
  }

  if (state.selectedEventId) {
    populateEventEditor(state.selectedEventId);
  } else {
    showEmptyEventEditor();
  }
}



async function submitAddEventRequest() {
  await submitRequest({
    requestId: "add_event",
    requestType: "add_event",
    coordinates: getRequestCoordinates(),
    successMessage: "Add event request sent",
  });
}

async function submitEditedEventRequest(targetId, formData) {
  await submitRequest({
    requestId: `edit-event-${targetId}`,
    requestType: "edited_event",
    coordinates: getRequestCoordinates(),
    clientRequestPayload: { targetId },
    properties: { formData },
    successMessage: `Edit event request for ${targetId} sent`,
  });
}

async function submitDeletedEventRequest(targetId) {
  await submitRequest({
    requestId: `delete-event-${targetId}`,
    requestType: "deleted_event",
    coordinates: getRequestCoordinates(),
    clientRequestPayload: { targetId },
    successMessage: `Delete event request for ${targetId} sent`,
  });
}

async function init() {
  const [criteriaRes, resultRes, fbConfigRes] = await Promise.all([
    fetch("map_criteria_components.json"),
    fetch("map_result_components.json"),
    fetch("online_config.json"),
  ]);
  const criteriaJson = await criteriaRes.json();
  CRITERIA_COMPONENT_OPTIONS = Object.keys(criteriaJson);
  TRIGGER_COMPONENT_OPTIONS = Object.entries(criteriaJson).filter(([, m]) => m.role === "trigger").map(([k]) => k);
  TARGET_COMPONENT_OPTIONS = Object.entries(criteriaJson).filter(([, m]) => m.role === "target").map(([k]) => k);
  RESULT_COMPONENT_FIELD_CONFIG = await resultRes.json();
  RESULT_COMPONENT_OPTIONS = Object.keys(RESULT_COMPONENT_FIELD_CONFIG);
  const { nodes, defaultSessionName, updateLocationInterval, mapLayer, ...fbSdkConfig } = await fbConfigRes.json();
  firebaseConfig = fbSdkConfig;
  firebaseGeoObjectsNode = nodes.geoObjects;
  firebaseClientRequestNode = nodes.clientRequests;
  firebaseEventCriteriaNode = nodes.eventCriteria;
  firebaseEventResultsNode = nodes.eventResults;
  state.sessionName = defaultSessionName || "testBed";
  state.updateLocationInterval = updateLocationInterval || 2000;
  state.mapLayer = mapLayer?.default?.url || "";
  state.mapLayerAttribution = mapLayer?.default?.attribution || "";
  loadCollapseState();
  applyCollapseState();
  initMap();
  bindUi();
  locateUser();
  initFirebaseListener();
  promptUserId();
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
    if (!editorForm.hidden && state.selectedId) {
      editorForm.requestSubmit();
    }
  });


  L.tileLayer(state.mapLayer, {
    attribution: state.mapLayerAttribution,
    maxZoom: 19,
    minZoom: 12,
  }).addTo(state.map);
}

function bindUi() {
  drawerToggle.addEventListener("click", () => setDrawerOpen(drawer, drawerToggle, !drawer.classList.contains("is-open")));
  drawerClose.addEventListener("click", () => { setDrawerOpen(drawer, drawerToggle, false); closeEditorPanel(); });
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
  editorCancelButton?.addEventListener("click", () => closeEditorPanel());
  editorCancelBottomButton?.addEventListener("click", () => closeEditorPanel());
  coordPickButton?.addEventListener("click", () => {
    const entering = !state.coordPickMode;
    setCoordPickMode(entering);
    if (entering) {
      setDrawerOpen(drawer, drawerToggle, false);
    }
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
  eventsResultsDrawerToggle?.addEventListener("click", () => {
    setDrawerOpen(eventsResultsDrawer, eventsResultsDrawerToggle, !eventsResultsDrawer?.classList.contains("is-open"));
  });
  eventsResultsDrawerClose?.addEventListener("click", () => setDrawerOpen(eventsResultsDrawer, eventsResultsDrawerToggle, false));
  addEventButton?.addEventListener("click", () => {
    void submitAddEventRequest();
  });
  addTriggerCriterionButton?.addEventListener("click", () => addEmptyCriterionRowTo(triggerCriteriaList, TRIGGER_COMPONENT_OPTIONS));
  addTargetCriterionButton?.addEventListener("click", () => addEmptyCriterionRowTo(targetCriteriaList, TARGET_COMPONENT_OPTIONS));
  triggerCriteriaList?.addEventListener("click", (event) => {
    const button = event.target.closest('button[data-action="remove-criterion"]');
    if (!button) return;
    button.closest(".stat-row")?.remove();
    if (!triggerCriteriaList.querySelector(".stat-row")) {
      renderCriterionRowsInto(triggerCriteriaList, {}, TRIGGER_COMPONENT_OPTIONS);
    }
    applyEventEditorPermissions();
  });
  targetCriteriaList?.addEventListener("click", (event) => {
    const button = event.target.closest('button[data-action="remove-criterion"]');
    if (!button) return;
    button.closest(".stat-row")?.remove();
    if (!targetCriteriaList.querySelector(".stat-row")) {
      renderCriterionRowsInto(targetCriteriaList, {}, TARGET_COMPONENT_OPTIONS);
    }
    applyEventEditorPermissions();
  });
  addResultButton?.addEventListener("click", () => {
    addEmptyResultRow();
  });
  eventResultsList?.addEventListener("click", (event) => {
    const button = event.target.closest('button[data-action="remove-result"]');
    if (!button) return;
    button.closest(".stat-row")?.remove();
    if (!eventResultsList.querySelector(".stat-row")) {
      renderEventResultsEditor({});
    }
    applyEventEditorPermissions();
  });
  eventResultsList?.addEventListener("change", (event) => {
    const select = event.target.closest('select[data-field="name"]');
    if (!select) return;
    const row = select.closest(".stat-row");
    const oldName = row?.dataset.resultName || "";
    const newName = select.value;
    if (oldName === newName) return;
    const currentResults = collectResultsFromEditor();
    const nextResults = {};
    for (const [k, v] of Object.entries(currentResults)) {
      if (k === oldName) {
        nextResults[newName] = buildDefaultResultData(newName);
      } else {
        nextResults[k] = v;
      }
    }
    renderEventResultsEditor(nextResults);
    applyEventEditorPermissions();
  });
  eventsList?.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-event-id]");
    if (!button) return;
    selectEvent(button.dataset.eventId);
  });
  eventEditorForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canEditObjects()) {
      if (eventSaveStatus) eventSaveStatus.textContent = "Read-only mode: editing requires gm password.";
      return;
    }
    if (!state.selectedEventId) return;
    const eventEntry = state.events[state.selectedEventId];
    if (!eventEntry) return;

    const formData = {
      name: eventFieldName?.value.trim() || "",
      triggerComponents: collectCriteriaComponentsFrom(triggerCriteriaList),
      targetComponents: collectCriteriaComponentsFrom(targetCriteriaList),
      results: collectResultsFromEditor(),
    };

    if (eventSaveStatus) eventSaveStatus.textContent = state.firebaseReady ? "Sending edit request..." : "Saving...";
    try {
      await submitEditedEventRequest(state.selectedEventId, formData);
      if (eventSaveStatus) eventSaveStatus.textContent = state.firebaseReady
        ? "Edit request sent. Server will apply updates shortly."
        : "Saved locally.";
    } catch (error) {
      console.error(error);
      if (eventSaveStatus) eventSaveStatus.textContent = "Edit request failed. Check Firebase configuration and permissions.";
    }
  });
  deleteEventButton?.addEventListener("click", async () => {
    if (!canEditObjects()) {
      if (eventSaveStatus) eventSaveStatus.textContent = "Read-only mode: deleting requires gm password.";
      return;
    }
    if (!state.selectedEventId || !state.events[state.selectedEventId]) {
      if (eventSaveStatus) eventSaveStatus.textContent = "Delete failed: no event selected.";
      return;
    }
    const deletingId = state.selectedEventId;
    if (eventSaveStatus) eventSaveStatus.textContent = state.firebaseReady ? "Sending delete request..." : "Deleting...";
    try {
      await submitDeletedEventRequest(deletingId);
      if (eventSaveStatus) eventSaveStatus.textContent = state.firebaseReady
        ? "Delete request sent. Server will remove the event shortly."
        : "Deleted locally.";
    } catch (error) {
      console.error(error);
      if (eventSaveStatus) eventSaveStatus.textContent = "Delete request failed. Check Firebase configuration and permissions.";
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
        displayName: fieldName.value.trim() || objectEntry.properties?.displayName || state.selectedId,
        appearance: {
          ...objectEntry.properties?.appearance,
          color: fieldColor.value,
          visibleTo: parseVisibleList(fieldVisible.value),
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

function setDrawerOpen(drawerEl, toggleEl, isOpen) {
  drawerEl?.classList.toggle("is-open", isOpen);
  toggleEl?.setAttribute("aria-expanded", String(isOpen));
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
        startCoordinateTracking();
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

    resetListener(firebaseGeoObjectsNode, "listenerUnsubscribe", handleObjectSnapshot);
    resetListener(firebaseEventCriteriaNode, "criteriaListenerUnsubscribe", handleCriteriaSnapshot);
    resetListener(firebaseEventResultsNode, "eventListenerUnsubscribe", handleEventSnapshot);
    modal.hidden = true;

    // Defer startCoordinateTracking until the first Firebase
    // snapshot arrives in handleObjectSnapshot, so existing data is not overwritten.
    state.pendingUserSetup = true;
  });
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

      state.objects[state.userId] = updated;
      renderLayer();
    }

    void submitRequest({
      requestId: "new_location",
      requestType: "new_location",
      coordinates: [lng, lat],
      quiet: true,
    });
  }, state.updateLocationInterval);
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
  resetListener(firebaseGeoObjectsNode, "listenerUnsubscribe", handleObjectSnapshot);
  resetListener(firebaseEventCriteriaNode, "criteriaListenerUnsubscribe", handleCriteriaSnapshot);
  resetListener(firebaseEventResultsNode, "eventListenerUnsubscribe", handleEventSnapshot);
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
    await update(ref(state.database, getFirebasePath(firebaseClientRequestNode)), {
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
    visibleTo: parseVisibleList(fieldVisible.value),
    traits: parseVisibleList(fieldTraits.value),
    latitude: coordDisplayLat.textContent.replace(/^Lat:\s*/i, "").trim(),
    longitude: coordDisplayLng.textContent.replace(/^Lng:\s*/i, "").trim(),
    radius: fieldRadius.value.trim(),
    stats: nextEntry?.properties?.stats || {},
  };

  await submitRequest({
    requestId: `edit-${targetId}`,
    requestType: "edited_object",
    coordinates,
    clientRequestPayload: {
      targetId,
      targetPath: `${getFirebasePath(firebaseGeoObjectsNode)}/${targetId}`,
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
      targetPath: `${getFirebasePath(firebaseGeoObjectsNode)}/${targetId}`,
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
      startCoordinateTracking();
    } else {
      startCoordinateTracking();
    }
  }

  if (state.selectedId && !state.objects[state.selectedId]) {
    closeEditorPanel();
  } else if (state.selectedId) {
    populateEditor(state.selectedId);
  } else {
    showEmptyEditor();
  }

  // Reapply collapse state after editor updates
  applyCollapseState();

  // Clear dismissed-message tracking for messages that were removed from the DB,
  // then check whether any new messages arrived for the current user.
  if (state.userId) {
    const currentMessages = new Set(state.objects[state.userId]?.properties?.messages ?? []);
    for (const msg of state.dismissedMessages) {
      if (!currentMessages.has(msg)) {
        state.dismissedMessages.delete(msg);
      }
    }
    checkForUserMessages();
  }
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
  const visibleTo = feature.properties?.appearance?.visibleTo;
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

  return `
    <div>
      <strong>${escapeHtml(properties.displayName || properties.id || "Untitled object")}</strong>
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
          const name = escapeHtml(feature.properties?.displayName || id || "Unnamed object");

          return `
            <li>
              <button class="${selectedClass}" type="button" data-id="${escapeHtml(id)}">
                <span class="list-color-dot" style="background: ${escapeHtml(color)};"></span>
                <span>${name}</span>
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
  showEditorPanel();
  renderObjectList();
  setDrawerOpen(drawer, drawerToggle, true);

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

  const displayName = feature.properties?.displayName || "";
  const stats = normalizeStats(feature.properties);
  editorForm.hidden = false;
  setEditorFormCollapsed(false);
  editorEmptyState.textContent = `Editing ${displayName || id}`;
  fieldName.value = displayName;
  fieldColor.value = feature.properties?.appearance?.color || "#0b8f87";
  const rawVisible = feature.properties?.appearance?.visibleTo;
  fieldVisible.value = Array.isArray(rawVisible) ? rawVisible.join(", ") : "";
  const rawTraits = feature.properties?.traits;
  fieldTraits.value = Array.isArray(rawTraits) ? rawTraits.join(", ") : "";
  coordDisplayLat.textContent = feature.geometry?.coordinates ? `Lat: ${feature.geometry.coordinates[1]}` : "Lat: --";
  coordDisplayLng.textContent = feature.geometry?.coordinates ? `Lng: ${feature.geometry.coordinates[0]}` : "Lng: --";
  fieldRadius.value = Number.isFinite(feature.properties?.appearance?.radius) ? String(feature.properties.appearance.radius) : "";
  renderStatsEditor(stats);
  applyEditorPermissions();
}

function showEmptyEditor() {
  editorForm.hidden = true;
  setEditorFormCollapsed(true);
  editorEmptyState.textContent = "Select an object from the list.";
  saveStatus.textContent = "";
  renderStatsEditor({});
  applyEditorPermissions();
}

function showEditorPanel() {
  editorPanel.classList.add("is-open");
}

function closeEditorPanel() {
  editorPanel.classList.remove("is-open");
  state.selectedId = null;
  showEmptyEditor();
  renderObjectList();
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

function getFirebasePath(node) {
  return `${state.sessionName}/${node}`;
}

function resetListener(node, stateKey, handler) {
  if (!state.firebaseReady || !state.database) return;
  if (typeof state[stateKey] === "function") {
    state[stateKey]();
    handler({});
  }
  state[stateKey] = onValue(ref(state.database, getFirebasePath(node)), (snapshot) => {
    if (state.listenerActive) handler(snapshot.val() || {});
  });
}