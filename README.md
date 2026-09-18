# GreenThumb

GreenThumb is a Python-based software foundation for a smart indoor planter / grow frame that combines:
- a motion system driven by a BTT SKR Mini E3 V2 and Klipper
- a Raspberry Pi host running Mainsail / Klipper
- four capacitive soil sensors on an I2C hub
- per-zone watering and lighting control
- a Pi camera pipeline for monitoring and timelapse capture

This repository is intentionally structured as a product-ready foundation for a future commercial offering, not just a one-off prototype.

## Product concept

The system is a modular smart planter based on a modified IKEA VITTSJÖ frame with:
- black-brown melamine lower shelf and glass upper shelf
- 1000 mm 2020 extrusion rail mounted to the rear uprights
- GT2 belt + pulley drive powered by a NEMA 17 stepper
- sensorless homing on the motion board
- addressable LED strip for lighting effects and per-plant zones
- 12V peristaltic pump for controlled watering

## Software architecture

This project lays down the initial application stack:

- `greenthumb/config.py` – configuration and environment-driven runtime settings
- `greenthumb/models.py` – zone, sensor, and status dataclasses
- `greenthumb/hardware/` – hardware adapters for Klipper, sensors, LEDs, and pump
- `greenthumb/services/automation.py` – orchestration layer for automated watering and lighting
- `greenthumb/main.py` – FastAPI service exposing a basic API

## Startup

1. Create a virtual environment
2. Install dependencies:
   `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and adjust values for your station
4. Run the service:
   `uvicorn greenthumb.main:app --host 0.0.0.0 --port 8000 --reload`

## API

The app exposes a small initial API surface:

- `GET /health`
- `GET /api/v1/overview`
- `GET /api/v1/sensors`
- `POST /api/v1/water/{zone_id}` (optional `?volume_ml=` overrides the zone setting)
- `POST /api/v1/lights/{mode}`
- `POST /api/v1/motion/home/{axis}`

Example:

`curl http://127.0.0.1:8000/api/v1/overview`

## Local web UI

The initial control surface is a single-axis gantry system served from the Pi itself.

- The gantry moves along one solid rail only.
- Open the app at `http://<pi-host>:8000/`
- Use the page to home the gantry and jog it in precise steps

The first motion API endpoints are:

- `POST /api/v1/gantry/home`
- `POST /api/v1/gantry/move`

## Hardware assumptions

The code is written to be easy to adapt to the actual hardware stack:

- Klipper is the motion layer running on the BTT SKR Mini E3 V2
- Raspberry Pi hosts the application and camera services
- 4 capacitive moisture sensors are mapped to unique addresses and read through a passive I2C hub
- optical / camera monitoring can be integrated later into the same service layer

## Production / commercialization roadmap

This repository is set up to become a real product in stages:

1. Device abstraction layer
   - real vendor-specific drivers for soil sensors, LEDs, and pump control
   - resilient error handling and calibration profiles

2. User dashboards
   - web dashboard with plant health, schedule editor, and zone controls
   - user authentication and access controls

3. Automation rules
   - scheduling, threshold-based irrigation, seasonal growth tuning
   - alerting for low moisture, pump errors, camera anomalies

4. Commercial productization
   - configuration profiles per plant of different species
   - MQTT / websocket streaming, telemetry retention, remote monitoring
   - manufacturing-aware diagnostics and service support workflows

5. Device management
   - onboarding flows, firmware update support, fleet telemetry
   - OTA configuration and remote support tooling

## How watering decisions are made

A background loop polls every sensor once a minute, averages the last ten
readings per zone, and waters a zone whose average falls below its target.
[HOW_WATERING_WORKS.md](HOW_WATERING_WORKS.md) explains the rules and the
reasoning in plain language, for people who won't be reading the code.

## Hardware status

| Component | State |
|---|---|
| Soil sensors | Real — I2C via the seesaw protocol, no simulation |
| Gantry | Real — Klipper over its Unix socket |
| Pump | Real — Klipper `output_pin` on the SKR's HE0 MOSFET |
| LEDs | Real — WS2812B/WS2815/GS8208/WS2811 over SPI, strip type selectable in settings |
| Water level sensor | Real — non-contact sensor on the supply tube, via Klipper |
| Camera | Not built — the UI controls for it are inert |

Automatic watering is disabled by default (`auto_watering_enabled` in
`greenthumb/config.py`). Enable it only after testing the pump by hand and
measuring `pump_flow_ml_per_second` against a real dose, since that figure
converts a requested volume into a pump run time.