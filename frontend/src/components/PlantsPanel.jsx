import { useState } from 'react'

const draftFrom = (plant) => ({
  name: plant.name,
  light_start_time: plant.light_start_time ?? '08:00',
  light_stop_time: plant.light_stop_time ?? '20:00',
  moisture_target: plant.moisture_target ?? 45,
  watering_volume_ml: plant.watering_volume_ml ?? 100,
  position_mm: plant.position_mm ?? 0,
})

// -1 is "no reading", not dry. The backend uses it for a probe that is
// unplugged or unreadable, and showing that as 0% would read as "bone dry" and
// invite watering a plant whose sensor simply fell out.
const describeMoisture = (status) => {
  if (!status) return { text: '—', hint: 'no data yet' }
  if (status.moisture_percent == null || status.moisture_percent < 0) {
    return { text: 'no reading', hint: 'probe unplugged or unreadable', warn: true }
  }
  const text = `${status.moisture_percent.toFixed(0)}%`
  // Below a full window the loop will not water, so say so rather than show a
  // number that looks actionable.
  if (status.window_size && status.sample_count < status.window_size) {
    return {
      text,
      hint: `gathering history, ${status.sample_count}/${status.window_size}`,
    }
  }
  const target = status.target_moisture
  if (target != null) {
    return {
      text,
      hint:
        status.moisture_percent < target
          ? `below target of ${target}%`
          : `target ${target}%`,
      dry: status.moisture_percent < target,
    }
  }
  return { text, hint: '' }
}

export function PlantsPanel({ plants, onSave, status }) {
  const [drafts, setDrafts] = useState({})
  const [expandedPlantIds, setExpandedPlantIds] = useState([])

  // Drafts mirror the plants prop, and resyncing them during render rather than
  // in an effect means the inputs never paint one frame of stale values after
  // a save. React re-runs this component immediately, before touching the DOM.
  const [syncedPlants, setSyncedPlants] = useState(null)
  if (plants !== syncedPlants) {
    setSyncedPlants(plants)
    setDrafts(Object.fromEntries(plants.map((plant) => [plant.plant_id, draftFrom(plant)])))
  }

  const togglePlantExpanded = (plantId) => {
    setExpandedPlantIds((current) =>
      current.includes(plantId)
        ? current.filter((id) => id !== plantId)
        : [...current, plantId],
    )
  }

  const updateDraft = (plantId, field, value) => {
    setDrafts((current) => ({
      ...current,
      [plantId]: {
        ...current[plantId],
        [field]: value,
      },
    }))
  }

  return (
    <section className="panel-section">
      <h2>Plant Settings</h2>
      <div className="cards">
        {plants.map((plant) => {
          const draft = drafts[plant.plant_id] || draftFrom(plant)
          const isExpanded = expandedPlantIds.includes(plant.plant_id)
          const reading = describeMoisture(
            status?.find((item) => item.plant_id === plant.plant_id),
          )

          return (
            <div key={plant.plant_id} className="plant-card">
              <button
                type="button"
                className="plant-header"
                onClick={() => togglePlantExpanded(plant.plant_id)}
                aria-expanded={isExpanded}
              >
                <span>{plant.name}</span>
                <span className="plant-reading">
                  <strong className={reading.warn ? 'warn' : reading.dry ? 'dry' : undefined}>
                    {reading.text}
                  </strong>
                  {reading.hint && <small>{reading.hint}</small>}
                </span>
                <span className="plant-chevron">{isExpanded ? '−' : '+'}</span>
              </button>

              {isExpanded && (
                <>
                  <div className="field-grid">
                    <label>
                      Plant name
                      <input
                        value={draft.name}
                        onChange={(event) => updateDraft(plant.plant_id, 'name', event.target.value)}
                      />
                    </label>
                    <label>
                      Light start
                      <input
                        type="time"
                        value={draft.light_start_time}
                        onChange={(event) => updateDraft(plant.plant_id, 'light_start_time', event.target.value)}
                      />
                    </label>
                    <label>
                      Light stop
                      <input
                        type="time"
                        value={draft.light_stop_time}
                        onChange={(event) => updateDraft(plant.plant_id, 'light_stop_time', event.target.value)}
                      />
                    </label>
                    <label>
                      Moisture target (%)
                      <input
                        type="number"
                        value={draft.moisture_target}
                        onChange={(event) => updateDraft(plant.plant_id, 'moisture_target', event.target.value)}
                      />
                    </label>
                    <label>
                      Watering volume (mL)
                      <input
                        type="number"
                        min="0"
                        step="10"
                        value={draft.watering_volume_ml}
                        onChange={(event) =>
                          updateDraft(plant.plant_id, 'watering_volume_ml', event.target.value)
                        }
                      />
                    </label>
                    <label>
                      Watering location (mm)
                      <input
                        type="number"
                        value={draft.position_mm}
                        onChange={(event) => updateDraft(plant.plant_id, 'position_mm', event.target.value)}
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
                </>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
