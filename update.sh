#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <branch-name>"
    exit 1
fi

BRANCH_NAME=$1

# Stop the service

systemctl --user stop mercourier-${BRANCH_NAME}.service

# Pull the latest changes from the repository

git pull origin ${BRANCH_NAME}

# Start the service

systemctl --user start mercourier-${BRANCH_NAME}.service
