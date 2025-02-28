#!/bin/bash

# Change into the directory where the script is located
cd mercourier

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
if [[ "$OSTYPE" == "darwin"* ]]; then
    source venv/bin/activate
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    source venv/bin/activate
elif [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]]; then
    source venv/Scripts/activate
else
    echo "Unsupported OS"
    exit 1
fi

# Install the required packages
pip install -r requirements.txt

# Create systemd service file
cp mercourier.service /etc/systemd/system/mercourier.service

# Reload systemd
sudo systemctl daemon-reload

# Enable the service
sudo systemctl enable mercourier

# Start the service
sudo systemctl start mercourier

# Display the status of the service
sudo systemctl status mercourier