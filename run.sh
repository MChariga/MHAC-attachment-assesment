#!/usr/bin/env bash
# Pull the latest data from KoboToolbox, then serve the dashboard at http://localhost:8000
set -e
cd "$(dirname "$0")"
python3 pipeline/kobo_pipeline.py
echo "Dashboard: http://localhost:8000  (Ctrl+C to stop)"
python3 -m http.server 8000 --directory dashboard
