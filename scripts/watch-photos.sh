#!/bin/bash
# Watch the Google Drive folder and sync when its contents change.
# Polls the remote listing (one cheap API call) and only runs a full
# sync when the listing differs. Runs as photovault-sync.service.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REMOTE="${SYNC_REMOTE:-gdrive:PhotoFrame}"
POLL_INTERVAL="${SYNC_POLL_INTERVAL:-60}"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Prints a hash of the remote listing, or an empty string when the listing fails.
remote_fingerprint() {
    local listing
    local result=""
    if listing=$(rclone lsf "$REMOTE" --recursive --files-only --fast-list \
        --format "pst" --exclude ".*" --exclude "*.tmp" 2>/dev/null); then
        result=$(printf '%s' "$listing" | sort | sha256sum | cut -d' ' -f1)
    fi
    echo "$result"
}

log "Watching $REMOTE every ${POLL_INTERVAL}s"

# Sync once at startup to pick up anything that changed while the watcher was down.
LAST=$(remote_fingerprint)
"$SCRIPT_DIR/sync-photos.sh"

while true; do
    sleep "$POLL_INTERVAL"
    CURRENT=$(remote_fingerprint)

    if [ -z "$CURRENT" ]; then
        log "Remote listing failed, will retry"
        continue
    fi

    if [ "$CURRENT" != "$LAST" ]; then
        log "Remote changed, syncing"
        if "$SCRIPT_DIR/sync-photos.sh"; then
            LAST="$CURRENT"
        fi
    fi
done
