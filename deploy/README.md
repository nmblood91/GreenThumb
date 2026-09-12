# GreenThumb Pi Deployment

This folder contains the deployment files needed to run GreenThumb on a Raspberry Pi with a single-axis gantry driven by Klipper.

## Files

- `systemd/greenthumb-api.service` — runs the FastAPI backend on port 8000
- `nginx/greenthumb.conf` — serves the built React app and proxies `/api` to the backend
- `klipper/printer.cfg.example` — bare-bones single-axis gantry Klipper template
- `pi/install-green-thumb.sh` — install script for the Pi

## Quick installation on the Pi

1. Connect to the Pi.
2. Clone the repo into `/opt/greenthumb`.
3. Run:

   ```bash
   sudo bash /opt/greenthumb/deploy/pi/install-green-thumb.sh
   ```

4. Verify the API:

   ```bash
   curl http://localhost:8000/
   ```

5. Verify the front end:

   - open `http://<pi-ip>` in a browser

## Service behavior

- The backend runs as a systemd service on port 8000.
- Nginx serves the built frontend from `/opt/greenthumb/frontend/dist`.
- `/api` requests are proxied to the Python API.

## Klipper notes

- This is a simplified single-axis gantry config.
- Use it as a template and tune the pin map, travel range, and homing settings for your exact machine.
- The actual X-axis travel and homing logic should be validated with the mechanical machine before production use.

## Safety

- Keep the first gantry tests very short.
- Confirm the gantry can move freely before sending motion commands from the UI.
- Use a physical e-stop or kill switch for early hardware testing.
