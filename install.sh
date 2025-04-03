#!/bin/bash
set -ex

BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)

# Create a virtual environment
python -m venv venv

# Install required packages
venv/bin/pip install -r requirements.txt

# Create systemd service file
CURRENT_DIR=$(pwd)
SERVICE_NAME="mercourier-${BRANCH_NAME}.service"
SERVICE_FILE="${CURRENT_DIR}/${SERVICE_NAME}"

cat > $SERVICE_FILE <<FIN
[Unit]
Description=GitHub to Zulip Notification Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=${CURRENT_DIR}
ExecStart=./venv/bin/python main.py
Restart=always

[Install]
WantedBy=default.target
FIN

# Enable and Start the service
systemctl --user enable ${SERVICE_FILE}
systemctl --user start ${SERVICE_NAME}
systemctl --user status ${SERVICE_NAME}
