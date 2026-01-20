#!/bin/bash

# Helferboard Deployment Script for Raspberry Pi
# This script assumes the ZIP file is extracted to /opt/helferboard

set -e

echo "Starting Helferboard deployment..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo ./deploy.sh)"
  exit 1
fi

# Install system dependencies
echo "Installing system dependencies..."
apt update
apt install -y python3 python3-venv python3-pip

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv /opt/helferboard/venv

# Activate venv and install Python dependencies
echo "Installing Python dependencies..."
/opt/helferboard/venv/bin/pip install --upgrade pip
/opt/helferboard/venv/bin/pip install -r /opt/helferboard/requirements.txt

# Copy service file
echo "Installing systemd service..."
cp /opt/helferboard/scripts/helferboard.service /etc/systemd/system/

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable helferboard.service

# Start the service
echo "Starting Helferboard service..."
systemctl start helferboard.service

# Check status
systemctl status helferboard.service --no-pager

echo "Deployment completed successfully!"
echo "Helferboard should be accessible at http://localhost:8000"
echo "Admin interface at http://localhost:8000/admin"
