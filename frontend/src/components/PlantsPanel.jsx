import { useEffect, useState } from 'react'

const draftFrom = (zone) => ({
  name: zone.name,
  light_start_time: zone.light_start_time ?? '08:00',
  light_stop_time: zone.light_stop_time ?? '20:00',
  moisture_target: zone.moisture_target ?? 45,
  watering_volume_ml: zone.watering_volume_ml ?? 100,
  position_mm: zone.position_mm ?? 0,
})

export function ZonesPanel({ zones, onSave, onWater }) {
  const [drafts, setDrafts] = useState({})
  const [expandedZoneIds, setExpandedZoneIds] = useState([])

  useEffect(() => {
    setDrafts(Object.fromEntries(zones.map((zone) => [zone.zone_id, draftFrom(zone)])))
  }, [zones])

  const toggleZoneExpanded = (zoneId) => {
    setExpandedZoneIds((current) =>
      current.includes(zoneId)
        ? current.filter((id) => id !== zoneId)
        : [...current, zoneId],
    )
  }

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
      <h2>Zone Settings</h2>
      <div className="cards">
        {zones.map((zone) => {
          const draft = drafts[zone.zone_id] || draftFrom(zone)
          const isExpanded = expandedZoneIds.includes(zone.zone_id)

          return (
            <div key={zone.zone_id} className="zone-card">
              <button
                type="button"
                className="zone-header"
                onClick={() => toggleZoneExpanded(zone.zone_id)}
                aria-expanded={isExpanded}
              >
                <span>{zone.name}</span>
                <span className="zone-chevron">{isExpanded ? '−' : '+'}</span>
              </button>

              {isExpanded && (
                <>
                  <div className="field-grid">
                    <label>
                      Plant name
                      <input
                        value={draft.name}
                        onChange={(event) => updateDraft(zone.zone_id, 'name', event.target.value)}
                      />
                    </label>
                    <label>
                      Light start
                      <input
                        type="time"
                        value={draft.light_start_time}
                        onChange={(event) => updateDraft(zone.zone_id, 'light_start_time', event.target.value)}
                      />
                    </label>
                    <label>
                      Light stop
                      <input
                        type="time"
                        value={draft.light_stop_time}
                        onChange={(event) => updateDraft(zone.zone_id, 'light_stop_time', event.target.value)}
                      />
                    </label>
                    <label>
                      Moisture target (%)
                      <input
                        type="number"
                        value={draft.moisture_target}
                        onChange={(event) => updateDraft(zone.zone_id, 'moisture_target', event.target.value)}
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
                          updateDraft(zone.zone_id, 'watering_volume_ml', event.target.value)
                        }
                      />
                    </label>
                    <label>
                      Watering location (mm)
                      <input
                        type="number"
                        value={draft.position_mm}
                        onChange={(event) => updateDraft(zone.zone_id, 'position_mm', event.target.value)}
                      />
                    </label>
                  </div>

                  <div className="zone-actions-row">
                    <button
                      className="primary"
                      onClick={() => onSave({ ...zone, ...draft })}
                    >
                      Save Zone
                    </button>
                    <button onClick={() => onWater(zone.zone_id)}>Water Now</button>
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
