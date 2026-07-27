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
  onRemove,
  onChangeName,
  onChangeTags,
}) {
  return (
    <section className="criteria-components-section" aria-label={heading}>
      <div className="stats-header">
        <h3>{heading}</h3>
      </div>
      <div className="stats-list">
        {rows.length === 0 ? (
          <div className="stats-empty">No criteria yet. Add one to define matching rules.</div>
        ) : (
          rows.map((row, index) => (
            <article className="stat-row" key={index}>
              <div className="criterion-row-grid">
                <label>
                  <select value={row.name} disabled={disabled} onChange={(event) => onChangeName(index, event.target.value)}>
                    {options.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
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
                  className="stat-remove-button"
                  type="button"
                  aria-label="Remove criterion"
                  disabled={disabled}
                  onClick={() => onRemove(index)}
                >
                  ✕
                </button>
              </div>
            </article>
          ))
        )}
        <button className="stat-row-add-button" type="button" disabled={disabled} onClick={onAdd}>
          {addLabel}
        </button>
      </div>
    </section>
  );
}
