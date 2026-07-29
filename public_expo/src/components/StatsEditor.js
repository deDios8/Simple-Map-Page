// Renders one editable row per zone stat (name + value), reused by ZoneEditor.
export default function StatsEditor({ rows, disabled, onAdd, onDuplicate, onRemove, onChange }) {
  return (
    <section className="stats-section" aria-labelledby="stats-heading">
      <div className="stats-header">
        <h2 id="stats-heading">Stats</h2>
      </div>
      <div className="component-list">
        {rows.map((row, index) => (
            <article className="component-row" key={row.key || index}>
              <div className="component-row-grid">
                <label>
                  Name
                  <input
                    type="text"
                    placeholder="Health"
                    value={row.name}
                    disabled={disabled}
                    onChange={(event) => onChange(index, "name", event.target.value)}
                  />
                </label>
                <label>
                  Value
                  <input
                    type="number"
                    step="any"
                    title={`Valid range: ${row.min_value} to ${row.max_value}`}
                    value={row.value}
                    disabled={disabled}
                    onChange={(event) => onChange(index, "value", event.target.value)}
                  />
                </label>
                <button
                  className="duplicate-button"
                  type="button"
                  aria-label="Duplicate stat"
                  disabled={disabled}
                  onClick={() => onDuplicate(index)}
                >
                  ⧉
                </button>
                <button
                  className="remove-button"
                  type="button"
                  aria-label="Remove stat"
                  disabled={disabled}
                  onClick={() => onRemove(index)}
                >
                  ✕
                </button>
              </div>
            </article>
          ))
        }
        <button className="row-add-button" type="button" disabled={disabled} onClick={onAdd}>
          Add stat
        </button>
      </div>
    </section>
  );
}
