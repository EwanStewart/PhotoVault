#!/bin/bash

export DISPLAY=:0
export XAUTHORITY=/home/ewastewa/.Xauthority

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Start Flask app in background
echo "Starting Flask app"
"${SCRIPT_DIR}/run.sh" &
FLASK_PID=$!

# Wait for Flask to be ready
echo "Waiting for Flask to start"
for i in {1..30}; do
    if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
        echo "Flask is ready"
        break
    fi
    sleep 1
done

sleep 2

xrandr --output DSI-1 --mode 800x480 --rotate normal || true

xset s off
xset s noblank
xset -dpms

pkill chromium || true

rm -f ~/.config/chromium/SingletonLock \
      ~/.config/chromium/SingletonSocket \
      ~/.config/chromium/SingletonCookie

sleep 10

chromium \
  --kiosk \
  --start-fullscreen \
  --window-size=800,480 \
  --window-position=0,0 \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --disable-session-crashed-bubble \
  --password-store=basic \
  --disable-gpu \
  --disable-software-rasterizer \
  --disable-dev-shm-usage \
  --single-process \
  --process-per-site \
  --disable-extensions \
  --disable-background-networking \
  --disable-sync \
  --disable-translate \
  --disable-features=TranslateUI,VizDisplayCompositor \
  --memory-pressure-off \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --disable-renderer-backgrounding \
  --disable-component-update \
  --disable-domain-reliability \
  --disable-client-side-phishing-detection \
  http://localhost:5000
