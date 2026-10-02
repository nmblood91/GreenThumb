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
- Mechanical limit switch for X homing — wired normally-closed. Printer endstop
  modules are usually sold 3-pin; one wire comes off. See
  [deploy/README.md](deploy/README.md) for which

## Compute and monitoring
- Raspberry Pi 4 (1 GB is sufficient). **Raspberry Pi 3 Model B+ is the floor** —
  it keeps the 85 × 56 mm outline and mounting hole positions, the standard 15-pin
  CSI camera connector, 1 GB of RAM and dual-band WiFi. Model B (not B+) also fits
  but is 2.4 GHz only. Do **not** substitute a Pi 3 Model A+ or a Zero 2 W: both
  are a different board outline with different mounting holes, and both are
  512 MB. The Zero 2 W additionally uses the narrow 22-pin CSI connector
- Note that a Pi 3 B+ and a Pi 4 share mounting holes but **not** port positions —
  the Pi 4 has two micro-HDMI jacks, USB-C power, and Ethernet and USB swapped.
  An enclosure needs either a generous port opening or two faceplates
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
- Reservoir. A **bottom or side bulkhead outlet** is the tidier option — the tube
  leaves at the lowest point and stays wet. A plain tank you dip a tube into from
  the top pumps identically; feed it through a hole in the lid rather than over
  the rim, since the rim crossing is a high spot in a suction line
- Weight for the intake end of a dipped tube, so it does not float up and start
  sucking air as the tank drains
- Tubing, sized to the level sensor's 0-13 mm sensing range
- Water delivery nozzle — mounts on the gantry, and must sit above the
  reservoir water line
- Hose fittings and secure mounting. **No anti-drip fitting on the outlet's
  falling leg** — the delivery check depends on that section draining back
  between doses, which is exactly what an anti-drip fitting prevents. A stopped
  peristaltic pump already occludes the tube, so there is no check valve to add
- Non-contact liquid level sensor (CQRobot CQRSENYW001 or similar)
- Optional flow sensor for diagnostics

Vertical order is nozzle, then pump, then reservoir — see
[deploy/README.md](deploy/README.md) for why, and what goes wrong if it is
inverted.

## Lighting
- Addressable LED strip
- 5V or 12V LED power supply depending on product design
- LED controller logic
- Diffuser or housing if needed
- Wiring and connectors

## Power and electronics
- 12V power supply, 5A minimum (7A recommended)
- DC-DC converter 12V to 5V @ 3A
- Main inline fuse: 5A fast-blow (charger output into the busbar)
- Pump circuit fuse: 1A fast-blow (SKR HE0 to pump positive)
- LED circuit fuse: 2A fast-blow (busbar to strip +12V)
- Inline fuse holders, 16 AWG leads, one per fuse above
- Flyback diode for the pump: 1N5822 (3A Schottky), required — see
  [POWER_SYSTEM.md](POWER_SYSTEM.md)
- 2x 3-way lever connectors (Wago 221 or similar) — the diode and the pump leads
  land here rather than being soldered to the pump terminals, see
  [deploy/README.md](deploy/README.md)
- 74AHCT125 level shifter for the LED data line
- Busbar / power distribution block
- Wiring harness and cable routing
- **See [POWER_SYSTEM.md](POWER_SYSTEM.md) for full electrical specifications**

## Software stack
- Klipper on Raspberry Pi
- Python FastAPI service
- Local dashboard
- Sensor and watering service logic

## UI
- smartphone app
- plant profile library

## Notes

This BOM is a functional starting point for a prototype and product planning. A production version should include manufacturing-ready connectors, safety certifications, and reliability checks for pump cycle life, moisture calibration drift, and product enclosure durability.
