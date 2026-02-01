# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Raspberry Pi photo frame with Spotify "Now Playing" overlay. Docker-based Flask application running on Pi 3B+ with 7" touchscreen.

## Development Commands

```bash
# Build and start
docker-compose build
docker-compose up -d

# View logs
docker-compose logs -f

# Sync photos from Google Drive
./sync-photos.sh

# Health check
curl http://localhost:5000/api/health
```

No test suite or linting is configured.

## Architecture

**Stack:** Flask backend, vanilla JavaScript frontend, Docker deployment

**Entry Point:** `app/main.py` - Flask server on port 5000

**Key Files:**
- `app/main.py` - Flask routes, hardware control APIs (brightness, volume, display power), theme/sync endpoints
- `app/spotify_client.py` - Spotipy wrapper for OAuth, playback control, queue, and library management
- `app/static/script.js` - Touch gesture handling, slideshow logic, API polling, state management
- `app/static/style.css` - CSS with theming variables, responsive overlay UI
- `app/templates/index.html` - Fullscreen photo frame UI with Spotify overlay, queue panel, playback controls

**Data Flow:**
- Photos served from `/app/photos` (mounted from host, synced via rclone from Google Drive)
- Spotify OAuth tokens stored in Docker volume
- Hardware control via sysfs at `/sys/class/backlight/` (configurable via env vars)
- Container-to-host communication via `/tmp/photoframe_*` temp files
- Sync status tracked in `/tmp/photoframe_sync_status`

**API Endpoints:**
- `GET /photos` - List photos with metadata, `GET /photos/<name>` - Serve photo
- `GET/POST /api/brightness` - Display brightness (0-255)
- `GET /api/brightness/auto` - Get recommended brightness for current hour
- `GET/POST /api/volume` - Spotify volume (0-100)
- `GET/POST /api/display` - Display power (on/off)
- `GET /api/now-playing` - Current track with progress, saved status
- `POST /api/skip`, `POST /api/pause`, `POST /api/resume` - Playback control
- `POST /api/like` - Save/unsave current track
- `GET /api/queue` - Upcoming tracks
- `GET /api/sync-status` - Photo sync status
- `GET/POST /api/theme` - Theme preferences
- `GET /api/health` - Health check

## Hardware Integration

Designed for Raspberry Pi with official 7" touchscreen. Hardware paths are configurable via environment variables:
- `BRIGHTNESS_PATH` - defaults to `/sys/class/backlight/10-0045/brightness`
- `DISPLAY_POWER_PATH` - defaults to `/sys/class/backlight/10-0045/bl_power`

Brightness control uses a host-side daemon (`brightness-helper.sh`) that reads from temp files and writes to sysfs.

## Configuration

Environment variables via `.env` file (not in repo):
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REDIRECT_URI` (default: http://localhost:5000/callback)

## Security Notes

- Filename validation prevents directory traversal in photo serving
- JSON request validation on all POST endpoints
- Spotify token refresh handled automatically with proper error handling
