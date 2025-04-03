#!/bin/bash

set -ex

BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
SERVICE_NAME="mercourier-${BRANCH_NAME}.service"

# Stop the service
systemctl --user stop ${SERVICE_NAME}

# Pull the latest changes from the repository
git pull origin ${BRANCH_NAME}

# Start the service
systemctl --user start ${SERVICE_NAME}
