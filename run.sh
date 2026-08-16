#!/bin/bash
# One-command launcher for the Catalogue Importer app.
echo "Installing dependencies (first run only)..."
pip install -r requirements.txt --break-system-packages -q
echo ""
echo "Starting Catalogue Importer..."
echo "Open this link in your browser: http://localhost:5000"
echo ""
python3 app.py
