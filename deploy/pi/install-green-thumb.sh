#!/usr/bin/env bash
set -euo pipefail

echo "Installing GreenThumb on the Pi..."

sudo apt update
sudo apt install -y git python3-venv python3-pip nginx curl

# Install core dependencies
echo "Installing build dependencies..."
sudo apt install -y python3-dev libffi-dev build-essential libncurses-dev libusb-dev avrdude gcc-arm-none-eabi binutils-arm-none-eabi

# Create printer_data and log directories
sudo -u pi mkdir -p /home/pi/printer_data/config /home/pi/printer_data/gcodes /home/pi/klipper_logs

# Auto-detect Klipper device with retry (up to 30 seconds)
echo "Detecting Klipper device (waiting up to 30 seconds)..."
KLIPPER_DEVICE=""
for i in {1..30}; do
  KLIPPER_DEVICE=$(ls /dev/serial/by-id/ 2>/dev/null | grep -i klipper | head -1)
  if [ -n "$KLIPPER_DEVICE" ]; then
    echo "✓ Found Klipper device: $KLIPPER_DEVICE"
    break
  fi
  if [ $i -lt 30 ]; then
    echo "  Waiting... ($i/30)"
    sleep 1
  fi
done

if [ -z "$KLIPPER_DEVICE" ]; then
  echo ""
  echo "⚠️  No Klipper device detected after 30 seconds"
  echo "Make sure your SKR board is connected and powered on."
  echo "After connecting it, run:"
  echo "  sudo bash /opt/greenthumb/deploy/pi/install-green-thumb.sh"
  echo ""
fi

# Generate printer.cfg from template with actual device ID
if [ -n "$KLIPPER_DEVICE" ]; then
  sed "s|serial: /dev/serial/by-id/usb-Klipper_xxx|serial: /dev/serial/by-id/$KLIPPER_DEVICE|" /opt/greenthumb/deploy/klipper/printer.cfg.example > /tmp/printer.cfg
  sudo -u pi cp /tmp/printer.cfg /home/pi/printer_data/config/printer.cfg
  echo "✓ Generated printer.cfg with device serial ID"
else
  # Fallback: copy template as-is if device not detected yet
  if [ ! -f /home/pi/printer_data/config/printer.cfg ]; then
    sudo -u pi cp /opt/greenthumb/deploy/klipper/printer.cfg.example /home/pi/printer_data/config/printer.cfg
  fi
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Installing Node.js 20 LTS..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt install -y nodejs
fi

cd /opt || exit 1
if [ ! -d "/opt/greenthumb" ]; then
  sudo git clone --depth 1 https://github.com/nmblood91/GreenThumb.git /opt/greenthumb
fi

cd /opt/greenthumb
sudo mkdir -p /opt/greenthumb/logs
sudo chown pi:pi /opt/greenthumb/logs
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cd /opt/greenthumb/frontend
npm install
npm run build

# Install Klipper host software (last, to avoid blocking on large clone)
echo "Installing Klipper host software..."
if [ ! -d /home/pi/klipper ]; then
  sudo -u pi bash -c 'cd ~ && git clone --depth 1 https://github.com/Klipper3d/klipper.git'
fi
# Always install/update Klipper dependencies
sudo -u pi bash -c 'pip install --break-system-packages cffi greenlet jinja2 markupsafe pyserial'

# Always create/update the systemd service (even if Klipper was already cloned)
cat > /tmp/klipper.service << 'EOF'
[Unit]
Description=Klipper 3D Printer Firmware
Documentation=https://www.klipper3d.org/
After=network-online.target
Wants=network-online.target

[Install]
WantedBy=multi-user.target

[Service]
Type=simple
User=pi
RemainAfterExit=yes
RuntimeDirectory=klipper
ExecStart=/usr/bin/python3 /home/pi/klipper/klippy/klippy.py /home/pi/printer_data/config/printer.cfg -l /home/pi/klipper_logs/klippy.log -a /run/klipper/uds
Restart=always
RestartSec=10
EOF

sudo cp /tmp/klipper.service /etc/systemd/system/klipper.service
sudo systemctl daemon-reload

# Start Klipper and verify it connects
echo "Starting Klipper..."
sudo systemctl enable --now klipper
sleep 3

# Check if Klipper connected to MCU
echo "Verifying Klipper connection..."
if sudo -u pi grep -q "MCU 'mcu' is ready" /home/pi/klipper_logs/klippy.log 2>/dev/null; then
  echo "✓ Klipper connected to MCU successfully"
elif sudo systemctl is-active --quiet klipper; then
  echo "✓ Klipper service is running"
else
  echo "⚠️  Klipper service failed to start"
  echo "Check logs with: tail -50 ~/klipper_logs/klippy.log"
  echo "Or systemd status: sudo systemctl status klipper"
fi

sudo cp /opt/greenthumb/deploy/systemd/greenthumb-api.service /etc/systemd/system/greenthumb-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now greenthumb-api.service

sudo cp /opt/greenthumb/deploy/nginx/greenthumb.conf /etc/nginx/sites-available/greenthumb.conf
sudo ln -sf /etc/nginx/sites-available/greenthumb.conf /etc/nginx/sites-enabled/greenthumb.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

sudo systemctl status greenthumb-api.service --no-pager

printf "\nGreenThumb install complete.\n"
printf "Open: http://$(hostname -I | awk '{print $1}')\n"
printf "API: http://$(hostname -I | awk '{print $1}'):8000\n"
