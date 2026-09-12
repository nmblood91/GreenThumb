#!/usr/bin/env bash
set -euo pipefail

echo "Installing GreenThumb on the Pi..."

sudo apt update
sudo apt upgrade -y
sudo apt install -y git python3-venv python3-pip nginx curl

# Install Klipper dependencies
echo "Installing Klipper and dependencies..."
sudo apt install -y python3-dev libffi-dev build-essential libncurses-dev libusb-dev avrdude gcc-arm-none-eabi binutils-arm-none-eabi

# Install Klipper host software (must run as pi user, not root)
if [ ! -d /home/pi/klipper ]; then
  sudo -u pi bash -c 'cd ~ && git clone https://github.com/Klipper3d/klipper.git && cd klipper/scripts && bash ./install-octopi.sh'
else
  echo "Klipper already installed, skipping..."
fi

# Create printer_data directories
mkdir -p ~/printer_data/config ~/printer_data/gcodes

# Copy printer.cfg from template if it doesn't exist
if [ ! -f ~/printer_data/config/printer.cfg ]; then
  cp /opt/greenthumb/deploy/klipper/printer.cfg.example ~/printer_data/config/printer.cfg

  # Auto-detect Klipper serial device
  KLIPPER_DEVICE=$(ls /dev/serial/by-id/ 2>/dev/null | grep -i klipper | head -1)

  if [ -n "$KLIPPER_DEVICE" ]; then
    echo "✓ Found Klipper device: $KLIPPER_DEVICE"
    sed -i "s|serial: /dev/serial/by-id/usb-Klipper_xxx|serial: /dev/serial/by-id/$KLIPPER_DEVICE|" ~/printer_data/config/printer.cfg
    echo "✓ Updated printer.cfg with serial ID"
  else
    echo ""
    echo "⚠️  No Klipper device detected yet"
    echo "You must connect your SKR board and update the [mcu] serial line:"
    echo "  1. Connect your SKR board via USB"
    echo "  2. Run: ls -la /dev/serial/by-id/"
    echo "  3. Find your Klipper device and copy its full ID"
    echo "  4. Edit ~/printer_data/config/printer.cfg and update the serial line"
    echo "  5. Restart Klipper: sudo systemctl restart klipper"
    echo ""
  fi
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Installing Node.js 20 LTS..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt install -y nodejs
fi

cd /opt || exit 1
if [ ! -d "/opt/greenthumb" ]; then
  sudo git clone https://github.com/<your-user>/<your-repo>.git /opt/greenthumb
fi

cd /opt/greenthumb
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cd /opt/greenthumb/frontend
npm install
npm run build

# Start Klipper service
echo "Starting Klipper service..."
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
