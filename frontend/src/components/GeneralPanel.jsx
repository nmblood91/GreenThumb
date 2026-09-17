import { useEffect, useState } from 'react'

// Relative so the page works from any device. An absolute localhost URL resolves
// to whatever machine the browser is on, not the Pi.
const API_BASE = '/api/v1'

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

export function GeneralPanel({ overview, cameraStatus }) {
  const [settings, setSettings] = useState({
    ledMode: 'schedule',
    brightness: 75,
    color: '#00ff80',
    chip: 'WS2812B',
    colorOrder: 'GRB',
    cameraEnabled: true,
  })

  const lighting = overview?.lighting
  const colorOrderOptions = lighting?.color_order_options ?? DEFAULT_COLOR_ORDERS
  const chipOptions = lighting?.chip_options ?? []

  useEffect(() => {
    setSettings((current) => ({
      ...current,
      ledMode: UI_MODE_BY_BACKEND[lighting?.mode] ?? current.ledMode,
      brightness: lighting?.brightness ?? current.brightness,
      color: toHexColor(lighting?.color || current.color),
      chip: lighting?.chip ?? current.chip,
      colorOrder: lighting?.color_order ?? current.colorOrder,
      cameraEnabled: overview?.camera_enabled ?? current.cameraEnabled,
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

      await fetch(`${API_BASE}/lights/chip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chip: settings.chip }),
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
            LED strip type
            <select
              value={settings.chip}
              onChange={(event) =>
                setSettings((current) => ({ ...current, chip: event.target.value }))
              }
            >
              {chipOptions.map((option) => (
                <option key={option.name} value={option.name}>
                  {option.name} ({option.description})
                </option>
              ))}
            </select>
          </label>
          <p className="field-hint">
            Sets the signal timing for your strip. WS2811 drives three LEDs per
            pixel, so set LED count to a third of the LEDs you can see.
          </p>
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

        {lighting && lighting.spi_ready === false && (
          <p className="field-hint warning">
            LED output unavailable, SPI did not open
            {lighting.error ? `: ${lighting.error}` : ''}
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

        <button type="button" className="primary save-settings-button" onClick={saveSettings}>
          Save Settings
        </button>
      </div>
    </section>
  )
}
