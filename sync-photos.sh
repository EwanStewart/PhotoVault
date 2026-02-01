#!/bin/bash
# Sync photos from Google Drive
# Run manually or via cron

PHOTOS_DIR="${PHOTOS_DIR:-/home/pi/photoframe/photos}"
SYNC_STATUS_FILE="/tmp/photoframe_sync_status"
LOG_FILE="/tmp/photoframe_sync.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Truncate log if too large (>1MB)
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null) -gt 1048576 ]; then
    tail -100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

log "Starting photo sync..."

# Run rclone sync
if rclone sync gdrive:PhotoFrame "$PHOTOS_DIR" --exclude ".*" --exclude "*.tmp" 2>&1 | tee -a "$LOG_FILE"; then
    # Count photos
    PHOTO_COUNT=$(find "$PHOTOS_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.webp" -o -iname "*.bmp" \) | wc -l)

    # Write status file
    echo "$(date -Iseconds)|success|$PHOTO_COUNT" > "$SYNC_STATUS_FILE"

    log "Photo sync complete: $PHOTO_COUNT photos"
else
    # Write error status
    echo "$(date -Iseconds)|error|0" > "$SYNC_STATUS_FILE"

    log "ERROR: Photo sync failed"
    exit 1
fi
