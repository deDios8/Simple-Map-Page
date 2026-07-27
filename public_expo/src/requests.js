// Every user-initiated write goes through submitRequest(), which writes one
// entry to `{sessionName}/zzz_clientRequests`. The Python backend (server/)
// watches that node, applies the change, and updates `zones`/`events` - the
// client never writes to zones/events directly.
import { ref, update } from "firebase/database";
import { database, dbPath, NODES } from "./firebase";

export async function submitRequest(
  sessionName,
  { requestId, requestType, userId, coordinates, clientRequestPayload = {}, properties = {}, quiet = false },
) {
  if (!userId) {
    throw new Error("Request unavailable: enter your ID first.");
  }
  if (!Array.isArray(coordinates) || coordinates.length < 2) {
    throw new Error("Request unavailable: invalid coordinates.");
  }

  const timestamp = new Date().toISOString();
  const requestKey = `${Date.now()}-${userId}-${String(requestType)}`.replace(/\s+/g, "-");
  const requestFeature = {
    type: "Feature",
    geometry: { type: "Point", coordinates },
    properties: {
      id: requestKey,
      ...properties,
      clientRequestPayload: {
        requesterId: userId,
        timestamp,
        type: requestType,
        requestedAction: requestId,
        ...clientRequestPayload,
      },
    },
  };

  await update(ref(database, dbPath(sessionName, NODES.clientRequests)), {
    [requestKey]: requestFeature,
  });

  return { timestamp, quiet };
}

// [lat, lng] (as stored in app state) -> [lng, lat] (GeoJSON order for requests)
function toGeoJsonCoordinates(userLocation) {
  return Array.isArray(userLocation) ? [userLocation[1], userLocation[0]] : null;
}

export function submitNewLocationRequest(sessionName, userId, userLocation) {
  return submitRequest(sessionName, {
    requestId: "new_location",
    requestType: "new_location",
    userId,
    coordinates: toGeoJsonCoordinates(userLocation),
    quiet: true,
  });
}

export function submitButtonClickRequest(sessionName, userId, userLocation, requestId) {
  return submitRequest(sessionName, {
    requestId,
    requestType: "button_click",
    userId,
    coordinates: toGeoJsonCoordinates(userLocation),
  });
}

export function submitAddZoneRequest(sessionName, userId, userLocation, formData = {}) {
  return submitRequest(sessionName, {
    requestId: "add_zone",
    requestType: "button_click",
    userId,
    coordinates: toGeoJsonCoordinates(userLocation),
    properties: { formData },
  });
}

export function submitEditedZoneRequest(sessionName, userId, targetId, formData, coordinates) {
  return submitRequest(sessionName, {
    requestId: `edit-${targetId}`,
    requestType: "edited_zone",
    userId,
    coordinates,
    clientRequestPayload: {
      targetId,
      targetPath: `${dbPath(sessionName, NODES.zones)}/${targetId}`,
    },
    properties: { formData },
  });
}

export function submitDeletedZoneRequest(sessionName, userId, targetId, coordinates) {
  return submitRequest(sessionName, {
    requestId: `delete-${targetId}`,
    requestType: "deleted_zone",
    userId,
    coordinates,
    clientRequestPayload: {
      targetId,
      targetPath: `${dbPath(sessionName, NODES.zones)}/${targetId}`,
    },
  });
}

export function submitClearLogsRequest(sessionName, userId, targetId, coordinates) {
  return submitRequest(sessionName, {
    requestId: `clear-logs-${targetId}`,
    requestType: "clear_logs",
    userId,
    coordinates,
    clientRequestPayload: {
      targetId,
      targetPath: `${dbPath(sessionName, NODES.zones)}/${targetId}`,
    },
  });
}

export function submitClearAllLogsRequest(sessionName, userId, userLocation) {
  return submitRequest(sessionName, {
    requestId: "clear-logs-all",
    requestType: "clear_logs_all",
    userId,
    coordinates: toGeoJsonCoordinates(userLocation),
  });
}

export function submitAddEventRequest(sessionName, userId, userLocation, formData = {}) {
  return submitRequest(sessionName, {
    requestId: "add_event",
    requestType: "add_event",
    userId,
    coordinates: toGeoJsonCoordinates(userLocation),
    properties: { formData },
  });
}

export function submitEditedEventRequest(sessionName, userId, targetId, formData, userLocation) {
  return submitRequest(sessionName, {
    requestId: `edit-event-${targetId}`,
    requestType: "edited_event",
    userId,
    coordinates: toGeoJsonCoordinates(userLocation),
    clientRequestPayload: { targetId },
    properties: { formData },
  });
}

export function submitDeletedEventRequest(sessionName, userId, targetId, userLocation) {
  return submitRequest(sessionName, {
    requestId: `delete-event-${targetId}`,
    requestType: "deleted_event",
    userId,
    coordinates: toGeoJsonCoordinates(userLocation),
    clientRequestPayload: { targetId },
  });
}

export function submitDismissMessageRequest(sessionName, userId, message, userLocation) {
  return submitRequest(sessionName, {
    requestId: `dismiss-msg-${userId}`,
    requestType: "dismiss_message",
    userId,
    coordinates: toGeoJsonCoordinates(userLocation),
    clientRequestPayload: { targetId: userId },
    properties: { formData: { message } },
    quiet: true,
  });
}
