import { useEffect, useRef, useState } from "react";
import { useApp } from "../AppContext";
import {
  TRIGGER_COMPONENT_OPTIONS,
  TARGET_COMPONENT_OPTIONS,
  RESULT_COMPONENT_OPTIONS,
  RESULT_COMPONENT_FIELD_CONFIG,
} from "../config";
import { extractCriteriaComponents, extractResults, parseCsv } from "../eventUtils";
import { submitEditedEventRequest, submitDeletedEventRequest } from "../requests";
import CriteriaListEditor from "./CriteriaListEditor";
import ResultsEditor from "./ResultsEditor";

function nextAvailableOption(options, usedNames) {
  return options.find((option) => !usedNames.has(option)) ?? options[0];
}

function rawValueFromResultData(name, data) {
  const config = RESULT_COMPONENT_FIELD_CONFIG[name];
  if (!config) return "";
  const raw = data?.[config.fieldName];
  if (config.fieldType === "bool") return raw === false ? "false" : "true";
  if (config.fieldType === "number" || config.fieldType === "float") return raw != null ? String(raw) : "0";
  if (config.fieldType === "csv") return Array.isArray(raw) ? raw.join(", ") : raw != null ? String(raw) : "";
  if (config.fieldType === "json") {
    if (raw != null && typeof raw === "object") {
      try {
        return JSON.stringify(raw);
      } catch (error) {
        return "{}";
      }
    }
    return typeof raw === "string" ? raw : "{}";
  }
  return raw != null ? String(raw) : "";
}

function defaultRawValueForResult(name) {
  const config = RESULT_COMPONENT_FIELD_CONFIG[name];
  if (!config) return "";
  if (config.fieldType === "bool") return "true";
  if (config.fieldType === "number" || config.fieldType === "float") return "0";
  if (config.fieldType === "json") return "{}";
  return "";
}

function parseResultRawValue(name, rawValue) {
  const config = RESULT_COMPONENT_FIELD_CONFIG[name];
  if (!config) return {};
  const text = String(rawValue ?? "").trim();
  let parsed;
  if (config.fieldType === "bool") parsed = text === "true";
  else if (config.fieldType === "number") parsed = parseInt(text, 10) || 0;
  else if (config.fieldType === "float") parsed = parseFloat(text) || 0;
  else if (config.fieldType === "csv") parsed = parseCsv(text);
  else if (config.fieldType === "json") {
    try {
      parsed = JSON.parse(text);
    } catch (error) {
      parsed = {};
    }
  } else parsed = text;
  return { [config.fieldName]: parsed };
}

export default function EventEditor() {
  const { events, selectedEventId, selectEvent, isAdmin, sessionName, userId, userLocation } = useApp();
  const selectedEvent = selectedEventId ? events[selectedEventId] : null;

  const [name, setName] = useState("");
  const [triggerRows, setTriggerRows] = useState([]);
  const [targetRows, setTargetRows] = useState([]);
  const [resultRows, setResultRows] = useState([]);
  const [saveStatus, setSaveStatus] = useState("");

  // Snapshot of the form's values right after loading an event, used to tell
  // whether the user has changed anything yet (see isDirty below).
  const initialFormRef = useRef("");

  // Re-sync the form from the latest server data whenever it changes.
  useEffect(() => {
    if (!selectedEvent) return;
    const nextName = selectedEvent.properties?.displayName || "";

    const triggers = extractCriteriaComponents(selectedEvent.properties?.Triggers, TRIGGER_COMPONENT_OPTIONS);
    const nextTriggerRows = Object.entries(triggers).map(([rowName, data]) => ({
      name: rowName,
      tagsText: (Array.isArray(data?.tags) ? data.tags : []).join(", "),
    }));

    const targets = extractCriteriaComponents(selectedEvent.properties?.Targets, TARGET_COMPONENT_OPTIONS);
    const nextTargetRows = Object.entries(targets).map(([rowName, data]) => ({
      name: rowName,
      tagsText: (Array.isArray(data?.tags) ? data.tags : []).join(", "),
    }));

    const results = extractResults(selectedEvent.properties, RESULT_COMPONENT_OPTIONS);
    const nextResultRows = Object.entries(results).map(([rowName, data]) => ({
      name: rowName,
      rawValue: rawValueFromResultData(rowName, data),
    }));

    setName(nextName);
    setTriggerRows(nextTriggerRows);
    setTargetRows(nextTargetRows);
    setResultRows(nextResultRows);

    initialFormRef.current = JSON.stringify({
      name: nextName,
      triggerRows: nextTriggerRows,
      targetRows: nextTargetRows,
      resultRows: nextResultRows,
    });
  }, [selectedEvent]);

  // True once anything in the form differs from what it loaded with - drives
  // the Save button's styling (see the render below).
  const isDirty = initialFormRef.current !== JSON.stringify({ name, triggerRows, targetRows, resultRows });

  // Only clear the save-status message when the selection itself changes -
  // not on every snapshot refresh of the same event.
  useEffect(() => {
    setSaveStatus("");
  }, [selectedEventId]);

  if (!selectedEventId || !selectedEvent) {
    return (
      <div className="editor-panel">
        <div className="editor-panel-header">
          <h2>Select an event to edit.</h2>
        </div>
      </div>
    );
  }

  function addTriggerRow() {
    setTriggerRows((prev) => [
      ...prev,
      { name: nextAvailableOption(TRIGGER_COMPONENT_OPTIONS, new Set(prev.map((row) => row.name))), tagsText: "" },
    ]);
  }
  function addTargetRow() {
    setTargetRows((prev) => [
      ...prev,
      { name: nextAvailableOption(TARGET_COMPONENT_OPTIONS, new Set(prev.map((row) => row.name))), tagsText: "" },
    ]);
  }
  function addResultRow() {
    setResultRows((prev) => {
      const nextName = nextAvailableOption(RESULT_COMPONENT_OPTIONS, new Set(prev.map((row) => row.name)));
      return [...prev, { name: nextName, rawValue: defaultRawValueForResult(nextName) }];
    });
  }

  // Criteria/result rows are keyed by component name (one of each type per
  // event), so "duplicate" copies the row's other field but has to pick the
  // next unused name - same as the add-row functions above.
  function duplicateTriggerRow(index) {
    setTriggerRows((prev) => {
      const nextName = nextAvailableOption(TRIGGER_COMPONENT_OPTIONS, new Set(prev.map((row) => row.name)));
      return [...prev, { ...prev[index], name: nextName }];
    });
  }
  function duplicateTargetRow(index) {
    setTargetRows((prev) => {
      const nextName = nextAvailableOption(TARGET_COMPONENT_OPTIONS, new Set(prev.map((row) => row.name)));
      return [...prev, { ...prev[index], name: nextName }];
    });
  }
  function duplicateResultRow(index) {
    setResultRows((prev) => {
      const nextName = nextAvailableOption(RESULT_COMPONENT_OPTIONS, new Set(prev.map((row) => row.name)));
      return [...prev, { ...prev[index], name: nextName }];
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!isAdmin) {
      setSaveStatus("Read-only mode: editing requires gm password.");
      return;
    }

    const triggerComponents = {};
    for (const row of triggerRows) {
      triggerComponents[row.name] = { tags: parseCsv(row.tagsText) };
    }
    const targetComponents = {};
    for (const row of targetRows) {
      targetComponents[row.name] = { tags: parseCsv(row.tagsText) };
    }
    const results = {};
    for (const row of resultRows) {
      results[row.name] = parseResultRawValue(row.name, row.rawValue);
    }

    const formData = {
      name: name.trim(),
      triggerComponents,
      targetComponents,
      results,
    };

    setSaveStatus("Sending edit request...");
    try {
      await submitEditedEventRequest(sessionName, userId, selectedEventId, formData, userLocation);
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
      await submitDeletedEventRequest(sessionName, userId, selectedEventId, userLocation);
      setSaveStatus("Delete request sent. Server will remove the event shortly.");
    } catch (error) {
      console.error(error);
      setSaveStatus("Delete request failed. Check Firebase configuration and permissions.");
    }
  }

  return (
    <div className="editor-panel is-open">
      <div className="editor-panel-header">
        <label>
          <input
            type="text"
            placeholder="Event label"
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
              form="event-editor-form"
              disabled={!isAdmin}
            >
              Save
            </button>
            <button className="danger-button" type="button" disabled={!isAdmin} onClick={handleDelete}>
              Delete
            </button>
            <button className="text-button" type="button" onClick={() => selectEvent(null)}>
              Cancel
            </button>
          </div>
          <p className="save-status" aria-live="polite">
            {saveStatus}
          </p>
        </div>
      </div>
      <div className="editor-panel-body">
        <form id="event-editor-form" className="editor-form" onSubmit={handleSubmit}>
          <CriteriaListEditor
            heading="Trigger If..."
            addLabel="Add criterion"
            options={TRIGGER_COMPONENT_OPTIONS}
            rows={triggerRows}
            disabled={!isAdmin}
            onAdd={addTriggerRow}
            onDuplicate={duplicateTriggerRow}
            onRemove={(index) => setTriggerRows((prev) => prev.filter((_, i) => i !== index))}
            onChangeName={(index, value) =>
              setTriggerRows((prev) => prev.map((row, i) => (i === index ? { ...row, name: value } : row)))
            }
            onChangeTags={(index, value) =>
              setTriggerRows((prev) => prev.map((row, i) => (i === index ? { ...row, tagsText: value } : row)))
            }
          />

          <CriteriaListEditor
            heading="Then Target..."
            addLabel="Add criterion"
            options={TARGET_COMPONENT_OPTIONS}
            rows={targetRows}
            disabled={!isAdmin}
            onAdd={addTargetRow}
            onDuplicate={duplicateTargetRow}
            onRemove={(index) => setTargetRows((prev) => prev.filter((_, i) => i !== index))}
            onChangeName={(index, value) =>
              setTargetRows((prev) => prev.map((row, i) => (i === index ? { ...row, name: value } : row)))
            }
            onChangeTags={(index, value) =>
              setTargetRows((prev) => prev.map((row, i) => (i === index ? { ...row, tagsText: value } : row)))
            }
          />

          <ResultsEditor
            rows={resultRows}
            disabled={!isAdmin}
            onAdd={addResultRow}
            onDuplicate={duplicateResultRow}
            onRemove={(index) => setResultRows((prev) => prev.filter((_, i) => i !== index))}
            onChangeName={(index, value) =>
              setResultRows((prev) =>
                prev.map((row, i) => (i === index ? { name: value, rawValue: defaultRawValueForResult(value) } : row)),
              )
            }
            onChangeValue={(index, value) =>
              setResultRows((prev) => prev.map((row, i) => (i === index ? { ...row, rawValue: value } : row)))
            }
          />
        </form>
      </div>
    </div>
  );
}
