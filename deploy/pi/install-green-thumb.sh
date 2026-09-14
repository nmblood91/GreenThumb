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

# Copy printer.cfg from template if it doesn't exist
if [ ! -f /home/pi/printer_data/config/printer.cfg ]; then
  sudo -u pi cp /opt/greenthumb/deploy/klipper/printer.cfg.example /home/pi/printer_data/config/printer.cfg
fi

# Always try to auto-detect and update Klipper serial device
echo "Detecting Klipper device..."
KLIPPER_DEVICE=$(ls /dev/serial/by-id/ 2>/dev/null | grep -i klipper | head -1)

if [ -n "$KLIPPER_DEVICE" ]; then
  echo "✓ Found Klipper device: $KLIPPER_DEVICE"
  sudo -u pi sed -i "s|serial: /dev/serial/by-id/usb-Klipper_.*|serial: /dev/serial/by-id/$KLIPPER_DEVICE|" /home/pi/printer_data/config/printer.cfg
  echo "✓ Updated printer.cfg with serial ID"
else
  echo ""
  echo "⚠️  No Klipper device detected yet"
  echo "After connecting your SKR board via USB, run:"
  echo "  sudo bash /opt/greenthumb/deploy/pi/install-green-thumb.sh"
  echo "to auto-detect and configure it."
  echo ""
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
  sudo -u pi bash -c 'cd ~/klipper && pip install --break-system-packages greenlet jinja2 markupsafe pyserial'
fi

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
ExecStart=/usr/bin/python3 /home/pi/klipper/klippy/klippy.py /home/pi/printer_data/config/printer.cfg -l /home/pi/klipper_logs/klippy.log -a /run/klipper_uds
Restart=always
RestartSec=10
EOF

sudo cp /tmp/klipper.service /etc/systemd/system/klipper.service
sudo systemctl daemon-reload

# Start services
echo "Starting services..."
sudo systemctl enable --now klipper

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
