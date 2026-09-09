export function GantryPanel({ plants, gantryPosition, onHome, onMove, onMoveToPlant }) {
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
        <button onClick={() => onMove(-10)}>Move Left -10 mm</button>
        <button onClick={() => onMove(10)}>Move Right +10 mm</button>
      </div>

      <div className="motion-grid two-up">
        <button onClick={() => onMove(-50)}>Move Left -50 mm</button>
        <button onClick={() => onMove(50)}>Move Right +50 mm</button>
      </div>

      <div className="subsection">
        <h3>Move to Plant</h3>
        <div className="plant-actions-grid">
          {plants.map((plant) => (
            <button key={plant.zone_id} onClick={() => onMoveToPlant(plant.zone_id)}>
              {plant.name}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
