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

const firebaseCollectionPath = "geoObjects";
const firebaseClientRequestPath = "clientRequests";

const demoGeoObjects = {
  downtown: {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [-101.31304, 48.21224],
    },
    properties: {
      id: "downtown",
      name: "Downtown Pin",
      visible: true,
      color: "#0b8f87",
      radius: 12,
      description: "Current point of interest.",
      extraData: {
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
      name: "Hidden Marker",
      visible: false,
      color: "#5e718c",
      radius: 8,
      description: "This stays hidden until visibility is enabled.",
      extraData: {
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
      name: "Staging Zone",
      visible: true,
      color: "#d2603f",
      description: "Rectangular work area.",
      extraData: {
        access: "restricted",
        supervisor: "Ops A",
      },
    },
  },
};

const state = {
  map: null,
  userMarker: null,
  geoJsonLayer: null,
  database: null,
  firebaseReady: false,
  objects: {},
  selectedId: null,
  userLocation: null,
  userId: null,
  trackingInterval: null,
  listenerActive: true,
  listenerUnsubscribe: null,
};

const locationStatus = document.querySelector("#location-status");
const drawer = document.querySelector("#drawer");
const drawerToggle = document.querySelector("#drawer-toggle");
const drawerClose = document.querySelector("#drawer-close");
const listenerToggle = document.querySelector("#listener-toggle");
const requestAButton = document.querySelector("#request-a-button");
const requestBButton = document.querySelector("#request-b-button");
const requestXButton = document.querySelector("#request-x-button");
const requestYButton = document.querySelector("#request-y-button");
const objectList = document.querySelector("#object-list");
const editorForm = document.querySelector("#editor-form");
const editorEmptyState = document.querySelector("#editor-empty-state");
const saveStatus = document.querySelector("#save-status");
const fieldName = document.querySelector("#field-name");
const fieldColor = document.querySelector("#field-color");
const fieldVisible = document.querySelector("#field-visible");
const fieldLatitude = document.querySelector("#field-latitude");
const fieldLongitude = document.querySelector("#field-longitude");
const fieldRadius = document.querySelector("#field-radius");
const fieldDescription = document.querySelector("#field-description");
const fieldExtra = document.querySelector("#field-extra");

init();

function init() {
  initMap();
  bindUi();
  locateUser();
  initFirebaseListener();
  promptUserId();
}

function initMap() {
  state.map = L.map("map", {
    zoomControl: false,
    tap: true,
  }).setView([48.21224, -101.31304], 14);

  L.control.zoom({ position: "topright" }).addTo(state.map);

  // L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  //   attribution: "&copy; OpenStreetMap contributors",
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    attribution:
      "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    maxZoom: 19,
    minZoom: 12,
  }).addTo(state.map);
}

function bindUi() {
  drawerToggle.addEventListener("click", () => setDrawerOpen(!drawer.classList.contains("is-open")));
  drawerClose.addEventListener("click", () => setDrawerOpen(false));
  listenerToggle.addEventListener("click", toggleListener);
  requestAButton.addEventListener("click", () => {
    void submitClientRequest("request A");
  });
  requestBButton.addEventListener("click", () => {
    void submitClientRequest("request B");
  });
  requestXButton.addEventListener("click", () => {
    void submitClientRequest("request X");
  });
  requestYButton.addEventListener("click", () => {
    void submitClientRequest("request Y");
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
    const currentCoordinates = objectEntry.geometry?.coordinates;
    const fallbackLatitude = Array.isArray(currentCoordinates) ? currentCoordinates[1] : null;
    const fallbackLongitude = Array.isArray(currentCoordinates) ? currentCoordinates[0] : null;
    const fallbackRadius = Number.isFinite(objectEntry.properties?.radius)
      ? objectEntry.properties.radius
      : null;
    const nextLatitude = Number.isFinite(parsedLatitude) ? parsedLatitude : fallbackLatitude;
    const nextLongitude = Number.isFinite(parsedLongitude) ? parsedLongitude : fallbackLongitude;
    const nextRadius = Number.isFinite(parsedRadius) ? parsedRadius : fallbackRadius;

    let nextGeometry = objectEntry.geometry;
    if (objectEntry.geometry?.type === "Point" && Number.isFinite(nextLatitude) && Number.isFinite(nextLongitude)) {
      nextGeometry = {
        ...objectEntry.geometry,
        coordinates: [nextLongitude, nextLatitude],
      };
    }

    const nextEntry = {
      ...objectEntry,
      geometry: nextGeometry,
      properties: {
        ...objectEntry.properties,
        name: fieldName.value.trim() || objectEntry.properties.name || state.selectedId,
        color: fieldColor.value,
        visible: fieldVisible.checked,
        latitude: nextLatitude,
        longitude: nextLongitude,
        radius: nextRadius,
        description: fieldDescription.value.trim(),
        extraData: parsedExtra,
      },
    };

    saveStatus.textContent = state.firebaseReady ? "Saving to Firebase..." : "Saving locally...";

    try {
      await persistObject(state.selectedId, nextEntry);
      saveStatus.textContent = state.firebaseReady
        ? "Saved. Remote updates will sync automatically."
        : "Saved locally. Add Firebase config to sync remotely.";
    } catch (error) {
      console.error(error);
      saveStatus.textContent = "Save failed. Check Firebase configuration and permissions.";
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
      const latLng = [coords.latitude, coords.longitude];
      state.userLocation = latLng;

      if (state.userId && !state.objects[state.userId]) {
        createUserObject();
      } 
      if (state.userId && !state.trackingInterval) {
        startCoordinateTracking();
      }

      if (!state.userMarker) {
        state.userMarker = L.circleMarker(latLng, {
          radius: 9,
          color: "#12413a",
          weight: 2,
          fillColor: "#f9fffd",
          fillOpacity: 0.95,
        }).addTo(state.map);

        state.map.setView(latLng, 16);
      } else {
        state.userMarker.setLatLng(latLng);
      }

      locationStatus.textContent = `GPS locked: ${coords.latitude.toFixed(5)}, ${coords.longitude.toFixed(5)}`;
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

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.querySelector("#user-id-input");
    const id = input.value.trim();
    if (!id) {
      return;
    }

    state.userId = id;
    modal.hidden = true;

    if (state.userLocation) {
      if (!state.objects[state.userId]) {
        createUserObject();
      } else {
        startCoordinateTracking();
      }
    }
  });
}

function createUserObject() {
  if (!state.userId || !state.userLocation) {
    return;
  }

  const [lat, lng] = state.userLocation;

  const userFeature = {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [lng, lat],
    },
    properties: {
      id: state.userId,
      name: state.userId,
      visible: true,
      color: "#000000",
      radius: 9,
      description: "Live user location.",
      extraData: {},
    },
  };

  persistObject(state.userId, userFeature);
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

    const existing = state.objects[state.userId];
    if (!existing) {
      return;
    }

    const [lat, lng] = state.userLocation;

    const updated = {
      ...existing,
      geometry: {
        ...existing.geometry,
        coordinates: [lng, lat],
      },
    };

    state.objects[state.userId] = updated;
    renderLayer();

    if (state.firebaseReady && state.database) {
      update(ref(state.database, firebaseCollectionPath), { [state.userId]: updated });
    }
  }, 2000);
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
  const objectRef = ref(state.database, firebaseCollectionPath);  

  state.firebaseReady = true;

  state.listenerUnsubscribe = onValue(objectRef, (snapshot) => {
    if (state.listenerActive) {
      applyObjects(snapshot.val() || {});
    }
  });
}

function toggleListener() {
  state.listenerActive = !state.listenerActive;
  listenerToggle.setAttribute("data-state", state.listenerActive ? "active" : "paused");
  listenerToggle.textContent = state.listenerActive ? "pause db" : "resume db";
  listenerToggle.setAttribute("title", state.listenerActive ? "Pause Firebase listener" : "Resume Firebase listener");
}

async function submitClientRequest(requestId) {
  if (!state.firebaseReady || !state.database) {
    locationStatus.textContent = "Request unavailable: Firebase is not ready.";
    return;
  }

  if (!state.userId) {
    locationStatus.textContent = "Request unavailable: enter your ID first.";
    return;
  }

  if (!state.userLocation) {
    locationStatus.textContent = "Request unavailable: waiting for location fix.";
    return;
  }

  const [lat, lng] = state.userLocation;
  const timestamp = new Date().toISOString();
  const requestKey = `${Date.now()}-${requestId.replace(/\s+/g, "-")}`;
  const requestFeature = {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [lng, lat],
    },
    properties: {
      timestamp,
      requesterId: state.userId,
      id: requestId,
    },
  };

  try {
    await update(ref(state.database, firebaseClientRequestPath), {
      [requestKey]: requestFeature,
    });
    locationStatus.textContent = `${requestId} sent at ${timestamp}`;
  } catch (error) {
    console.error(error);
    locationStatus.textContent = "Request failed. Check Firebase permissions and connection.";
  }
}

function applyObjects(nextObjects) {
  state.objects = normalizeObjects(nextObjects);
  renderLayer();
  renderObjectList();

  if (state.selectedId && !state.objects[state.selectedId]) {
    state.selectedId = null;
  }

  if (state.selectedId) {
    populateEditor(state.selectedId);
  } else {
    showEmptyEditor();
  }
}

function normalizeObjects(rawObjects) {
  if (Array.isArray(rawObjects)) {
    return rawObjects.reduce((accumulator, entry, index) => {
      if (!entry) {
        return accumulator;
      }

      const id = entry.properties?.id || `item-${index}`;
      accumulator[id] = {
        ...entry,
        properties: {
          ...entry.properties,
          id,
        },
      };
      return accumulator;
    }, {});
  }

  return Object.entries(rawObjects).reduce((accumulator, [key, entry]) => {
    if (!entry) {
      return accumulator;
    }

    accumulator[key] = {
      ...entry,
      properties: {
        ...entry.properties,
        id: entry.properties?.id || key,
      },
    };
    return accumulator;
  }, {});
}

function renderLayer() {
  if (state.geoJsonLayer) {
    state.geoJsonLayer.remove();
  }

  const visibleFeatures = Object.values(state.objects).filter((feature) => feature.properties?.visible);

  state.geoJsonLayer = L.geoJSON(visibleFeatures, {
    pointToLayer: (feature, latlng) => L.circleMarker(latlng, pointStyle(feature)),
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
  const color = feature.properties?.color || "#0b8f87";
  const radius = Number.isFinite(feature.properties?.radius) ? feature.properties.radius : 9;
  return {
    radius,
    color,
    fillColor: color,
    fillOpacity: 0.85,
    weight: 2,
  };
}

function polygonStyle(feature) {
  const color = feature.properties?.color || "#0b8f87";
  return {
    color,
    fillColor: color,
    fillOpacity: 0.22,
    weight: 2,
  };
}

function buildPopupMarkup(feature) {
  const properties = feature.properties || {};
  const extraData = properties.extraData || {};
  const extraItems = Object.entries(extraData)
    .map(([key, value]) => `<li><strong>${escapeHtml(key)}:</strong> ${escapeHtml(String(value))}</li>`)
    .join("");

  return `
    <div>
      <strong>${escapeHtml(properties.name || properties.id || "Untitled object")}</strong>
      <p>${escapeHtml(properties.description || "No description available.")}</p>
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
          const color = feature.properties?.color || "#0b8f87";
          const visible = feature.properties?.visible ? "Visible" : "Hidden";
          const selectedClass = state.selectedId === id ? "is-selected" : "";
          const name = escapeHtml(feature.properties?.name || id || "Unnamed object");
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

  editorForm.hidden = false;
  editorEmptyState.textContent = `Editing ${feature.properties?.name || id}`;
  fieldName.value = feature.properties?.name || "";
  fieldColor.value = feature.properties?.color || "#0b8f87";
  fieldVisible.checked = Boolean(feature.properties?.visible);
  fieldLatitude.value = feature.geometry?.coordinates ? String(feature.geometry.coordinates[1]) : "";
  fieldLongitude.value = feature.geometry?.coordinates ? String(feature.geometry.coordinates[0]) : "";
  fieldRadius.value = Number.isFinite(feature.properties?.radius) ? String(feature.properties.radius) : "";
  fieldDescription.value = feature.properties?.description || "";
  fieldExtra.value = JSON.stringify(feature.properties?.extraData || {}, null, 2);
}

function showEmptyEditor() {
  editorForm.hidden = true;
  editorEmptyState.textContent = "Select an object from the list.";
  saveStatus.textContent = "";
}

async function persistObject(id, nextEntry) {
  if (state.firebaseReady && state.database) {
    await update(ref(state.database, firebaseCollectionPath), { [id]: nextEntry });
  }

  applyObjects({
    ...state.objects,
    [id]: nextEntry,
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