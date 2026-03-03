#!/bin/bash
set -e

echo "=== Configuring Autostart ==="

AUTOSTART_DIR="$HOME/.config/lxsession/LXDE-pi"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/autostart" << 'EOF'
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@xset s off
@xset -dpms
@xset s noblank
@unclutter -idle 0.5 -root &
@chromium-browser --kiosk --noerrdialogs --disable-infobars --incognito http://localhost:5000
EOF

echo "Autostart file created at $AUTOSTART_DIR/autostart"

# Disable screen blanking via raspi-config
echo "Disabling screen blanking..."
sudo raspi-config nonint do_blanking 1 2>/dev/null || echo "Note: Could not disable blanking via raspi-config (may not be available)"

# Install unclutter to hide cursor
echo "Installing unclutter (hides mouse cursor)..."
sudo apt install -y unclutter

echo ""
echo "=== Done! ==="
echo "Chromium will launch in kiosk mode on next boot."
echo "Now run 05-start.sh to start the container, then reboot."
