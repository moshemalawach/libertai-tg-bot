#!/bin/bash

source venv/bin/activate

export DEBUG=true
python3 src/app.py

# Deactivate the virtual environment
deactivate

# Exit the script
exit 0
