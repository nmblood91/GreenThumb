from __future__ import annotations

from fastapi import Body, FastAPI
from fastapi.responses import HTMLResponse

from greenthumb.config import settings
from greenthumb.logging_setup import log_event, read_recent_logs, setup_logging
from greenthumb.services.automation import GreenThumbAutomation

setup_logging()

app = FastAPI(
    title=settings.app_name,
    description="Smart planter automation platform for the GreenThumb hardware stack.",
    version="0.1.0",
)

automation = GreenThumbAutomation()


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    zone_rows = "".join(
        f"""
        <div class="zone-row">
            <button class="zone-button" data-zone="{zone['zone_id']}" data-position="{zone['position_mm']}">{zone['name']}</button>
            <input type="number" min="0" max="{settings.gantry_rail_length_mm}" step="1" value="{zone['position_mm']}" data-zone-input="{zone['zone_id']}" />
            <button class="set-position" data-zone="{zone['zone_id']}">Set</button>
        </div>
        """ for zone in automation.get_zone_positions()
    )

    plant_rows = "".join(
        f"""
        <div class="plant-card">
            <h3>{plant['name']}</h3>
            <div class="plant-grid">
                <label>
                    Name
                    <input type="text" data-plant-name="{plant['zone_id']}" value="{plant['name']}" />
                </label>
                <label>
                    Start hour
                    <input type="number" min="0" max="23" value="{plant['light_start_hour']}" data-plant-start="{plant['zone_id']}" />
                </label>
                <label>
                    Stop hour
                    <input type="number" min="0" max="23" value="{plant['light_stop_hour']}" data-plant-stop="{plant['zone_id']}" />
                </label>
            </div>
            <div class="plant-actions">
                <button class="save-plant" data-zone="{plant['zone_id']}">Save Plant</button>
            </div>
        </div>
        """ for plant in automation.get_zone_positions()
    )

    return HTMLResponse(
        """
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>GreenThumb</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background: #0e1d13;
                    color: #eaf3eb;
                    margin: 0;
                    padding: 32px;
                }
                .panel {
                    max-width: 980px;
                    margin: 0 auto;
                    background: #162d1f;
                    border: 1px solid #2c4d39;
                    border-radius: 14px;
                    padding: 24px;
                    box-shadow: 0 12px 30px rgba(0,0,0,0.25);
                }
                .tabs {
                    display: flex;
                    gap: 10px;
                    margin-bottom: 18px;
                    flex-wrap: wrap;
                }
                .tab-btn {
                    background: #214a31;
                    border: 1px solid #35674b;
                    color: white;
                    padding: 12px 16px;
                    border-radius: 10px;
                    cursor: pointer;
                }
                .tab-btn.active { background: #2e7d4b; }
                .tab-panel {
                    display: none;
                }
                .tab-panel.active { display: block; }
                h1, h2, h3 { margin-top: 0; }
                .grid {
                    display: grid;
                    grid-template-columns: repeat(2, minmax(170px, 1fr));
                    gap: 12px;
                    margin-top: 22px;
                }
                .zone-grid, .plant-grid {
                    display: grid;
                    grid-template-columns: 1fr;
                    gap: 10px;
                    margin-top: 18px;
                }
                .plant-card {
                    background: #0f1f17;
                    border: 1px solid #2a4836;
                    border-radius: 12px;
                    padding: 16px;
                    margin-top: 12px;
                }
                .plant-grid {
                    margin-top: 10px;
                }
                label {
                    display: block;
                    font-size: 0.9rem;
                    color: #d8eadc;
                }
                input {
                    width: 100%;
                    padding: 10px 12px;
                    border-radius: 8px;
                    border: 1px solid #335a43;
                    background: #102517;
                    color: #eaf3eb;
                    box-sizing: border-box;
                    margin-top: 6px;
                }
                button {
                    background: #2e7d4b;
                    border: none;
                    border-radius: 10px;
                    color: white;
                    padding: 14px 12px;
                    font-size: 1rem;
                    cursor: pointer;
                }
                button:hover { background: #3c935d; }
                .danger { background: #7b2d2d; }
                .danger:hover { background: #8d3535; }
                .status {
                    margin-top: 18px;
                    background: #0d1a12;
                    border: 1px solid #2c4d39;
                    border-radius: 8px;
                    padding: 12px 14px;
                    min-height: 44px;
                    white-space: pre-wrap;
                }
                .zone-row {
                    display: grid;
                    grid-template-columns: 1fr 120px 110px;
                    gap: 10px;
                    align-items: center;
                }
                .log-box {
                    background: #0d1a12;
                    border: 1px solid #2c4d39;
                    border-radius: 8px;
                    padding: 12px;
                    max-height: 260px;
                    overflow: auto;
                    white-space: pre-wrap;
                    font-family: Consolas, monospace;
                    font-size: 0.82rem;
                }
                .plant-actions {
                    margin-top: 12px;
                }
            </style>
        </head>
        <body>
            <div class="panel">
                <h1>GreenThumb</h1>

                <div class="tabs">
                    <button class="tab-btn active" data-tab="gantry">View / Control Gantry</button>
                    <button class="tab-btn" data-tab="settings">General Settings</button>
                    <button class="tab-btn" data-tab="plants">Plant / Zone Settings</button>
                </div>

                <div id="gantry" class="tab-panel active">
                    <h2>View / Control Gantry</h2>
                    <div class="grid">
                        <button id="homeGantry">Home Gantry</button>
                        <button class="danger" data-distance="-25">Move -25 mm</button>
                        <button data-distance="-10">Move -10 mm</button>
                        <button data-distance="10">Move +10 mm</button>
                        <button data-distance="25">Move +25 mm</button>
                        <button data-distance="50">Move +50 mm</button>
                    </div>
                    <div class="zone-grid">
                        {zone_rows}
                    </div>
                </div>

                <div id="settings" class="tab-panel">
                    <h2>General Settings</h2>
                    <div class="grid">
                        <button id="refreshLogsBtn">Refresh Logs</button>
                        <button id="systemStatusBtn">System Status</button>
                    </div>
                    <div id="status" class="status">Ready.</div>
                    <div class="log-box" id="logBox">Loading recent logs...</div>
                </div>

                <div id="plants" class="tab-panel">
                    <h2>Plant / Zone Settings</h2>
                    <div class="plant-grid">
                        {plant_rows}
                    </div>
                </div>
            </div>

            <script>
                const statusEl = document.getElementById('status');

                function setStatus(message) {
                    statusEl.textContent = message;
                }

                async function callApi(path, options = {}) {
                    const response = await fetch(path, {
                        headers: { 'Content-Type': 'application/json' },
                        ...options
                    });
                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.detail || 'Request failed');
                    }
                    return data;
                }

                document.querySelectorAll('.tab-btn').forEach((button) => {
                    button.addEventListener('click', () => {
                        document.querySelectorAll('.tab-btn').forEach((btn) => btn.classList.remove('active'));
                        document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.remove('active'));
                        button.classList.add('active');
                        document.getElementById(button.dataset.tab).classList.add('active');
                    });
                });

                document.getElementById('homeGantry').addEventListener('click', async () => {
                    setStatus('Homing gantry...');
                    try {
                        const result = await callApi('/api/v1/gantry/home', { method: 'POST' });
                        setStatus(`Homed: ${JSON.stringify(result)}`);
                        logEvent('Gantry homed from UI');
                    } catch (error) {
                        setStatus(`Home failed: ${error.message}`);
                    }
                });

                document.querySelectorAll('[data-distance]').forEach((button) => {
                    button.addEventListener('click', async () => {
                        const distance = Number(button.dataset.distance);
                        setStatus(`Moving gantry ${distance} mm...`);
                        try {
                            const result = await callApi('/api/v1/gantry/move', {
                                method: 'POST',
                                body: JSON.stringify({ distance_mm: distance })
                            });
                            setStatus(`Move result: ${JSON.stringify(result)}`);
                            logEvent(`Gantry move by ${distance} mm`);
                        } catch (error) {
                            setStatus(`Move failed: ${error.message}`);
                        }
                    });
                });

                document.querySelectorAll('.zone-button').forEach((button) => {
                    button.addEventListener('click', async () => {
                        const zoneId = button.dataset.zone;
                        const position = Number(button.dataset.position || 0);
                        setStatus(`Moving to ${zoneId} at ${position} mm...`);
                        try {
                            const result = await callApi(`/api/v1/zones/${zoneId}/move`, { method: 'POST' });
                            setStatus(`Move to zone result: ${JSON.stringify(result)}`);
                            logEvent(`Moved gantry to zone ${zoneId}`);
                        } catch (error) {
                            setStatus(`Zone move failed: ${error.message}`);
                        }
                    });
                });

                document.querySelectorAll('.set-position').forEach((button) => {
                    button.addEventListener('click', async () => {
                        const zoneId = button.dataset.zone;
                        const input = document.querySelector(`[data-zone-input="${zoneId}"]`);
                        const position = Number(input.value);
                        setStatus(`Setting ${zoneId} position to ${position} mm...`);
                        try {
                            const result = await callApi(`/api/v1/zones/${zoneId}/position`, {
                                method: 'POST',
                                body: JSON.stringify({ position_mm: position })
                            });
                            const zoneButton = document.querySelector(`button[data-zone="${zoneId}"]`);
                            if (zoneButton) {
                                zoneButton.dataset.position = result.position_mm;
                                zoneButton.textContent = `${zoneId} @ ${result.position_mm} mm`;
                            }
                            setStatus(`Updated position: ${JSON.stringify(result)}`);
                            logEvent(`Zone ${zoneId} position updated to ${result.position_mm} mm`);
                        } catch (error) {
                            setStatus(`Update failed: ${error.message}`);
                        }
                    });
                });

                document.querySelectorAll('.save-plant').forEach((button) => {
                    button.addEventListener('click', async () => {
                        const zoneId = button.dataset.zone;
                        const nameInput = document.querySelector(`[data-plant-name="${zoneId}"]`);
                        const startInput = document.querySelector(`[data-plant-start="${zoneId}"]`);
                        const stopInput = document.querySelector(`[data-plant-stop="${zoneId}"]`);
                        const name = nameInput.value.trim();
                        const startHour = Number(startInput.value);
                        const stopHour = Number(stopInput.value);

                        setStatus(`Saving plant ${zoneId} settings...`);
                        try {
                            await callApi(`/api/v1/plants/${zoneId}/name`, {
                                method: 'POST',
                                body: JSON.stringify({ name: name })
                            });
                            await callApi(`/api/v1/plants/${zoneId}/lighting`, {
                                method: 'POST',
                                body: JSON.stringify({ start_hour: startHour, stop_hour: stopHour })
                            });
                            setStatus(`Plant ${zoneId} settings saved.`);
                            logEvent(`Plant ${zoneId} settings updated`);
                        } catch (error) {
                            setStatus(`Save failed: ${error.message}`);
                        }
                    });
                });

                async function refreshLogs() {
                    try {
                        const logs = await callApi('/api/v1/logs?lines=100');
                        const logBox = document.getElementById('logBox');
                        logBox.textContent = logs.join('');
                    } catch (error) {
                        document.getElementById('logBox').textContent = `Could not load logs: ${error.message}`;
                    }
                }

                document.getElementById('refreshLogsBtn').addEventListener('click', refreshLogs);
                document.getElementById('systemStatusBtn').addEventListener('click', async () => {
                    setStatus('Checking system status...');
                    try {
                        const overview = await callApi('/api/v1/overview');
                        setStatus(`System status: ${JSON.stringify(overview)}`);
                    } catch (error) {
                        setStatus(`Status check failed: ${error.message}`);
                    }
                });

                async function logEvent(message) {
                    try {
                        await callApi('/api/v1/logs/write', {
                            method: 'POST',
                            body: JSON.stringify({ message: message })
                        });
                    } catch (error) {
                        console.warn('Log write failed', error);
                    }
                }

                refreshLogs();
            </script>
        </body>
        </html>
        """.replace("{zone_rows}", zone_rows).replace("{plant_rows}", plant_rows)
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get(f"{settings.api_prefix}/overview")
async def get_overview() -> dict[str, object]:
    return automation.get_overview()


@app.get(f"{settings.api_prefix}/sensors")
async def read_sensors() -> list[dict[str, object]]:
    return automation.read_sensors()


@app.get(f"{settings.api_prefix}/logs")
async def get_logs(lines: int = 100) -> list[str]:
    return read_recent_logs(lines)


@app.post(f"{settings.api_prefix}/logs/write")
async def write_log(payload: dict[str, str] = Body(default_factory=dict)) -> dict[str, str]:
    message = str(payload.get("message", "")).strip()
    if not message:
        return {"status": "ignored", "message": "empty"}
    log_event(message)
    return {"status": "ok", "message": message}


@app.post(f"{settings.api_prefix}/water/{{zone_id}}")
async def water_zone(zone_id: str, volume_ml: int = 180) -> dict[str, object]:
    result = automation.water_zone(zone_id, volume_ml)
    log_event(f"Zone {zone_id} watered with {volume_ml} mL")
    return result


@app.post(f"{settings.api_prefix}/lights/{{mode}}")
async def set_light_mode(mode: str) -> dict[str, object]:
    result = automation.set_light_mode(mode)
    log_event(f"LED mode changed to {mode}")
    return result


@app.get(f"{settings.api_prefix}/zones")
async def list_zones() -> list[dict[str, object]]:
    return automation.get_zone_positions()


@app.post(f"{settings.api_prefix}/zones/{{zone_id}}/position")
async def set_zone_position(zone_id: str, payload: dict[str, float] = Body(default_factory=dict)) -> dict[str, object]:
    position_mm = float(payload.get("position_mm", 0.0))
    result = automation.set_zone_position(zone_id, position_mm)
    log_event(f"Zone {zone_id} position set to {position_mm} mm")
    return result


@app.post(f"{settings.api_prefix}/zones/{{zone_id}}/move")
async def move_to_zone(zone_id: str) -> dict[str, object]:
    result = automation.move_to_zone(zone_id)
    log_event(f"Moved gantry to zone {zone_id}")
    return result


@app.post(f"{settings.api_prefix}/gantry/home")
async def home_gantry() -> dict[str, object]:
    result = automation.home_gantry()
    log_event("Gantry homed")
    return result


@app.post(f"{settings.api_prefix}/gantry/move")
async def move_gantry(payload: dict[str, float] = Body(default_factory=dict)) -> dict[str, object]:
    distance_mm = float(payload.get("distance_mm", 0.0))
    result = automation.move_gantry_relative(distance_mm)
    log_event(f"Gantry moved by {distance_mm} mm")
    return result


@app.post(f"{settings.api_prefix}/motion/home/{{axis}}")
async def home_axis(axis: str) -> dict[str, object]:
    result = automation.home_motion_axis(axis)
    log_event(f"Axis {axis} homed")
    return result


@app.post(f"{settings.api_prefix}/motion/move")
async def move_axis(payload: dict[str, float] = Body(default_factory=dict)) -> dict[str, object]:
    x_mm = float(payload.get("x_mm", 0.0))
    y_mm = float(payload.get("y_mm", 0.0))
    z_mm = float(payload.get("z_mm", 0.0))
    result = automation.move_axis_relative(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm)
    log_event(f"Manual axis move: x={x_mm} y={y_mm} z={z_mm}")
    return result


@app.get(f"{settings.api_prefix}/plants")
async def list_plants() -> list[dict[str, object]]:
    return [
        {
            "zone_id": plant.zone_id,
            "name": plant.name,
            "position_mm": plant.position_mm,
            "light_start_hour": plant.light_start_hour,
            "light_stop_hour": plant.light_stop_hour,
            "moisture_target": plant.moisture_target,
            "led_start_index": plant.led_start_index,
            "led_end_index": plant.led_end_index,
        }
        for plant in automation.plants
    ]


@app.post(f"{settings.api_prefix}/plants/{{zone_id}}/name")
async def update_plant_name(zone_id: str, payload: dict[str, str] = Body(default_factory=dict)) -> dict[str, object]:
    name = str(payload.get("name", "")).strip()
    result = automation.update_plant_name(zone_id, name)
    log_event(f"Plant {zone_id} renamed to {name}")
    return result


@app.post(f"{settings.api_prefix}/plants/{{zone_id}}/lighting")
async def update_light_schedule(zone_id: str, payload: dict[str, int] = Body(default_factory=dict)) -> dict[str, object]:
    start_hour = int(payload.get("start_hour", 8))
    stop_hour = int(payload.get("stop_hour", 20))
    result = automation.update_light_schedule(zone_id, start_hour, stop_hour)
    log_event(f"Plant {zone_id} light schedule set to {start_hour}:00 - {stop_hour}:00")
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("greenthumb.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
