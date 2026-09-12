# GreenThumb Pi Deployment

This folder contains the deployment files needed to run GreenThumb on a Raspberry Pi with a single-axis gantry driven by Klipper.

## Files

- `systemd/greenthumb-api.service` — runs the FastAPI backend on port 8000
- `nginx/greenthumb.conf` — serves the built React app and proxies `/api` to the backend
- `klipper/firmware.bin` — pre-built Klipper MCU firmware for SKR Mini E3 V2 (flash via SD card)
- `klipper/printer.cfg.example` — bare-bones single-axis gantry Klipper template
- `pi/install-green-thumb.sh` — install script for the Pi

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

## Flashing the SKR Mini E3 V2 Board

The SKR Mini E3 V2 board comes with an onboard micro-SD card that contains the bootloader. The Klipper MCU firmware is flashed via this SD card.

**Pre-flashed firmware location:** `deploy/klipper/firmware.bin`

### Flashing steps (per unit):

1. **Get the firmware file onto an SD card:**
   - On your laptop: Clone or download the GreenThumb repo
   - Locate `deploy/klipper/firmware.bin`
   - Power off the SKR board and remove its onboard micro-SD card
   - Insert the card into your laptop's card reader
   - Copy `firmware.bin` to the root of the SD card (it must be named exactly `firmware.bin`)

2. **Flash the board:**
   - Safely eject the SD card from your laptop
   - Reinsert the SD card into the SKR Mini E3 V2
   - Power-cycle the board (full power off, then on)
   - Wait 10-20 seconds. The bootloader will detect `firmware.bin` and flash it automatically
   - After a successful flash, the bootloader renames the file to `FIRMWARE.CUR` to prevent re-flashing

3. **Verify success:**
   - Connect the SKR board via USB to the Pi (if not already connected)
   - Run:
     ```bash
     ls -la /dev/serial/by-id/
     ```
   - You should see a device entry containing `Klipper` (e.g., `usb-Klipper_stm32f103xe_XXXXXXXXXXXX-if00`)
   - If it doesn't appear, double-check:
     - `firmware.bin` was correctly copied to the SD card root (not a subfolder)
     - The board was power-cycled (not just reset)
     - The SD card reader worked correctly

4. **Update printer config:**
   - Once the board is detected, re-run the install script or manually update `~/printer_data/config/printer.cfg` with the correct serial ID
   - Restart Klipper:
     ```bash
     sudo systemctl restart klipper
     tail -20 ~/klipper_logs/klippy.log
     ```
   - Look for a clean `mcu 'mcu': Configured` message — no clock errors

## Klipper notes

- This is a simplified single-axis gantry config.
- Use it as a template and tune the pin map, travel range, and homing settings for your exact machine.
- The actual X-axis travel and homing logic should be validated with the mechanical machine before production use.

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
