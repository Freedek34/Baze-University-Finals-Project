#!/bin/bash
# CryptoVault Backend Startup Script

cd /home/clinton/Desktop/Project/banking-system/backend

# Kill any existing Flask processes
pkill -f "python.*app.py" 2>/dev/null

# Start the server
echo "Starting CryptoVault Backend Server..."
PYTHONPATH=venv/lib/python3.12/site-packages venv/bin/python app.py
