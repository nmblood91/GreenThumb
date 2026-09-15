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
   - Set username/password (default: `pi` / your password)

2. **Boot the Pi and wait ~2 minutes** for initial setup to complete.

3. **SSH into the Pi**:
   ```bash
   ssh pi@greenthumb.local
   ```

4. **Install git and clone the repo**:
   ```bash
   sudo apt update
   sudo apt install -y git
   sudo git clone --depth 1 https://github.com/nmblood91/GreenThumb.git /opt/greenthumb
   ```

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

8. **Open the web UI**:
   - Open `http://greenthumb.local` in your browser
   - Or use the Pi's IP: `http://<pi-ip>`


## Service behavior

- The backend runs as a systemd service on port 8000.
- Nginx serves the built frontend from `/opt/greenthumb/frontend/dist`.
- `/api` requests are proxied to the Python API.

## Wiring the X Endstop

X homes against a mechanical switch on the **X-STOP** connector. Sensorless
(StallGuard) homing is not usable on this board: the TMC2209 drives its DIAG
output correctly, but that signal is not routed to `PC0`, so the pin reads high
forever and `G28 X` completes instantly without moving.

Mount the switch inside the dead zone at the **left** end of the rail, so the
carriage trips it before reaching the mechanical limit.

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

**Calibrating `position_endstop`.** X0 is the first usable position, and the
switch sits behind it at a negative coordinate, so homing can park clear of the
switch instead of resting on the lower limit. `position_endstop` is how far the
trigger point is from X0, negated — at `-20`, homing ends 20 mm past the switch.
Pick the gap you want, then set `position_min` to the same value. Keep
`position_max` at the travel remaining from X0 to the far dead zone.

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
    └→ [2A Pump Fuse] → HE0 "12/24V" pin

Pump (+) ───────→ 12V Busbar (+)
Pump (-) ───────→ HE0 "PC8" pin
HE0 "GND" ──────→ 12V Busbar GND
```

**Connection summary:**
- Pump positive → 12V Busbar (fused)
- Pump negative → HE0 PC8 pin
- HE0 12/24V pin → 12V Busbar (fused)
- HE0 GND pin → Busbar GND

The SKR board's internal mosfet on PC8 switches the pump circuit on/off. Control via Klipper's `SET_HEATER_TEMPERATURE HEATER=pump TARGET=50` (on) / `TARGET=0` (off) from the FastAPI backend.

See [POWER_SYSTEM.md](../POWER_SYSTEM.md) for complete busbar and fusing specifications.

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
