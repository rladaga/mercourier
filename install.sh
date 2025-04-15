#!/bin/bash
set -ex

BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
CURRENT_USER=$(whoami)

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
ExecStart=/usr/bin/uv run main.py
Restart=always

[Install]
WantedBy=default.target
FIN

# Enable and Start the service
systemctl --user enable ${SERVICE_FILE}
systemctl --user start ${SERVICE_NAME}
systemctl --user status ${SERVICE_NAME}

# This service is being set to be a user service,
# which means that when the user logs out the systemd instance will shutdown as well as the service,
# to keep your systemd instance and the service running after logout you need to enable lingering for your user,
# that´s why we run the command line below.
sudo loginctl enable-linger ${CURRENT_USER}
