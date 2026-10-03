import { useEffect, useMemo, useState } from 'react'
import { Chart } from './Chart'
import { API_BASE } from '../api'

const RANGES = [
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
  { label: '7d', hours: 24 * 7 },
  { label: '30d', hours: 24 * 30 },
  { label: '90d', hours: 24 * 90 },
]

const PLANT_COLORS = ['#4ade80', '#60a5fa', '#f472b6', '#fbbf24']

export function HistoryPanel() {
  const [hours, setHours] = useState(24)
  const [metric, setMetric] = useState('moisture')
  const [history, setHistory] = useState(null)
  const [status, setStatus] = useState('Loading history...')

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setStatus('Loading history...')
      try {
        const response = await fetch(`${API_BASE}/history?hours=${hours}`)
        const data = await response.json()
        if (cancelled) return
        if (!response.ok) {
          setStatus(data.error || 'Failed to load history')
          return
        }
        setHistory(data)
        setStatus('')
      } catch (error) {
        if (!cancelled) setStatus(`Failed to load history: ${error.message}`)
      }
    }

    load()
    // Ignore a response that arrives after the range changed again.
    return () => {
      cancelled = true
    }
  }, [hours])

  const moisture = metric === 'moisture'

  const data = useMemo(() => {
    if (!history) return [[]]
    return [
      history.timestamps,
      ...history.plants.map((plant) =>
        moisture ? plant.moisture_percent : plant.temperature_c,
      ),
    ]
  }, [history, moisture])

  const series = useMemo(() => {
    if (!history) return [{}]
    return [
      {},
      ...history.plants.map((plant, index) => ({
        label: plant.name,
        stroke: PLANT_COLORS[index % PLANT_COLORS.length],
        width: 2,
        // Gaps are real: they mean the sensor could not be read.
        spanGaps: false,
        value: (self, raw) =>
          raw == null ? '--' : `${raw.toFixed(1)}${moisture ? '%' : '°C'}`,
      })),
    ]
  }, [history, moisture])

  // Fixed for moisture so plants and time ranges stay visually comparable
  // instead of the axis rescaling to whatever happens to be on screen.
  const yRange = moisture ? [0, 100] : undefined

  const hasData = history?.timestamps?.length > 0
  const failedCount = (history?.waterings || []).filter(
    (watering) => watering.delivered === false,
  ).length

  return (
    <section className="panel-section">
      <h2>History</h2>

      <div className="history-controls">
        <div className="range-row">
          {RANGES.map((range) => (
            <button
              key={range.label}
              type="button"
              className={hours === range.hours ? 'tab active' : 'tab'}
              onClick={() => setHours(range.hours)}
            >
              {range.label}
            </button>
          ))}
        </div>
        <div className="range-row">
          <button
            type="button"
            className={moisture ? 'tab active' : 'tab'}
            onClick={() => setMetric('moisture')}
          >
            Moisture
          </button>
          <button
            type="button"
            className={!moisture ? 'tab active' : 'tab'}
            onClick={() => setMetric('temperature')}
          >
            Temperature
          </button>
        </div>
      </div>

      {status && <p className="field-hint">{status}</p>}

      {!status && !hasData && (
        <p className="field-hint">
          No readings in this range yet. The control loop records one a minute,
          so a fresh install needs a few minutes before the chart fills in.
        </p>
      )}

      {hasData && (
        <>
          <Chart
            data={data}
            series={series}
            markers={history.waterings || []}
            yRange={yRange}
            yLabel={moisture ? 'Moisture %' : 'Temp °C'}
          />
          <p className="field-hint">
            Dashed vertical lines mark waterings
            {history.waterings?.length
              ? ` (${history.waterings.length} in this range)`
              : ' (none in this range)'}
            . Gaps in a line mean that sensor could not be read.
          </p>
          {failedCount > 0 && (
            <p className="field-hint warning">
              {failedCount === 1 ? '1 dose' : `${failedCount} doses`} ran but no
              water reached the outlet, drawn as solid red lines. Look for a
              moisture curve that did not rise afterwards.
            </p>
          )}
        </>
      )}
    </section>
  )
}
