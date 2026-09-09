import { useEffect, useState } from 'react'

export function PlantsPanel({ plants, onSave }) {
  const [drafts, setDrafts] = useState({})

  useEffect(() => {
    setDrafts(
      Object.fromEntries(
        plants.map((plant) => [
          plant.zone_id,
          {
            name: plant.name,
            light_start_time: plant.light_start_time ?? '08:00',
            light_stop_time: plant.light_stop_time ?? '20:00',
            moisture_target: plant.moisture_target ?? 45,
            position_mm: plant.position_mm ?? 0,
          },
        ]),
      ),
    )
  }, [plants])

  const updateDraft = (zoneId, field, value) => {
    setDrafts((current) => ({
      ...current,
      [zoneId]: {
        ...current[zoneId],
        [field]: value,
      },
    }))
  }

  return (
    <section className="panel-section">
      <h2>Plant / Zone Settings</h2>
      <div className="cards">
        {plants.map((plant) => {
          const draft = drafts[plant.zone_id] || {
            name: plant.name,
            light_start_time: plant.light_start_time ?? '08:00',
            light_stop_time: plant.light_stop_time ?? '20:00',
            moisture_target: plant.moisture_target ?? 45,
            position_mm: plant.position_mm ?? 0,
          }

          return (
            <div key={plant.zone_id} className="plant-card">
              <h3>{plant.name}</h3>
              <div className="field-grid">
                <label>
                  Name
                  <input
                    value={draft.name}
                    onChange={(event) => updateDraft(plant.zone_id, 'name', event.target.value)}
                  />
                </label>
                <label>
                  Light start
                  <input
                    type="time"
                    value={draft.light_start_time}
                    onChange={(event) => updateDraft(plant.zone_id, 'light_start_time', event.target.value)}
                  />
                </label>
                <label>
                  Light stop
                  <input
                    type="time"
                    value={draft.light_stop_time}
                    onChange={(event) => updateDraft(plant.zone_id, 'light_stop_time', event.target.value)}
                  />
                </label>
                <label>
                  Moisture target (%)
                  <input
                    type="number"
                    value={draft.moisture_target}
                    onChange={(event) => updateDraft(plant.zone_id, 'moisture_target', event.target.value)}
                  />
                </label>
                <label>
                  Watering location (mm)
                  <input
                    type="number"
                    value={draft.position_mm}
                    onChange={(event) => updateDraft(plant.zone_id, 'position_mm', event.target.value)}
                  />
                </label>
              </div>

              <div className="plant-actions-row">
                <button
                  className="primary"
                  onClick={() => onSave({ ...plant, ...draft })}
                >
                  Save Plant
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
