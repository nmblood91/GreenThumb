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
      throw new Error(data.detail || data.error || 'Request failed')
    }

    return data
  }

  // Motion endpoints answer 200 with {ok: false, error} when Klipper refuses
  // the move, so a successful request is not a successful move.
  const describeResult = (result) =>
    result?.ok === false ? `failed - ${result.error}` : 'ok'

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

  const moveToZone = async (zoneId) => {
    try {
      const zone = zones.find((item) => item.zone_id === zoneId)
      setStatus(`Moving gantry to ${zone?.name || zoneId}...`)
      const result = await fetchJson(`/zones/${zoneId}/move`, { method: 'POST' })
      setStatus(`Move to ${zone?.name || zoneId}: ${describeResult(result)}`)
      await loadDashboard()
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

      await fetchJson(`/zones/${zone.zone_id}/volume`, {
        method: 'POST',
        body: JSON.stringify({ watering_volume_ml: Number(zone.watering_volume_ml) }),
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

  const waterZone = async (zoneId) => {
    try {
      const zone = zones.find((item) => item.zone_id === zoneId)
      const label = zone?.name || zoneId
      // The request does not return until the gantry has moved and the dose has
      // finished, which is over a minute, so say so rather than looking hung.
      setStatus(`Watering ${label}, this takes a minute...`)
      const result = await fetchJson(`/water/${zoneId}`, { method: 'POST' })
      setStatus(
        result?.status === 'error'
          ? `Water ${label}: failed - ${result.error}`
          : `Watered ${label} with ${result.volume_ml} mL.`,
      )
      await loadDashboard()
    } catch (error) {
      setStatus(`Water failed: ${error.message}`)
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
        <GeneralPanel overview={overview} cameraStatus={cameraStatus} />
      )}

      {activeTab === 'plants' && (
        <ZonesPanel zones={zones} onSave={saveZone} onWater={waterZone} />
      )}
      {activeTab === 'logs' && <LogsPanel logs={logs} />}
    </div>
  )
}

export default App
