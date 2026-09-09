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
- `greenthumb/models.py` – plant, sensor, and status dataclasses
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
- `POST /api/v1/water/{zone_id}?volume_ml=180`
- `POST /api/v1/lights/{mode}`
- `POST /api/v1/motion/home/{axis}`

Example:

`curl http://127.0.0.1:8000/api/v1/overview`

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

## Notes

This current version intentionally uses simulated sensor data and a lightweight abstraction layer so that the project is runnable on a development machine before hardware integration is added on the Pi.

The next practical step is to replace the simulated sensor and pump behaviors with actual Raspberry Pi GPIO / I2C drivers and to integrate with the Klipper API for real motion operations.