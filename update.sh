#!/bin/bash

# Stop the service

sudo systemctl stop mercourier

# Pull the latest changes from the repository

git pull origin main

# Start the service

sudo systemctl start mercourier