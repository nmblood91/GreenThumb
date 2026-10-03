import { useCallback, useEffect, useMemo, useState } from 'react'
import { TopBar } from './components/TopBar'
import { TabBar } from './components/TabBar'
import { GantryPanel } from './components/GantryPanel'
import { GeneralPanel } from './components/GeneralPanel'
import { CalibrationPanel } from './components/CalibrationPanel'
import { PlantsPanel } from './components/PlantsPanel'
import { LogsPanel } from './components/LogsPanel'
import { HistoryPanel } from './components/HistoryPanel'
import './App.css'

const API_BASE = '/api/v1'

const fetchJson = async (path, options = {}) => {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || data.error || 'Request failed')
  }

  return data
}


function App() {
  const [activeTab, setActiveTab] = useState('gantry')
  const [overview, setOverview] = useState(null)
  const [plants, setPlants] = useState([])
  const [logs, setLogs] = useState([])
  const [status, setStatus] = useState('Loading GreenThumb...')

  // Motion endpoints answer 200 with {ok: false, error} when Klipper refuses
  // the move, so a successful request is not a successful move.
  const describeResult = (result) =>
    result?.ok === false ? `failed - ${result.error}` : 'ok'

  const loadDashboard = useCallback(async () => {
    try {
      const [overviewData, plantsData, logsData] = await Promise.all([
        fetchJson('/overview'),
        fetchJson('/plants'),
        fetchJson('/logs?lines=20'),
      ])

      setOverview(overviewData)
      setPlants(plantsData)
      setLogs(logsData)
      if (logsData?.length) {
        setStatus(logsData[0])
      } else {
        setStatus('System online and ready.')
      }
    } catch (error) {
      setStatus(`Connection failed: ${error.message}`)
    }
    // Stable: it closes over nothing reactive, so the mount effect below can
    // depend on it honestly instead of suppressing the dependency warning.
  }, [])

  useEffect(() => {
    // Guarded rather than a bare loadDashboard(): a response that lands after
    // the component is gone would set state on nothing, and setting state
    // straight from an effect body is what the hooks lint objects to.
    let cancelled = false
    async function loadOnMount() {
      if (!cancelled) await loadDashboard()
    }
    loadOnMount()
    return () => {
      cancelled = true
    }
  }, [loadDashboard])

  const gantryPosition = useMemo(() => {
    const movement = overview?.movement ?? {}
    if (movement.ok === false) return 'unavailable'
    if (!movement.homed) return 'not homed'

    const numericValue = Number(movement.position)
    return Number.isFinite(numericValue) ? `${numericValue} mm` : 'unknown'
  }, [overview])

  const homeGantry = async () => {
    try {
      setStatus('Homing gantry...')
      const result = await fetchJson('/gantry/home', { method: 'POST' })
      setStatus(`Home gantry: ${describeResult(result)}`)
      await loadDashboard()
    } catch (error) {
      setStatus(`Home failed: ${error.message}`)
    }
  }

  const moveGantry = async (distance) => {
    try {
      setStatus(`Moving gantry ${distance} mm...`)
      const result = await fetchJson('/gantry/move', {
        method: 'POST',
        body: JSON.stringify({ distance_mm: distance }),
      })
      setStatus(`Move gantry ${distance} mm: ${describeResult(result)}`)
      await loadDashboard()
    } catch (error) {
      setStatus(`Move failed: ${error.message}`)
    }
  }

  const moveToPlant = async (plantId) => {
    try {
      const plant = plants.find((item) => item.plant_id === plantId)
      setStatus(`Moving gantry to ${plant?.name || plantId}...`)
      const result = await fetchJson(`/plants/${plantId}/move`, { method: 'POST' })
      setStatus(`Move to ${plant?.name || plantId}: ${describeResult(result)}`)
      await loadDashboard()
    } catch (error) {
      setStatus(`Move to plant failed: ${error.message}`)
    }
  }

  const savePlant = async (plant) => {
    try {
      setStatus(`Saving ${plant.name}...`)

      await fetchJson(`/plants/${plant.plant_id}/name`, {
        method: 'POST',
        body: JSON.stringify({ name: plant.name }),
      })

      await fetchJson(`/plants/${plant.plant_id}/lighting`, {
        method: 'POST',
        body: JSON.stringify({
          start_time: plant.light_start_time,
          stop_time: plant.light_stop_time,
        }),
      })

      await fetchJson(`/plants/${plant.plant_id}/moisture`, {
        method: 'POST',
        body: JSON.stringify({ moisture_target: Number(plant.moisture_target) }),
      })

      await fetchJson(`/plants/${plant.plant_id}/volume`, {
        method: 'POST',
        body: JSON.stringify({ watering_volume_ml: Number(plant.watering_volume_ml) }),
      })

      await fetchJson(`/plants/${plant.plant_id}/position`, {
        method: 'POST',
        body: JSON.stringify({ position_mm: Number(plant.position_mm) }),
      })

      setStatus(`Saved ${plant.name}.`)
      await loadDashboard()
    } catch (error) {
      setStatus(`Save failed: ${error.message}`)
    }
  }


  return (
    <div className="app-shell">
      <TopBar />
      <TabBar activeTab={activeTab} onChange={setActiveTab} />
      <div className="status-bar">{status}</div>

      {activeTab === 'gantry' && (
        <GantryPanel
          plants={plants}
          gantryPosition={gantryPosition}
          onHome={homeGantry}
          onMove={moveGantry}
          onMoveToPlant={moveToPlant}
        />
      )}

      {activeTab === 'general' && (
        <>
          <GeneralPanel overview={overview} />
          {/* Fetches and refreshes its own calibration state: a run takes
              seconds and only this panel cares about the result. */}
          <CalibrationPanel />
        </>
      )}

      {activeTab === 'plants' && (
        <PlantsPanel plants={plants} onSave={savePlant} />
      )}
      {/* Fetches its own data so changing the range does not reload the dashboard. */}
      {activeTab === 'history' && <HistoryPanel />}
      {activeTab === 'logs' && <LogsPanel logs={logs} />}
    </div>
  )
}

export default App
