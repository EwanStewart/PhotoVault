#!/bin/bash
# Display schedule for photoframe
# Turns display off at 7pm (19:00) and on at 7am (07:00)
# Add to crontab: * * * * * /home/ewastewa/photoframe/display-schedule.sh

BRIGHTNESS_PATH="/sys/class/backlight/10-0045/brightness"
DISPLAY_POWER_PATH="/sys/class/backlight/10-0045/bl_power"
STATE_FILE="/tmp/photoframe_display_state"
SAVED_BRIGHTNESS_FILE="/tmp/photoframe_saved_brightness"

HOUR=$(date +%H)

# Function to turn display off
display_off() {
    # Save current brightness before turning off
    if [ -f "$BRIGHTNESS_PATH" ]; then
        cat "$BRIGHTNESS_PATH" > "$SAVED_BRIGHTNESS_FILE"
    fi
    # Set bl_power to 1 (off)
    echo "1" > "$DISPLAY_POWER_PATH" 2>/dev/null
    echo "off" > "$STATE_FILE"
}

# Function to turn display on
display_on() {
    # Set bl_power to 0 (on)
    echo "0" > "$DISPLAY_POWER_PATH" 2>/dev/null
    # Restore brightness if saved
    if [ -f "$SAVED_BRIGHTNESS_FILE" ]; then
        cat "$SAVED_BRIGHTNESS_FILE" > "$BRIGHTNESS_PATH" 2>/dev/null
    fi
    echo "on" > "$STATE_FILE"
}

# Get current state
CURRENT_STATE="on"
if [ -f "$STATE_FILE" ]; then
    CURRENT_STATE=$(cat "$STATE_FILE")
fi

# Check time and set display state
# Off during 19:00-06:59, On during 07:00-18:59
if [ "$HOUR" -ge 19 ] || [ "$HOUR" -lt 7 ]; then
    # Should be off
    if [ "$CURRENT_STATE" != "off" ]; then
        display_off
    fi
else
    # Should be on
    if [ "$CURRENT_STATE" != "on" ]; then
        display_on
    fi
fi
