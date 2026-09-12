# GreenThumb Pi Deployment

This folder contains the deployment files needed to run GreenThumb on a Raspberry Pi with a single-axis gantry driven by Klipper.

## Files

- `systemd/greenthumb-api.service` — runs the FastAPI backend on port 8000
- `nginx/greenthumb.conf` — serves the built React app and proxies `/api` to the backend
- `klipper/printer.cfg.example` — bare-bones single-axis gantry Klipper template
- `pi/install-green-thumb.sh` — install script for the Pi

## Quick installation on the Pi

1. Connect to the Pi via SSH.
2. Install git (if not already installed):

   ```bash
   sudo apt update
   sudo apt install -y git
   ```

3. Clone the repo into `/opt/greenthumb`:

   ```bash
   sudo git clone https://github.com/nmblood91/GreenThumb.git /opt/greenthumb
   ```

   **Why `/opt`?** This is the Linux standard for third-party applications and system services. It ensures the app persists across reboots/updates, stays isolated from user files, and works properly with systemd services running at startup.

4. Run the install script (installs Klipper, Python backend, React frontend, Nginx):

   ```bash
   sudo bash /opt/greenthumb/deploy/pi/install-green-thumb.sh
   ```

5. **Configure Klipper**:
   - If your SKR board was **connected during installation**, the serial ID was auto-detected ✓
   - If the board **wasn't connected yet**, connect it now and update `~/printer_data/config/printer.cfg`:
     ```bash
     ls -la /dev/serial/by-id/  # Find your board's ID
     # Edit the file and update the [mcu] serial: line
     nano ~/printer_data/config/printer.cfg
     ```
   - Restart Klipper:
     ```bash
     sudo systemctl restart klipper
     ```

6. Verify the API:

   ```bash
   curl http://localhost:8000/
   ```

7. Verify the front end:

   - Open `http://<pi-ip>` in a browser

## Service behavior

- The backend runs as a systemd service on port 8000.
- Nginx serves the built frontend from `/opt/greenthumb/frontend/dist`.
- `/api` requests are proxied to the Python API.

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
