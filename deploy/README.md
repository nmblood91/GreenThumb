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

The peristaltic pump is controlled via the SKR's **HE0 (heater) connector** on the bottom edge of the board. This is a switched 12V output that turns the pump on/off.

**SKR Mini E3 V2.0 HE0 connector pinout (3 pins):**
```
[12/24V] [PC8] [GND]
```

**Wiring from power busbar to SKR:**
```
12V Busbar (+)
    ├→ [5A Main Fuse] → SKR Main Power Input
    └→ [1A Pump Fuse] → HE0 "12/24V" pin

Pump (+) ───────→ 12V Busbar (+)
Pump (-) ───────→ HE0 "PC8" pin
HE0 "GND" ──────→ 12V Busbar GND
```

**Connection summary:**
- Pump positive → 12V Busbar (fused)
- Pump negative → HE0 PC8 pin
- HE0 12/24V pin → 12V Busbar (fused)
- HE0 GND pin → Busbar GND

### Flyback diode (required)

HE0's mosfet is designed for a heater cartridge, which is purely resistive. A
pump is an inductive motor: when the mosfet switches off, the collapsing field
drives the negative terminal above +12V, and that spike can destroy the mosfet.
A flyback diode gives the current a loop through the motor winding instead.

Fit it **across the pump's own two terminals**, in parallel with the motor — not
inline with a wire, and not at the board end.

```
   +12V  (fused, from busbar)
     │
     ├──────────────────┐
     │                  │
  Pump (+)         ═══╪◀═══   diode, STRIPED end toward +12V
     │                  │
  [ MOTOR ]             │
     │                  │
  Pump (−)              │
     │                  │
     ├──────────────────┘
     │
   HE0 PC8  (mosfet switches this to ground)
```

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
Supply (+) ----> Strip +V        (5V or 12V, matching the chip)
Supply GND ----> Strip GND --+-- Pi GND (any ground pin)
Pi GPIO10 (pin 19, MOSI) ----+-> [74AHCT125 level shifter] --> Strip DIN
```

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
