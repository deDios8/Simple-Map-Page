import { RESULT_COMPONENT_FIELD_CONFIG, RESULT_COMPONENT_OPTIONS } from "../config";

// Row-list editor for an event's Results. This is the piece that was dead
// code in the prototype (its DOM query looked for the wrong element id) -
// here it's just plain component state, so there's no id to mismatch.
export default function ResultsEditor({ rows, disabled, onAdd, onDuplicate, onRemove, onChangeName, onChangeValue }) {
  return (
    <section className="event-section" aria-labelledby="event-heading">
      <div className="stats-header">
        <h3 id="event-heading">Results</h3>
      </div>
      <div className="component-list">
        {rows.map((row, index) => {
          const config = RESULT_COMPONENT_FIELD_CONFIG[row.name] || {};
          return (
            <article className="component-row" key={index}>
              <div className="result-row-grid">
                <label>
                  <select
                    value={row.name}
                    disabled={disabled}
                    onChange={(event) => onChangeName(index, event.target.value)}
                  >
                    {RESULT_COMPONENT_OPTIONS.map((option) => {
                      const value = typeof option === "string" ? option : option.value;
                      const label = typeof option === "string" ? option : option.label || option.value;
                      return (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      );
                    })}
                  </select>
                </label>
                <ResultValueField
                  config={config}
                  value={row.rawValue}
                  disabled={disabled}
                  onChange={(value) => onChangeValue(index, value)}
                />
                <button
                  className="duplicate-button"
                  type="button"
                  aria-label="Duplicate result"
                  disabled={disabled}
                  onClick={() => onDuplicate(index)}
                >
                  ⧉
                </button>
                <button
                  className="remove-button"
                  type="button"
                  aria-label="Remove result"
                  disabled={disabled}
                  onClick={() => onRemove(index)}
                >
                  ✕
                </button>
              </div>
            </article>
          );
        })}
        <button className="row-add-button" type="button" disabled={disabled} onClick={onAdd}>
          Add result
        </button>
      </div>
    </section>
  );
}

function ResultValueField({ config, value, disabled, onChange }) {
  const { fieldType = "text", label = "Value", placeholder = "" } = config;

  if (fieldType === "bool") {
    return (
      <label>
        {label}
        <select value={value === "false" ? "false" : "true"} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
      </label>
    );
  }

  if (fieldType === "number" || fieldType === "float") {
    return (
      <label>
        {label}
        <input
          type="number"
          value={value}
          placeholder={placeholder}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
    );
  }

  // csv, json, and plain text all edit as free text; parsing happens on save.
  return (
    <label>
      {label}
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
