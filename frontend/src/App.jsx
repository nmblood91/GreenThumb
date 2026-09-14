import { useEffect, useMemo, useState } from 'react'
import { TopBar } from './components/TopBar'
import { TabBar } from './components/TabBar'
import { GantryPanel } from './components/GantryPanel'
import { GeneralPanel } from './components/GeneralPanel'
import { ZonesPanel } from './components/PlantsPanel'
import { LogsPanel } from './components/LogsPanel'
import './App.css'

const API_BASE = '/api/v1'

function App() {
  const [activeTab, setActiveTab] = useState('gantry')
  const [overview, setOverview] = useState(null)
  const [zones, setZones] = useState([])
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
      const [overviewData, zonesData, logsData] = await Promise.all([
        fetchJson('/overview'),
        fetchJson('/zones'),
        fetchJson('/logs?lines=20'),
      ])

      setOverview(overviewData)
      setZones(zonesData)
      setLogs(logsData)
      if (logsData?.length) {
        setStatus(logsData[0])
      } else {
        setStatus('System online and ready.')
      }
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
      zones[0]?.position_mm ??
      0

    const numericValue = Number(rawValue)
    return Number.isFinite(numericValue) ? numericValue : 0
  }, [overview, zones])

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

  const moveToZone = async (zoneId) => {
    try {
      const zone = zones.find((item) => item.zone_id === zoneId)
      setStatus(`Moving gantry to ${zone?.name || zoneId}...`)
      const result = await fetchJson(`/zones/${zoneId}/move`, { method: 'POST' })
      setStatus(`Moved to ${zone?.name || zoneId}: ${JSON.stringify(result)}`)
    } catch (error) {
      setStatus(`Move to zone failed: ${error.message}`)
    }
  }

  const saveZone = async (zone) => {
    try {
      setStatus(`Saving ${zone.name}...`)

      await fetchJson(`/zones/${zone.zone_id}/plant`, {
        method: 'POST',
        body: JSON.stringify({ name: zone.name }),
      })

      await fetchJson(`/zones/${zone.zone_id}/lighting`, {
        method: 'POST',
        body: JSON.stringify({
          start_time: zone.light_start_time,
          stop_time: zone.light_stop_time,
        }),
      })

      await fetchJson(`/zones/${zone.zone_id}/moisture`, {
        method: 'POST',
        body: JSON.stringify({ moisture_target: Number(zone.moisture_target) }),
      })

      await fetchJson(`/zones/${zone.zone_id}/position`, {
        method: 'POST',
        body: JSON.stringify({ position_mm: Number(zone.position_mm) }),
      })

      setStatus(`Saved ${zone.name}.`)
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
          zones={zones}
          gantryPosition={gantryPosition}
          onHome={homeGantry}
          onMove={moveGantry}
          onMoveToZone={moveToZone}
        />
      )}

      {activeTab === 'general' && (
        <GeneralPanel overview={overview} zones={zones} cameraStatus={cameraStatus} />
      )}

      {activeTab === 'plants' && <ZonesPanel zones={zones} onSave={saveZone} />}
      {activeTab === 'logs' && <LogsPanel logs={logs} />}
    </div>
  )
}

export default App
