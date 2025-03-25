#!/bin/bash

# Install necessary packages
sudo pacman -S python python-pip python-virtualenv

# Create a virtual environment
python -m venv venv

# Install required packages
venv/bin/pip install -r requirements.txt

# Create systemd service file
CURRENT_DIR=$(pwd)
SERVICE_FILE="$CURRENT_DIR/mercourier.service"

SERVICE_CONTENT="[Unit]
Description=GitHub to Zulip Notification Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=${CURRENT_DIR}
Environment=PATH=${CURRENT_DIR}/venv/bin
ExecStart=${CURRENT_DIR}/venv/bin/python ${CURRENT_DIR}/main.py
Restart=always

[Install]
WantedBy=default.target"

# Write the service file
echo "$SERVICE_CONTENT" > "$SERVICE_FILE"

# Enable, Reload and Start the mercourier.service
systemctl --user enable "$SERVICE_FILE"
systemctl --user daemon-reload
systemctl --user start mercourier

systemctl --user status mercourier
