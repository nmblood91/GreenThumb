import { useCallback, useEffect, useState } from 'react'

// Relative so the page works from any device. An absolute localhost URL resolves
// to whatever machine the browser is on, not the Pi.
const API_BASE = '/api/v1'

const SAMPLE_SECONDS = 20

const INSTRUCTIONS = {
  dry: 'All sensors should be out of any soil, clean and dry, sitting in open air.',
  wet: 'The prongs should be in water — only the prongs, up to the marked line.',
}

export function CalibrationPanel() {
  const [calibration, setCalibration] = useState(null)
  const [busy, setBusy] = useState('')
  const [results, setResults] = useState(null)
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/sensors/calibration`)
      if (!response.ok) return
      setCalibration(await response.json())
    } catch {
      // A failed read leaves the table empty rather than breaking the panel;
      // the buttons below still work and will refresh it.
    }
  }, [])

  useEffect(() => {
    // Guarded rather than a bare load(): a response landing after the tab is
    // switched away would set state on a gone component, and setting state
    // straight from an effect body is what the hooks lint objects to.
    let cancelled = false
    async function loadOnMount() {
      if (!cancelled) await load()
    }
    loadOnMount()
    return () => {
      cancelled = true
    }
  }, [load])

  const runCalibration = async (endpoint) => {
    setBusy(endpoint)
    setResults(null)
    setMessage('')
    try {
      // Blocks for the whole sampling window, the way a gantry move blocks for
      // its travel. The button stays disabled until it returns.
      const response = await fetch(`${API_BASE}/sensors/calibration/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seconds: SAMPLE_SECONDS }),
      })
      const data = await response.json()
      if (!response.ok) {
        // 409 when a watering cycle holds the hardware, 400 for a bad endpoint.
        setMessage(data.error || 'Calibration failed')
        return
      }
      setResults(data)
      setMessage(
        data.stored === data.total
          ? `Stored the ${endpoint} point for all ${data.total} sensors.`
          : `Stored ${data.stored} of ${data.total}. See the reasons below.`,
      )
      await load()
    } catch (error) {
      setMessage(`Calibration failed: ${error.message}`)
    } finally {
      setBusy('')
    }
  }

  const reset = async () => {
    setBusy('reset')
    setResults(null)
    try {
      await fetch(`${API_BASE}/sensors/calibration/reset`, { method: 'POST' })
      setMessage('Calibration cleared. All sensors are back on the .env defaults.')
      await load()
    } catch (error) {
      setMessage(`Reset failed: ${error.message}`)
    } finally {
      setBusy('')
    }
  }

  const sensors = calibration?.sensors ?? []

  return (
    <section className="panel-section">
      <h2>Moisture calibration</h2>

      <div className="general-settings-form">
        <p className="field-hint">
          Measures each sensor's own dry and wet endpoints. Sensors read
          differently from each other in identical conditions, so calibrating
          them individually keeps that spread out of the reported percentage.
        </p>

        <div className="field-row">
          <div className="motion-grid two-up">
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={() => runCalibration('dry')}
            >
              {busy === 'dry' ? `Sampling… ${SAMPLE_SECONDS}s` : 'Calibrate dry (air)'}
            </button>
            <button
              type="button"
              disabled={Boolean(busy)}
              onClick={() => runCalibration('wet')}
            >
              {busy === 'wet' ? `Sampling… ${SAMPLE_SECONDS}s` : 'Calibrate wet (water)'}
            </button>
          </div>
          <p className="field-hint">
            <strong>Dry:</strong> {INSTRUCTIONS.dry}
            <br />
            <strong>Wet:</strong> {INSTRUCTIONS.wet}
          </p>
          <p className="field-hint warning">
            These boards are not waterproof. Put only the prongs in the water, up
            to the marked line — submerging the connector end destroys the sensor.
          </p>
          <p className="field-hint">
            Each run samples every sensor for {SAMPLE_SECONDS} seconds and takes
            the median. Watering is blocked while it runs. The two passes are
            independent, so either can be redone on its own.
          </p>
        </div>

        {message && <p className="field-hint warning">{message}</p>}

        {results && (
          <div className="field-row">
            <h3>Last run</h3>
            {results.sensors.map((sensor) => (
              <p className="field-hint" key={sensor.address}>
                <strong>{sensor.address}</strong>{' '}
                {sensor.written
                  ? `stored ${sensor.value} (spread ${sensor.spread} over ${sensor.samples} samples)`
                  : `not stored — ${sensor.reason}`}
              </p>
            ))}
          </div>
        )}

        <div className="field-row">
          <h3>Current calibration</h3>
          {sensors.length === 0 && <p className="field-hint">No sensors reporting.</p>}
          {sensors.map((sensor) => {
            const both = sensor.calibrated_dry && sensor.calibrated_wet
            const neither = !sensor.calibrated_dry && !sensor.calibrated_wet
            const source = neither
              ? 'using .env defaults'
              : both
                ? 'calibrated'
                : `half calibrated, ${sensor.calibrated_dry ? 'wet' : 'dry'} still default`
            return (
              <p className="field-hint" key={sensor.address}>
                <strong>{sensor.address}</strong> dry {sensor.dry} · wet {sensor.wet} ·
                span {sensor.wet - sensor.dry} — {source}
              </p>
            )
          })}
          <p className="field-hint">
            Air and water measure the sensor's full range, not the soil's. Dry
            soil reads around 30-40% on that scale, so tune each zone's target by
            watching the History tab rather than assuming a number is physical.
          </p>
        </div>

        <div className="field-row">
          <button type="button" disabled={Boolean(busy)} onClick={reset}>
            Reset calibration
          </button>
          <p className="field-hint">
            Clears stored values and returns every sensor to MOISTURE_RAW_DRY and
            MOISTURE_RAW_WET from <code>.env</code>.
          </p>
        </div>
      </div>
    </section>
  )
}
