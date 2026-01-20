#!/bin/bash

# Helferboard Start Script
# This script activates the virtual environment and starts the FastAPI application

cd /opt/helferboard

# Activate virtual environment
source venv/bin/activate

# Set environment variables (can be overridden by systemd service)
export ADMIN_USER=${ADMIN_USER:-admin}
export ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin}

# Start the application with uvicorn
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
