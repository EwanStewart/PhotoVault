#!/bin/bash
# Brightness helper - applies brightness changes requested by the Flask app.
# The app writes the desired value to DESIRED_FILE; this daemon polls it
# and writes to sysfs. Runs as root via photovault-brightness.service.

BRIGHTNESS_PATH="${BRIGHTNESS_PATH:-/sys/class/backlight/10-0045/brightness}"
DESIRED_FILE="/tmp/photovault_brightness"
LOG_FILE="/tmp/photovault_brightness.log"
LAST_APPLIED=""

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Truncate log if too large
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null) -gt 1048576 ]; then
    tail -100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

log "Brightness helper started"

while true; do
    if [ -f "$DESIRED_FILE" ]; then
        DESIRED=$(cat "$DESIRED_FILE" 2>/dev/null)

        if [ -n "$DESIRED" ] && [ "$DESIRED" != "$LAST_APPLIED" ]; then
            # Validate it's a number between 0-255
            if [[ "$DESIRED" =~ ^[0-9]+$ ]] && [ "$DESIRED" -ge 0 ] && [ "$DESIRED" -le 255 ]; then
                if echo "$DESIRED" > "$BRIGHTNESS_PATH" 2>/dev/null; then
                    LAST_APPLIED="$DESIRED"
                    log "Brightness set to $DESIRED"
                else
                    log "ERROR: Failed to write brightness $DESIRED to $BRIGHTNESS_PATH"
                fi
            else
                log "WARNING: Invalid brightness value: $DESIRED"
            fi
        fi
    fi
    # Use longer sleep to reduce CPU usage
    sleep 0.5
done
