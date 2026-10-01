# GreenThumb Pi Deployment

This folder contains the deployment files needed to run GreenThumb on a Raspberry Pi with a single-axis gantry driven by Klipper.

## Files

- `systemd/greenthumb-api.service` — runs the FastAPI backend on port 8000
- `nginx/greenthumb.conf` — serves the built React app and proxies `/api` to the backend
- `klipper/firmware.bin` — pre-built Klipper MCU firmware for SKR Mini E3 V2 (flash via SD card)
- `klipper/printer.cfg.example` — bare-bones single-axis gantry Klipper template
- `pi/install-green-thumb.sh` — install script for the Pi
- `pi/send-gcode.py` — sends one gcode command to Klipper and prints the reply

## Flashing the SKR Mini E3 V2 Board

The SKR Mini E3 V2 board comes with an onboard micro-SD card reader that contains the bootloader. The Klipper MCU firmware is flashed via this SD card.

**Pre-flashed firmware location:** `deploy/klipper/firmware.bin`

### Flashing steps (per unit):

1. **Get the firmware file onto an SD card:**
   - On your laptop: Clone or download the GreenThumb repo
   - Locate `deploy/klipper/firmware.bin`
   - Insert the SD card into your laptop's card reader
   - Copy `firmware.bin` to the root of the SD card (it must be named exactly `firmware.bin`)

2. **Flash the board:**
   - Safely eject the SD card from your laptop
   - Turn off SKR
   - Insert the SD card into the SKR Mini E3 V2
   - Turn on SKR
   - Watch for 2nd red light to begin flashing
   - Once that stops it is flashed
   - After a successful flash, the bootloader renames the file to `FIRMWARE.CUR` to prevent re-flashing

## Fresh Pi Setup

For a clean installation with the latest OS, start here:

1. **Flash Pi OS** using [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   - Choose **Raspberry Pi OS (64-bit)**
   - Set hostname: `greenthumb`
   - Enable SSH
   - **Username must be `pi`** — the systemd service, the Klipper paths, and the
     install script all reference `/home/pi` and run the API as `pi`. Any other
     username requires editing those in step with each other.

2. **Boot the Pi and wait ~2 minutes** for initial setup to complete.

3. **SSH into the Pi**:
   ```bash
   ssh pi@greenthumb.local
   ```

4. **Install git and clone the repo**:
   ```bash
   sudo apt update
   sudo apt install -y git
   sudo mkdir -p /opt/greenthumb
   sudo chown pi:pi /opt/greenthumb
   git clone --depth 1 https://github.com/nmblood91/GreenThumb.git /opt/greenthumb
   ```

   `sudo` creates the directory because `/opt` is root-owned, but the clone
   itself runs as `pi` so the checkout and `.git` belong to `pi` from the start.
   Cloning with `sudo` instead leaves a root-owned repo, and every later
   `sudo git` writes root-owned objects into `.git` that plain git then can't
   update.

5. **Run the installation script** (this installs everything):
   ```bash
   sudo bash /opt/greenthumb/deploy/pi/install-green-thumb.sh
   ```
   This will take 10-15 minutes. Watch for "GreenThumb install complete" at the end.

6. **Configure Klipper** (if SKR board is connected):
   - If auto-detected: ✓ Already configured
   - If not detected: See **Configure Klipper** section below

7. **Verify everything is running**:
   ```bash
   sudo systemctl status klipper
   sudo systemctl status greenthumb-api.service
   sudo systemctl status nginx
   ```

   The install script also prints an interface check at the end. If it reports
   `/dev/i2c-1` or `/dev/spidev0.0` missing, reboot and re-run it — the script is
   idempotent and safe to run repeatedly.

   Read the sensors directly, without going through the API:
   ```bash
   /opt/greenthumb/.venv/bin/python -m greenthumb.hardware.soil_sensors
   ```
   Sensors that are absent or unplugged report `-1` rather than a fake value.

   Check the bus is reliable, not just working, after any cabling change:
   ```bash
   /opt/greenthumb/.venv/bin/python -m greenthumb.hardware.soil_sensors --soak 120
   ```
   This hammers every address for two minutes and reports an error rate each.
   Intermittent I2C trouble is invisible in a single read and easy to mistake for
   a flaky sensor months later — see **I2C cable length** below.

8. **Open the web UI**:
   - Open `http://greenthumb.local` in your browser
   - Or use the Pi's IP: `http://<pi-ip>`


## Updating an installed Pi

```bash
cd /opt/greenthumb
git pull
sudo systemctl restart greenthumb-api.service
```

**Never `sudo git pull`.** The repo is owned by `pi`, and running git as root
writes root-owned objects into `.git` that plain git can no longer update. `sudo`
is only needed for the initial clone's parent directory and for the install
script.

Re-run the install script instead of pulling when the change touches
`printer.cfg.example`, the systemd units, or the nginx config — those are copied
out of the repo at install time, so a pull alone does not apply them.

## Service behavior

- The backend runs as a systemd service on port 8000.
- Nginx serves the built frontend from `/opt/greenthumb/frontend/dist`.
- `/api` requests are proxied to the Python API.

## Wiring the X Endstop

X homes against a mechanical switch on the **X-STOP** connector. Sensorless
(StallGuard) homing is not usable on this board: the TMC2209 drives its DIAG
output correctly, but that signal is not routed to `PC0`, so the pin reads high
forever and `G28 X` completes instantly without moving.

Mount the switch inside the dead zone at the **right** end of the rail, next to
the motor, so the carriage trips it before reaching the mechanical limit.

Homing at the motor end keeps the belt span between the pulley and the carriage
at its shortest when the switch trips, which makes the reference the most
repeatable point on the rail. The effect is tens of microns on a 1 m GT2 belt, so
treat it as a tiebreaker rather than a requirement -- either end works, and the
switch can move as long as `position_endstop`, `position_max` and the park
position in `homing_override` move together.

**Wiring** — two pins, no power needed:

```
Switch COM ──→ X-STOP  GND
Switch NC  ──→ X-STOP  signal (PC0)
```

X-STOP is a 2-pin connector, and a mechanical switch is a passive contact:
`^PC0` enables the MCU's internal pull-up, so the pin idles high on its own and
the switch only has to pull it to ground. Nothing here needs power.

**Most limit switches sold for printers are 3-pin, so one wire comes off.**
Which one depends on the board, and the S / G / V silkscreen is not a reliable
guide — on many of them it is generic connector labelling over a straight
passthrough of the microswitch's own C / NO / NC terminals, with no LED and no
supply pin at all. Trace it before cutting: multimeter on continuity, work the
lever, and find the pair that is **closed with the lever released**. That is
common and NC, and those are the two you keep.

A common case is S=C, G=NO, V=NC, which means keeping the *outer* two pins and
removing the middle one. Lift the retention tab in the connector housing with a
pin and slide the unwanted contact out rather than re-crimping.

**Prefer NC over NO** when the switch offers both. A broken wire or an unseated
connector then reads the same as triggered, so homing fails immediately. Wired
normally-open, a broken wire is indistinguishable from a healthy untriggered
switch, and the first sign of trouble is the carriage driving into the end of
the rail.

`printer.cfg` uses `endstop_pin: ^!PC0`, which expects a **normally-closed**
switch, matching Y and Z. Verify before homing:

```bash
python3 /opt/greenthumb/deploy/pi/send-gcode.py QUERY_ENDSTOPS
```

Released it must read `stepper_x:open`; held down by hand, `stepper_x:TRIGGERED`.
If those are backwards the switch is wired normally-open — use `^PC0` instead of
`^!PC0`, rather than rewiring.

**Calibrating `position_endstop`.** X960 is the last usable position and the
switch sits past it, so homing can retract clear of the switch instead of resting
on the upper limit. `position_endstop` is the coordinate at which the switch
trips — at `980`, it sits 20 mm beyond usable travel. Measure it against your own
mounting, then set `position_max` to the same value and park 20 mm short of it in
`homing_override`. X0 stays the left end of usable travel, so zone positions are
unaffected by which end the switch lives at.

`homing_positive_dir: True` is stated explicitly. Klipper would infer it from
`position_endstop` sitting at the top of the range, but then a later edit to
`position_max` could silently reverse which way the carriage homes.

## Wiring the Pump to SKR Board

The peristaltic pump is controlled via the SKR's **HE0 (heater) connector** on
the bottom edge of the board, which is how Klipper can switch it on and off.

**HE0 switches the ground side, not the positive side.** The mosfet sits between
PC8 and ground. The connector's other pin is the board's own 12V input rail
brought out, so it is live whenever the SKR is powered — but the pump does not
run, because its return path through PC8 stays open until Klipper closes the
mosfet.

That is worth being clear about, because it decides where the fuse goes. The
pump's current path is:

```
SKR VIN → HE0 12/24V pin → pump (+) → motor → pump (−) → PC8 → mosfet → GND
```

A fuse protects the pump only if it sits somewhere in *that* loop.

**Wiring — both pump leads land on HE0:**
```
HE0 "12/24V" ──[1A Pump Fuse]──→ Pump (+)
HE0 "PC8"    ──────────────────→ Pump (−)
```

**Connection summary:**
- HE0 12/24V pin → 1A fuse → pump positive
- Pump negative → HE0 PC8 pin
- Nothing from the pump goes to the busbar — the SKR's own power feed supplies it
- If your HE0 connector has a third GND pin, it is unused here; the mosfet
  already grounds the pump through PC8

Pump (+) could equally be taken from the busbar, since the HE0 12/24V pin is
electrically the same node. Keeping the pair together at the connector just
means one plug to pull and one fuse unambiguously in series with the motor.

### Flyback diode (required)

HE0's mosfet is designed for a heater cartridge, which is purely resistive. A
pump is an inductive motor: when the mosfet switches off, the collapsing field
drives the negative terminal above +12V, and that spike can destroy the mosfet.
A flyback diode gives the current a loop through the motor winding instead.

Fit it **across the pump's own two terminals**, in parallel with the motor — not
inline with a wire, and not at the board end.

```
  HE0 "12/24V"
       │
  [1A Pump Fuse]        in series, at the board end
       │
       ├──────────────┐
       │              │
    Pump (+)         ═╧═   STRIPED band at the top
       │              ▲    (cathode to the positive side)
   [ MOTOR ]          │
       │              │    1N5822, in parallel,
    Pump (−)          │    at the pump end
       │              │
       ├──────────────┘
       │
  HE0 "PC8"  ──→ mosfet ──→ GND
```

Note the diode sits *downstream* of the fuse. That is deliberate: if you fit it
backwards, the fuse is the thing that goes.

**Striped end (cathode) to the positive terminal.** Orientation is not optional:
reversed, the diode sits forward-biased across 12V as a dead short and blows the
1A pump fuse the moment you power up.

Solder it to the pump terminals and heat-shrink each leg, or solder across the
leads close to the pump. Wire between the diode and the motor is unprotected
inductance, so keep it short.

Part: a **1N5822** (3A Schottky) is comfortable overkill for a 0.2-0.3A pump and
costs the same as anything smaller, so it is the easy choice. A 1N5817 or 1N4001
is electrically adequate here too. Schottky parts switch faster and clamp the
spike more cleanly than a 1N400x.

The pump is declared in `printer.cfg` as an `[output_pin]`, not a heater:

```
[output_pin pump]
pin: PC8
value: 0
shutdown_value: 0
```

`shutdown_value: 0` stops the pump if Klipper errors out mid-dose. It is
deliberately not a `[heater_generic]` — that requires a temperature sensor, and
Klipper's `verify_heater` watchdog would fault partway through every watering
when commanded heat produced no temperature rise.

The backend doses with `SET_PIN PIN=pump VALUE=1`, a `G4` dwell, then
`SET_PIN PIN=pump VALUE=0`, sent as a single script so the switch-off is queued
on the MCU and a dropped connection cannot strand the pump running.

See [POWER_SYSTEM.md](../POWER_SYSTEM.md) for complete busbar and fusing specifications.

## I2C cable length

The soil sensors hang off a hub tree rather than home runs back to the Pi. A
representative layout is four 150 mm sensor drops into two sub-hubs, 400 mm from
each sub-hub to a master hub, and 100 mm from there to the Pi — about **1.5 m of
cable in total**.

**Total bus capacitance is what matters, not the longest run**, and it is the sum
of every branch. I2C allows 400 pF; at roughly 60 pF/m that 1.5 m contributes
about 90 pF, plus ~10 pF per sensor pin and a little for the hub boards. Around
145 pF, so roughly a third of budget. The tree also uses *less* cable than home
running each sensor would.

Too much capacitance slows the rise time of SDA and SCL, so the line has not
reached a valid high when the clock samples it. It does not fail cleanly — you
get occasional NACKs, which surface here as sensors randomly reporting `-1`.

Three things keep it healthy:

- **The I2C clock is set to 50 kHz** by the install script
  (`dtparam=i2c_arm_baudrate` in the boot config, applied after a reboot). Half
  the default speed means twice the time for the line to rise. The sensors are
  read once a minute, so the lost bandwidth costs nothing.
- **Use passive hubs with no pull-up resistors.** Each STEMMA sensor already
  carries 10 kΩ pull-ups; four in parallel with the Pi's built-in 1.8 kΩ is
  already about 1 kΩ, or 3.3 mA, which is at the I2C sink limit. Every hub that
  adds its own drags that lower until the sensors cannot pull the line
  convincingly low. If your hubs have them, remove the resistors rather than
  buying different hubs.
- **Route away from the LED data line and the stepper wiring.** 1.5 m of I2C run
  parallel to an 800 kHz WS2812B data line will cause more trouble than the
  capacitance ever will. Crossing at right angles is fine; running alongside is
  not. Sharing a few centimetres near the Pi header is harmless.

Verify with a soak test rather than a single read:

```bash
/opt/greenthumb/.venv/bin/python -m greenthumb.hardware.soil_sensors --soak 120
```

Clean means zero errors. Under 1% is tolerable. Above that, slow the clock
further, check the hubs for stacked pull-ups, and look at routing. Exit status is
non-zero when any populated address exceeds 1%, so it can gate a scripted check.

## Plumbing layout

Vertical order matters more than anything else about the water path. Top to
bottom: **nozzle, pump, reservoir.**

```
   HIGH POINT  ──────── top of the outlet run
     │      ╲
     │       ╲  falling leg  ──[ level sensor clamps here ]
     │        ╲
     │       NOZZLE  ──────── over the pot
     │
     │   outlet line (rising)
     │
   PUMP  ────────────── above the reservoir water line
     │
     │   suction line, short and steadily rising
     │
   RESERVOIR  ───────── lowest; water line below the nozzle
```

### Nozzle above the reservoir water line

This is the safety-critical one. A siphon can only run downhill, so with the
tank at the bottom a failed tube seal or a popped fitting means nothing happens
— the water has nowhere to go. Invert it and the same failure drains the whole
tank onto the floor.

What makes this safe rather than merely lucky is that **a stopped peristaltic
pump is a closed valve**: its rollers occlude the tube, so there is no open path
even when it is off. That is also why raising the reservoir would not let you
drop the pump — you would just be relying on that same occlusion to hold back a
gravity feed permanently instead of only while idle.

### Pump above the water line

The pump does not need to sit below the water; peristaltic pumps self-prime.
The cost is that the pump inlet becomes the *highest* point of the suction line
and so the first place to go dry if prime slips. That is a non-event in itself —
prime recovers in seconds — but it decides where the level sensor goes.

Keep the suction line short and steadily rising, with no high spots to trap air.
Suction joints are far less forgiving than pressure joints: a pinhole that would
never drip on the outlet side will break prime on the inlet side.

### Reservoir, and the suction tube

A tank with a **bottom or side bulkhead outlet** is the tidier option: the tube
leaves at the lowest point and stays wet whenever there is water above it. Worth
looking for — *bulkhead fitting*, *hydroponic reservoir with drain*, or any tank
sold with a spigot. A plain tank plus an aftermarket bulkhead fitting works too.

**A tube simply dipped in from the top is fine.** It needs no fittings and
pumps identically. Two things to watch, both about prime rather than sensing:

- **The rim crossing is a high spot**, which is exactly what a suction line is
  not supposed to have. Keep it as low as you can — through a hole in the lid
  rather than over the edge — and keep the whole run short.
- **Weight the intake end** so it stays at the bottom. A tube that floats up as
  the tank drains starts sucking air well before the tank is empty.

Note that with a dipped tube there is nowhere useful to sense *reservoir level*:
every reachable section of tube sits above the water line. That is why the
sensor lives on the outlet instead, described next.

## Wiring the Water Level Sensor

A non-contact liquid sensor (CQRobot CQRSENYW001 or similar) clamped around the
**outlet** tube confirms that a dose actually delivered water, instead of the
system running the pump and logging a dose that delivered nothing.

**Clamp it on the falling leg — after the high point, before the nozzle.**

### Why it verifies rather than blocks

This sensor does not gate watering. It cannot: the falling leg drains into the
pot after every dose, so it reads dry whenever the pump is idle, and a pre-check
would refuse every watering forever.

Instead the software starts the pump, watches the sensor a few seconds in, and
records whether water arrived. Running a peristaltic pump dry for a few seconds
is harmless, so there is nothing to protect against by checking first. What you
get in exchange is a better question answered: not "is water available at the
inlet" but "did water reach the plant" — which also catches a clog, a kink, a
split pump tube, or a pump turning with nothing engaged.

A dose that delivers nothing is logged as a warning, flagged in the History tab
as a solid red marker, and reported in the status bar. Nothing is blocked; the
next dose runs and re-checks, so a refilled tank clears the condition by itself.

### Where exactly to clamp it

The placement is fussier than it looks, because half the outlet run holds water
permanently:

- **Rising leg (pump → high point): stays full.** The stopped pump seals the
  bottom and water cannot climb over the peak to escape. A sensor here reads wet
  forever and tells you nothing.
- **Falling leg (high point → nozzle): drains.** It siphons into the pot when
  the pump stops and refills on the next dose. This is the only section with a
  signal in it.

**Do not fit an anti-drip fitting on the falling leg.** It exists to stop
exactly the drain-back this depends on. The cost of leaving it out is a few mL
dribbling into the pot it was already headed for.

Sizing: about 7 mL of 4 mm ID tube fills in roughly four seconds at the pump's
flow rate, against a 500 ms sensor response and a 60-second dose, so the timing
is not tight. `delivery_check_delay_seconds` in `greenthumb/config.py` sets how
long to wait before the first look; raise it if the falling leg is unusually
long.

**Set the board's dial switch to 3.3V output before wiring.** The SKR's endstop
inputs are 3.3V; at the 5V setting the sensor would overdrive the pin. With it at
3.3V the signal wire connects directly, no divider or level shifter.

```
Sensor VCC (red)   ----> 5V (Pi header pin 2, or the busbar 5V rail)
Sensor GND (black) ----> common ground, shared with the SKR
Sensor OUT (green) ----> Y-STOP signal pin (PC1)
```

Z-STOP is the spare if Y-STOP is taken. The sensor senses through 0-13 mm, so
check your tube's outer diameter falls inside that, and adjust the sensitivity
pot if the board has one.

**Confirm polarity before trusting it.** Bench the sensor first, powered at 5V
with the dial at 3.3V, and read the output on a full tube and an empty one —
allow 500 ms between changing the tube and reading, that is its response time.
Then check Klipper agrees:

```bash
python3 /opt/greenthumb/deploy/pi/send-gcode.py QUERY_FILAMENT_SENSOR SENSOR=water_supply
```

A full tube must report detected. If it reads backwards, change `switch_pin` to
`^!PC1` in `printer.cfg` and re-run the install script rather than rewiring.

Once confirmed, set `WATER_SENSOR_ENABLED=true` in `/opt/greenthumb/.env` and
restart the API.

Enabling it changes nothing about when watering happens — it only adds the
check afterwards. Three outcomes are recorded per dose: **delivered** (the line
read wet during the run), **not delivered** (it read dry throughout, logged as a
warning and drawn in red on the chart), and **unknown** (the sensor never
answered). Unknown is deliberately distinct from a failure: "we did not look" and
"we looked and saw nothing" are different problems.

## Wiring the LED Strip

Supported strips, selectable as **LED strip type** in the settings page:

| Chip | Supply | Pixels | Pads | Notes |
|---|---|---|---|---|
| WS2812B | 5V | one per LED | 3 | The common 5V strip |
| WS2815 | 12V | one per LED | 4 | 4th pad is a backup data line |
| GS8208 | 12V | one per LED | 3 | Often sold as "12V WS2812B" |
| WS2811 | 12V | one per **3** LEDs | 3 | Set LED count to LEDs / 3 |

They use different bit timing, so picking the wrong one gives no light or
garbage rather than a subtle colour shift. **To tell 12V strips apart, check the
cut marks.** Cuttable between every LED means one pixel per LED (WS2815 /
GS8208); cuttable only every third LED means WS2811.

```
12V Busbar (+) --[2A Fuse]--> Strip +V     (12V strips; a 5V strip needs its
Busbar GND -----> Strip GND --+-- Pi GND    own 5V supply, not the DC-DC)
Pi GPIO10 (pin 19, MOSI) -----+-> [74AHCT125 level shifter] --> Strip DIN
```

The 2A fuse is what keeps a shorted solder joint at the strip's input end from
taking down the Pi and the motion board with it. Sizing and the 5V case are in
[POWER_SYSTEM.md](../POWER_SYSTEM.md).

**The data pin must be GPIO10 (header pin 19).** The driver clocks the waveform
out of the SPI peripheral, which only exists on that pin. This avoids needing
root, which the usual PWM/DMA approach requires.

Two things that look like software faults but are not:

- **Pi ground must tie to the supply ground.** The data line is measured against
  ground; without a shared reference the strip sees nothing. Most common failure.
- **Use a level shifter.** These chips want logic high at roughly 70% of their
  supply, and the Pi only swings to 3.3V. Some strips tolerate it; flicker or junk
  on the first few pixels is this, not a bug.

**Do not power the strip from the Pi.** A 5V WS2812B strip pulls about 3.6A at 60
LEDs full white, far past the Pi's rail. 12V strips draw roughly a third of that,
but either way the strip's supply must not touch the Pi's pins.

If red and green come out swapped, change **LED colour order** in settings.
Selecting a strip type resets that order to the one that chip normally uses, so
choose the type first and adjust the order afterwards.

## Troubleshooting

If the installation script disconnects or fails, use these commands to diagnose:

**Check service status:**
```bash
sudo systemctl status klipper
sudo systemctl status greenthumb-api.service
sudo systemctl status nginx
```

**Check Klipper logs:**
```bash
tail -50 ~/klipper_logs/klippy.log
```

**Check GreenThumb API logs:**
```bash
sudo journalctl -u greenthumb-api.service -n 50
```

**Verify directories exist:**
```bash
ls -la /opt/greenthumb/
ls -la ~/printer_data/config/
```

**Restart services if needed:**
```bash
sudo systemctl restart klipper
sudo systemctl restart greenthumb-api.service
sudo systemctl restart nginx
```

If the install script fails midway, you can safely re-run it — it checks for existing installations and skips already-completed steps.

## Safety

- Keep the first gantry tests very short.
- Confirm the gantry can move freely before sending motion commands from the UI.
- Use a physical e-stop or kill switch for early hardware testing.
