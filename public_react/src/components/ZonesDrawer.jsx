import { useState } from 'react';
import ZoneList from './ZoneList';
import ZoneEditor from './ZoneEditor';

export default function ZonesDrawer({
  isOpen,
  onClose,
  sessionName,
  zones,
  selectedId,
  onSelectZone,
  onAddZone,
  onEditZone,
  onDeleteZone,
  onClearLogs,
  onClearAllLogs,
  gpsMode,
  onToggleGps,
  listenerActive,
  onToggleListener,
  currentLocation,
}) {
  const [showEditor, setShowEditor] = useState(false);

  const handleSelectZone = (id) => {
    onSelectZone(id);
    setShowEditor(true);
  };

  const handleAddZone = () => {
    onAddZone();
    setShowEditor(true);
  };

  const handleCloseEditor = () => {
    setShowEditor(false);
    onSelectZone(null);
  };

  const handleSaveZone = (data) => {
    onEditZone(selectedId, data);
  };

  const handleDeleteZone = () => {
    if (confirm('Delete this zone?')) {
      onDeleteZone(selectedId);
      handleCloseEditor();
    }
  };

  return (
    <aside 
      id="drawer" 
      className={`drawer ${isOpen ? 'is-open' : ''}`} 
      aria-label="zones"
    >
      <div className="drawer-header">
        <div>
          <p className="eyebrow">User Session</p>
          <h1 id="drawer-session-title">{sessionName || 'Session'}</h1>
        </div>
        <div className="drawer-header-actions">
          <button
            id="gps-toggle"
            className="gps-toggle"
            type="button"
            aria-label="Toggle GPS/Sim mode"
            title="Toggle between GPS and Simulation mode"
            data-mode={gpsMode ? 'gps' : 'sim'}
            onClick={onToggleGps}
          >
            {gpsMode ? 'GPS' : 'SIM'}
          </button>
          <button
            id="listener-toggle"
            className="listener-toggle"
            type="button"
            aria-label="Pause/Resume Firebase listener"
            title="Pause/Resume Firebase listener"
            data-state={listenerActive ? 'active' : 'paused'}
            onClick={onToggleListener}
          >
            {listenerActive ? 'pause db' : 'resume db'}
          </button>
          <button 
            id="drawer-close" 
            className="text-button" 
            type="button"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>

      <div className="drawer-body">
        <section className="panel-section">
          <div className="editor-header">
            <div className="section-actions">
              <button
                id="add-zone-button"
                className="text-button"
                type="button"
                aria-label="Add new zone at current location"
                onClick={handleAddZone}
              >
                Add zone
              </button>
            </div>
            <button
              id="clear-all-logs-button"
              className="text-button"
              type="button"
              aria-label="Clear zone logs for all zones"
              onClick={onClearAllLogs}
            >
              Clear logs
            </button>
          </div>
          <ZoneList
            zones={zones}
            selectedId={selectedId}
            onSelect={handleSelectZone}
          />
          <div className="editor-bottom-spacer" aria-hidden="true"></div>
        </section>
      </div>

      <div id="editor-panel" className={`editor-panel ${showEditor ? 'is-open' : ''}`}>
        <div className="editor-panel-header">
          <h2 id="editor-empty-state">
            {selectedId ? 'Edit Zone' : 'Select a zone to edit.'}
          </h2>
          <button
            id="editor-cancel-button"
            className="text-button"
            type="button"
            onClick={handleCloseEditor}
          >
            Cancel
          </button>
        </div>
        <div className="editor-panel-body">
          {selectedId && zones[selectedId] && (
            <ZoneEditor
              zone={zones[selectedId]}
              zoneId={selectedId}
              onSave={handleSaveZone}
              onDelete={handleDeleteZone}
              onClearLogs={() => onClearLogs(selectedId)}
              currentLocation={currentLocation}
            />
          )}
        </div>
      </div>
    </aside>
  );
}
