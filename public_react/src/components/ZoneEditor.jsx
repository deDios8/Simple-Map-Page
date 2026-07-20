import { useState, useEffect } from 'react';

export default function ZoneEditor({ 
  zone, 
  zoneId, 
  onSave, 
  onDelete, 
  onClearLogs,
  currentLocation 
}) {
  const [formData, setFormData] = useState({
    name: '',
    color: '#0b8f87',
    visible: '*',
    traits: '',
    radius: 50,
    coordinates: [],
    stats: {},
  });

  const [coordPickMode, setCoordPickMode] = useState(false);

  useEffect(() => {
    if (zone && zone.properties) {
      const appearance = zone.properties.appearance || {};
      const coords = zone.geometry?.coordinates || [];
      
      setFormData({
        name: appearance.displayName || zone.properties.id || '',
        color: appearance.color || '#0b8f87',
        visible: Array.isArray(appearance.visibleTo) ? appearance.visibleTo.join(',') : '*',
        traits: Array.isArray(zone.properties.traits) ? zone.properties.traits.join(',') : '',
        radius: appearance.radius || 50,
        coordinates: coords,
        stats: zone.properties.stats || {},
      });
    }
  }, [zone, zoneId]);

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Format data for Firebase with proper structure
    const zoneData = {
      appearance: {
        displayName: formData.name,
        color: formData.color,
        visibleTo: formData.visible.split(',').map(v => v.trim()).filter(Boolean),
        radius: formData.radius,
      },
      traits: formData.traits.split(',').map(v => v.trim()).filter(Boolean),
      stats: formData.stats,
    };
    
    onSave(zoneData);
  };

  const handleUseCurrentLocation = () => {
    if (currentLocation) {
      handleChange('coordinates', [currentLocation.lng, currentLocation.lat]);
    }
  };

  const displayLat = formData.coordinates[1] || '';
  const displayLng = formData.coordinates[0] || '';

  return (
    <form id="editor-form" className="editor-form" onSubmit={handleSubmit}>
      <div className="name-row">
        <label>
          Name
          <input
            id="field-name"
            name="name"
            type="text"
            placeholder="Zone name"
            value={formData.name}
            onChange={(e) => handleChange('name', e.target.value)}
          />
        </label>
        <label>
          Color
          <input
            id="field-color"
            name="color"
            type="color"
            value={formData.color}
            onChange={(e) => handleChange('color', e.target.value)}
          />
        </label>
      </div>

      <label>
        Visible To
        <input
          id="field-visible"
          name="visible"
          type="text"
          placeholder="* or user1,user2"
          value={formData.visible}
          onChange={(e) => handleChange('visible', e.target.value)}
        />
      </label>

      <label>
        Traits (comma-separated)
        <input
          id="field-traits"
          name="traits"
          type="text"
          placeholder="poi, shop, safe"
          value={formData.traits}
          onChange={(e) => handleChange('traits', e.target.value)}
        />
      </label>

      <div className="coordinates-section">
        <label>Coordinates</label>
        <div className="coordinates-row">
          <input
            id="coord-display-lat"
            type="number"
            step="any"
            placeholder="Latitude"
            value={displayLat}
            readOnly
          />
          <input
            id="coord-display-lng"
            type="number"
            step="any"
            placeholder="Longitude"
            value={displayLng}
            readOnly
          />
          <button
            id="coord-pick-button"
            type="button"
            className="text-button"
            onClick={handleUseCurrentLocation}
          >
            Use Current
          </button>
        </div>
      </div>

      <label>
        Radius (meters)
        <input
          id="field-radius"
          name="radius"
          type="number"
          min="1"
          value={formData.radius}
          onChange={(e) => handleChange('radius', Number(e.target.value))}
        />
      </label>

      <div className="stats-section">
        <label>Stats</label>
        <StatsEditor
          stats={formData.stats}
          onChange={(stats) => handleChange('stats', stats)}
        />
      </div>

      <div className="editor-actions">
        <button type="submit" className="primary-button">
          Save Changes
        </button>
        <button
          type="button"
          className="text-button"
          onClick={onClearLogs}
        >
          Clear Logs
        </button>
        <button
          type="button"
          className="text-button danger"
          onClick={onDelete}
        >
          Delete Zone
        </button>
      </div>
    </form>
  );
}

function StatsEditor({ stats, onChange }) {
  const statsEntries = Object.entries(stats || {});

  const handleStatChange = (key, field, value) => {
    const newStats = { ...stats };
    newStats[key] = { ...newStats[key], [field]: value };
    onChange(newStats);
  };

  const handleAddStat = () => {
    const newStats = { ...stats };
    const newKey = `stat-${Object.keys(newStats).length + 1}`;
    newStats[newKey] = {
      name: '',
      value: 0,
      max_value: 100,
      min_value: 0,
    };
    onChange(newStats);
  };

  const handleRemoveStat = (key) => {
    const newStats = { ...stats };
    delete newStats[key];
    onChange(newStats);
  };

  if (statsEntries.length === 0) {
    return (
      <div>
        <div className="stats-empty">
          No stats yet. Add one to track custom values.
        </div>
        <button
          type="button"
          className="text-button"
          onClick={handleAddStat}
        >
          Add Stat
        </button>
      </div>
    );
  }

  return (
    <div id="stats-list" className="stats-list">
      {statsEntries.map(([key, stat], index) => (
        <article key={key} className="stat-row">
          <div className="stat-row-grid">
            <label>
              Name
              <input
                type="text"
                value={stat.name || ''}
                placeholder="Health"
                onChange={(e) => handleStatChange(key, 'name', e.target.value)}
              />
            </label>
            <label>
              Value
              <input
                type="number"
                step="any"
                value={stat.value || 0}
                onChange={(e) => handleStatChange(key, 'value', Number(e.target.value))}
              />
            </label>
            <button
              className="stat-remove-button"
              type="button"
              onClick={() => handleRemoveStat(key)}
              aria-label="Remove stat"
            >
              ✕
            </button>
          </div>
        </article>
      ))}
      <button
        type="button"
        className="text-button"
        onClick={handleAddStat}
      >
        Add Stat
      </button>
    </div>
  );
}
