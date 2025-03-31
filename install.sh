#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <branch-name>"
    exit 1
fi

BRANCH_NAME=$1

# Install necessary packages
sudo pacman -S --noconfirm python python-pip python-virtualenv

# Create a virtual environment
python -m venv venv

# Install required packages
venv/bin/pip install -r requirements.txt

# Create systemd service file
CURRENT_DIR=$(pwd)
SERVICE_FILE="$CURRENT_DIR/mercourier-${BRANCH_NAME}.service"

cat > $SERVICE_FILE <<FIN
[Unit]
Description=GitHub to Zulip Notification Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=${CURRENT_DIR}
Environment=PATH=${CURRENT_DIR}/venv/bin
ExecStart=${CURRENT_DIR}/venv/bin/python ${CURRENT_DIR}/main.py
Restart=always

[Install]
WantedBy=default.target
FIN

# Enable, Reload and Start the mercourier.service
systemctl --user enable "$SERVICE_FILE"
systemctl --user daemon-reload
systemctl --user start mercourier-${BRANCH_NAME}.service

systemctl --user status mercourier-${BRANCH_NAME}.service
