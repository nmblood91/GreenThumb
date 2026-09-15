export function GantryPanel({ zones, gantryPosition, onHome, onMove, onMoveToZone }) {
  return (
    <section className="panel-section">
      <h2>View / Control Gantry</h2>

      <div className="camera-frame gantry-camera">
        <div className="camera-placeholder">Camera feed pending</div>
      </div>

      <div className="position-readout">Position: {gantryPosition} mm</div>

      <div className="motion-grid">
        <button className="primary" onClick={onHome}>Home Gantry</button>
      </div>

      <div className="motion-grid two-up">
        <button onClick={() => onMove(-10)}>Move Left 10 mm</button>
        <button onClick={() => onMove(10)}>Move Right 10 mm</button>
      </div>

      <div className="motion-grid two-up">
        <button onClick={() => onMove(-50)}>Move Left 50 mm</button>
        <button onClick={() => onMove(50)}>Move Right 50 mm</button>
      </div>

      <div className="subsection">
        <h3>Move to Zone</h3>
        <div className="zone-actions-grid">
          {zones.map((zone) => (
            <button key={zone.zone_id} onClick={() => onMoveToZone(zone.zone_id)}>
              {zone.name}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
