# GreenThumb Bill of Materials (Initial Prototype / Production Planning)

## Core structure
- Modified IKEA VITTSJÖ frame
- Black-brown melamine lower shelf
- Glass upper shelf
- 2020 aluminum extrusion rail, 1000 mm
- Mounting hardware for rear uprights and rail
- GT2 belt and pulley drive components
- NEMA 17 stepper motor
- Belt tensioning hardware

## Motion and control
- BTT SKR Mini E3 V2 control board
- TMC2209 stepper drivers
- Wiring harness and JST/XH connectors
- Power supply for motion system
- Emergency stop / fuse protection if required
- Sensorless homing configuration and tuning

## Compute and monitoring
- Raspberry Pi 4 or equivalent
- MicroSD card
- Pi Camera v2 or compatible CSI camera
- USB power and breakout hardware as needed
- Cooling solution for Pi, if required

## Sensing
- 4 capacitive soil moisture sensors
- STEMMA QT 5-port passive hub
- 3 sensor address pads (A0/A1) for unique I2C addresses
- Sensor wiring harness

## Watering system
- 12V peristaltic pump
- Reservoir and tubing
- Water delivery nozzle
- Check valves or anti-drip fittings
- Hose fittings and secure mounting
- Optional flow sensor for diagnostics

## Lighting
- Addressable LED strip
- 5V or 12V LED power supply depending on product design
- LED controller logic
- Diffuser or housing if needed
- Wiring and connectors

## Power and electronics
- 24V or 12V main power supply as required
- DC-DC conversion if needed
- Fuses and protection
- Buck converter for 5V logic rails
- Wiring loom, harness, and cable routing

## Software stack
- Klipper/Mainsail on Raspberry Pi
- Python FastAPI service
- Local dashboard
- Sensor and watering service logic

## UI
- smartphone app
- plant profile library

## Notes

This BOM is a functional starting point for a prototype and product planning. A production version should include manufacturing-ready connectors, safety certifications, and reliability checks for pump cycle life, moisture calibration drift, and product enclosure durability.
