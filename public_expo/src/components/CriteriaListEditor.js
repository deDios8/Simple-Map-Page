// Reusable row-list editor for an event's Trigger or Target criteria - each
// row picks a component name (from map_criteria_components.json) and a
// comma-separated tags list.
export default function CriteriaListEditor({
  heading,
  addLabel,
  options,
  rows,
  disabled,
  onAdd,
  onDuplicate,
  onRemove,
  onChangeName,
  onChangeTags,
}) {
  return (
    <section className="criteria-components-section" aria-label={heading}>
      <div className="stats-header">
        <h3>{heading}</h3>
      </div>
      <div className="component-list">
        {rows.map((row, index) => (
            <article className="component-row" key={index}>
              <div className="criterion-row-grid">
                <label>
                  <select value={row.name} disabled={disabled} onChange={(event) => onChangeName(index, event.target.value)}>
                    {options.map((option) => {
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
                <label>
                  Tags
                  <input
                    type="text"
                    placeholder="tag1, tag2"
                    value={row.tagsText}
                    disabled={disabled}
                    onChange={(event) => onChangeTags(index, event.target.value)}
                  />
                </label>
                <button
                  className="duplicate-button"
                  type="button"
                  aria-label="Duplicate criterion"
                  disabled={disabled}
                  onClick={() => onDuplicate(index)}
                >
                  ⧉
                </button>
                <button
                  className="remove-button"
                  type="button"
                  aria-label="Remove criterion"
                  disabled={disabled}
                  onClick={() => onRemove(index)}
                >
                  ✕
                </button>
              </div>
            </article>
          ))}
        <button className="row-add-button" type="button" disabled={disabled} onClick={onAdd}>
          {addLabel}
        </button>
      </div>
    </section>
  );
}
