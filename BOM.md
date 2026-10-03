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
- **Production target: Raspberry Pi 3 Model A+.** Chosen on cost. Same BCM2837B0
  and 1.4 GHz quad A53 as the 3 B+, dual-band WiFi, the standard 15-pin CSI
  camera connector, and the same 40-pin pinout — so nothing about the wiring or
  the camera ribbon changes. What differs: 512 MB RAM, a single USB-A port
  (the SKR takes it), no Ethernet, and a smaller 65 × 56 mm board with its own
  mounting pattern. See the hardware notes in [ROADMAP.md](ROADMAP.md) for the
  two things still to validate before this is locked
- **Development: Raspberry Pi 4 (1 GB) or Pi 3 Model B+.** A 3 B+ keeps the
  85 × 56 mm outline and mounting holes of the Pi 4; a Pi 4 and a 3 B+ share
  mounting holes but **not** port positions, since the Pi 4 has two micro-HDMI
  jacks, USB-C power, and Ethernet and USB swapped
- Not suitable: Pi Zero / Zero W and any ARMv6 Pi (no 64-bit, and NodeSource
  ships no ARMv6 packages). A Zero 2 W runs but uses the narrow 22-pin CSI
  connector, so the camera ribbon would differ
- Enclosure needs to carry both the A+ and a development board — different
  outlines and different port faces, so plan for two mounting patterns rather
  than one
- MicroSD card
- Pi Camera v2 or compatible CSI camera — **optional paid add-on, not base
  build.** Scoped to timelapse; the standard 15-pin ribbon fits both the A+ and
  the development boards. Live streaming is out of scope, see
  [ROADMAP.md](ROADMAP.md)
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
- Local web app served from the Pi, reached at `http://greenthumb.local` on the
  same network. No smartphone app and no cloud account — see
  [PRIVACY_SECURITY_SPEC.md](PRIVACY_SECURITY_SPEC.md) for why local-only is
  deliberate
- A per-species plant profile library is a roadmap item, not a current part;
  plant definitions live in `greenthumb/plants.py` and only the user-editable
  fields persist

## Notes

This BOM is a functional starting point for a prototype and product planning. A production version should include manufacturing-ready connectors, safety certifications, and reliability checks for pump cycle life, moisture calibration drift, and product enclosure durability.
