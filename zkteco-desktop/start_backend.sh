#!/bin/bash

# Activate virtual environment and start backend service
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run 'npm run install:backend' first."
    exit 1
fi

# Activate virtual environment and start service
source venv/bin/activate && python3 service_app.py