#!/usr/bin/env bash
set -euo pipefail

echo "Installing GreenThumb on the Pi..."

sudo apt update
sudo apt upgrade -y
sudo apt install -y git python3-venv python3-pip nginx curl

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
