import { useEffect, useMemo, useState } from 'react'
import { TopBar } from './components/TopBar'
import { TabBar } from './components/TabBar'
import { GantryPanel } from './components/GantryPanel'
import { OverviewPanel } from './components/OverviewPanel'
import { PlantsPanel } from './components/PlantsPanel'
import { LogsPanel } from './components/LogsPanel'
import './App.css'

const API_BASE = 'http://localhost:8000/api/v1'

function App() {
  const [activeTab, setActiveTab] = useState('gantry')
  const [overview, setOverview] = useState(null)
  const [plants, setPlants] = useState([])
  const [logs, setLogs] = useState([])
  const [status, setStatus] = useState('Loading GreenThumb...')
  const [loading, setLoading] = useState(true)

  const fetchJson = async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })

    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || 'Request failed')
    }

    return data
  }

  const loadDashboard = async () => {
    try {
      setLoading(true)
      const [overviewData, plantsData, logsData] = await Promise.all([
        fetchJson('/overview'),
        fetchJson('/plants'),
        fetchJson('/logs?lines=20'),
      ])

      setOverview(overviewData)
      setPlants(plantsData)
      setLogs(logsData)
      setStatus('System online and ready.')
    } catch (error) {
      setStatus(`Connection failed: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  const cameraStatus = useMemo(() => {
    if (!overview) return 'Camera stream offline'
    return overview.camera_status || 'Camera stream offline'
  }, [overview])

  const gantryPosition = useMemo(() => {
    const movement = overview?.movement ?? {}
    const rawValue =
      movement.x_mm ??
      movement.x_position ??
      movement.position_mm ??
      movement.position ??
      overview?.position_mm ??
      plants[0]?.position_mm ??
      0

    const numericValue = Number(rawValue)
    return Number.isFinite(numericValue) ? numericValue : 0
  }, [overview, plants])

  const homeGantry = async () => {
    try {
      setStatus('Homing gantry...')
      const result = await fetchJson('/gantry/home', { method: 'POST' })
      setStatus(`Gantry homed: ${JSON.stringify(result)}`)
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
      setStatus(`Move result: ${JSON.stringify(result)}`)
      await loadDashboard()
    } catch (error) {
      setStatus(`Move failed: ${error.message}`)
    }
  }

  const moveToPlant = async (zoneId) => {
    try {
      const plant = plants.find((item) => item.zone_id === zoneId)
      setStatus(`Moving gantry to ${plant?.name || zoneId}...`)
      const result = await fetchJson(`/zones/${zoneId}/move`, { method: 'POST' })
      setStatus(`Moved to ${plant?.name || zoneId}: ${JSON.stringify(result)}`)
    } catch (error) {
      setStatus(`Move to plant failed: ${error.message}`)
    }
  }

  const savePlant = async (plant) => {
    try {
      setStatus(`Saving ${plant.name}...`)

      await fetchJson(`/plants/${plant.zone_id}/name`, {
        method: 'POST',
        body: JSON.stringify({ name: plant.name }),
      })

      await fetchJson(`/plants/${plant.zone_id}/lighting`, {
        method: 'POST',
        body: JSON.stringify({
          start_time: plant.light_start_time,
          stop_time: plant.light_stop_time,
        }),
      })

      await fetchJson(`/plants/${plant.zone_id}/moisture-target`, {
        method: 'POST',
        body: JSON.stringify({ moisture_target: Number(plant.moisture_target) }),
      })

      await fetchJson(`/zones/${plant.zone_id}/position`, {
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
      <TopBar loading={loading} />
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
        <OverviewPanel overview={overview} plants={plants} cameraStatus={cameraStatus} />
      )}

      {activeTab === 'plants' && <PlantsPanel plants={plants} onSave={savePlant} />}
      {activeTab === 'logs' && <LogsPanel logs={logs} />}
    </div>
  )
}

export default App
