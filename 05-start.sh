#!/bin/bash
set -e

cd /home/ewastewa/photoframe

echo "=== Starting Photo Frame ==="
docker compose up -d

echo ""
echo "=== Container started! ==="
echo "Visit http://localhost:5000 to view the photo frame"
echo "Complete Spotify OAuth if this is the first run"
