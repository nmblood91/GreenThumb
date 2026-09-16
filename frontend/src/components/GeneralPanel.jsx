import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000/api/v1'

const toHexColor = (value) => {
  if (Array.isArray(value)) {
    const [r, g, b] = value
    return `#${[r, g, b]
      .map((channel) => channel.toString(16).padStart(2, '0'))
      .join('')}`
  }

  return value || '#00ff80'
}

const parseHexColor = (hex) => {
  const clean = hex.replace('#', '')
  const full = clean.length === 3 ? clean.split('').map((char) => char + char).join('') : clean
  const numeric = Number.parseInt(full, 16)

  return {
    r: (numeric >> 16) & 255,
    g: (numeric >> 8) & 255,
    b: numeric & 255,
  }
}

const UI_MODE_BY_BACKEND = {
  schedule: 'schedule',
  manual: 'on',
  rainbow: 'rainbow',
  off: 'off',
}

const DEFAULT_COLOR_ORDERS = ['RGB', 'RBG', 'GRB', 'GBR', 'BRG', 'BGR']

export function GeneralPanel({ overview, zones, cameraStatus }) {
  const [settings, setSettings] = useState({
    ledMode: 'schedule',
    brightness: 75,
    color: '#00ff80',
    colorOrder: 'RGB',
    deviceName: 'GreenThumb',
    cameraEnabled: true,
    defaultWateringVolume: 180,
    ledCount: 20,
  })

  const lighting = overview?.lighting
  const colorOrderOptions = lighting?.color_order_options ?? DEFAULT_COLOR_ORDERS

  useEffect(() => {
    setSettings((current) => ({
      ...current,
      ledMode: UI_MODE_BY_BACKEND[lighting?.mode] ?? current.ledMode,
      brightness: lighting?.brightness ?? current.brightness,
      color: toHexColor(lighting?.color || current.color),
      colorOrder: lighting?.color_order ?? current.colorOrder,
      ledCount: lighting?.led_count ?? current.ledCount,
      deviceName: overview?.device_name || current.deviceName,
      cameraEnabled: overview?.camera_enabled ?? current.cameraEnabled,
      defaultWateringVolume: overview?.default_watering_volume_ml ?? current.defaultWateringVolume,
    }))
  }, [overview])

  const saveSettings = async () => {
    try {
      const modeMap = {
        schedule: 'schedule',
        on: 'manual',
        rainbow: 'rainbow',
        off: 'off',
      }

      const mode = modeMap[settings.ledMode] || 'schedule'

      await fetch(`${API_BASE}/lights/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      })

      await fetch(`${API_BASE}/lights/brightness`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brightness: Number(settings.brightness) }),
      })

      await fetch(`${API_BASE}/lights/color-order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ color_order: settings.colorOrder }),
      })

      if (settings.ledMode === 'on') {
        const { r, g, b } = parseHexColor(settings.color)
        await fetch(`${API_BASE}/lights/color`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ r, g, b }),
        })
      }
    } catch (error) {
      console.error('Failed to save general settings', error)
    }
  }

  return (
    <section className="panel-section">
      <h2>General</h2>

      <div className="general-settings-form">
        <div className="field-row">
          <label>
            LED mode
            <select
              value={settings.ledMode}
              onChange={(event) => setSettings((current) => ({ ...current, ledMode: event.target.value }))}
            >
              <option value="schedule">Schedule</option>
              <option value="on">On</option>
              <option value="rainbow">Rainbow Mode</option>
              <option value="off">Off</option>
            </select>
          </label>
        </div>

        {settings.ledMode !== 'off' && (
          <div className="field-row">
            <label>
              Brightness
              <div className="slider-row">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={settings.brightness}
                  onChange={(event) =>
                    setSettings((current) => ({ ...current, brightness: Number(event.target.value) }))
                  }
                />
                <span>{settings.brightness}%</span>
              </div>
            </label>
          </div>
        )}

        {settings.ledMode === 'on' && (
          <div className="field-row">
            <label>
              LED color
              <input
                type="color"
                value={settings.color}
                onChange={(event) => setSettings((current) => ({ ...current, color: event.target.value }))}
              />
            </label>
          </div>
        )}

        <div className="field-row">
          <label>
            LED count
            <input
              type="number"
              min="1"
              value={settings.ledCount}
              onChange={(event) =>
                setSettings((current) => ({ ...current, ledCount: Number(event.target.value) }))
              }
            />
          </label>
        </div>

        <div className="field-row">
          <label>
            LED colour order
            <select
              value={settings.colorOrder}
              onChange={(event) =>
                setSettings((current) => ({ ...current, colorOrder: event.target.value }))
              }
            >
              {colorOrderOptions.map((order) => (
                <option key={order} value={order}>
                  {order}
                </option>
              ))}
            </select>
          </label>
          <p className="field-hint">
            If red and green look swapped on the strip, try a different order.
          </p>
        </div>

        {lighting && lighting.connected === false && (
          <p className="field-hint warning">
            LED strip not connected{lighting.error ? `: ${lighting.error}` : ''}
          </p>
        )}

        <div className="field-row">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={settings.cameraEnabled}
              onChange={(event) =>
                setSettings((current) => ({ ...current, cameraEnabled: event.target.checked }))
              }
            />
            Camera enabled
          </label>
        </div>

        <div className="field-row">
          <label>
            Device name / room name
            <input
              type="text"
              value={settings.deviceName}
              onChange={(event) =>
                setSettings((current) => ({ ...current, deviceName: event.target.value }))
              }
            />
          </label>
        </div>

        <div className="field-row">
          <label>
            Default watering volume (mL)
            <input
              type="number"
              min="0"
              step="10"
              value={settings.defaultWateringVolume}
              onChange={(event) =>
                setSettings((current) => ({ ...current, defaultWateringVolume: Number(event.target.value) }))
              }
            />
          </label>
        </div>

        <button type="button" className="primary save-settings-button" onClick={saveSettings}>
          Save Settings
        </button>
      </div>
    </section>
  )
}
