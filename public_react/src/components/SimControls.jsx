export default function SimControls({ onMove, visible }) {
  if (!visible) return null;

  return (
    <div id="sim-controls" className="sim-controls">
      <div className="sim-row">
        <button 
          id="sim-up-button" 
          className="sim-button" 
          type="button" 
          aria-label="Move up"
          onClick={() => onMove(0, 0.001)}
        >
          ↑
        </button>
        <button 
          id="sim-down-button" 
          className="sim-button" 
          type="button" 
          aria-label="Move down"
          onClick={() => onMove(0, -0.001)}
        >
          ↓
        </button>
      </div>
      <div className="sim-row">
        <button 
          id="sim-left-button" 
          className="sim-button" 
          type="button" 
          aria-label="Move left"
          onClick={() => onMove(-0.001, 0)}
        >
          ←
        </button>
        <button 
          id="sim-right-button" 
          className="sim-button" 
          type="button" 
          aria-label="Move right"
          onClick={() => onMove(0.001, 0)}
        >
          →
        </button>
      </div>
    </div>
  );
}
