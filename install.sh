#!/bin/bash

# Install necessary package
sudo pacman -S python python-pip python-virtualenv

# Create a virtual environment
python -m venv venv

# Install the required packages
venv/bin/pip install -r requirements.txt

# Create systemd service file

SERVICE_PATH="/etc/systemd/system/mercourier.service"
CURRENT_DIR=$(pwd)

SERVICE_CONTENT="[Unit]
Description=GitHub to Zulip Notification Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${CURRENT_DIR}
Environment=PATH=${CURRENT_DIR}/venv/bin
ExecStart=${CURRENT_DIR}/venv/bin/python ${CURRENT_DIR}/main.py
Restart=always

[Install]
WantedBy=multi-user.target"

echo "$SERVICE_CONTENT" | sudo tee "$SERVICE_PATH" > /dev/null

# Reload systemd
sudo systemctl daemon-reload

# Enable the service
sudo systemctl enable mercourier

# Start the service
sudo systemctl start mercourier

# Display the status of the service
sudo systemctl status mercourier