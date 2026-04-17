# PhotoVault

A Raspberry Pi photo frame with Spotify "Now Playing" overlay and Tapo smart bulb control. Runs as a Flask app on a Pi 3B+ with a 7" DSI touchscreen in Chromium kiosk mode.

## Features

- Fullscreen slideshow of photos synced from Google Drive via rclone
- HEIC support with on-the-fly JPEG conversion and cache
- EXIF-based photo metadata with GPS reverse geocoding (Nominatim)
- Spotify overlay: track, artist, album art, progress bar, queue view
- Spotify controls: skip, pause, resume, like, volume
- Tapo smart bulb panel: power, colour swatches, brightness, bulk operations
- Touch gestures:
  - Left edge swipe: brightness
  - Right edge swipe: volume
  - Double tap: display on/off
  - Single tap: overlay toggle (or queue toggle while playing)
- Scheduled display off between 19:00 and 07:00

## Requirements

- Raspberry Pi 3B+ (or similar) running Debian-based Linux
- 7" DSI touchscreen (tested against `/sys/class/backlight/10-0045`)
- Python 3, `libheif-dev`, `rclone`, `chromium`
- Spotify developer app (Client ID + Secret)
- TP-Link Tapo bulbs on the same network (optional)

## Project Layout

```
src/photovault/           Python package
  main.py                 Flask routes (photos, Spotify, hardware, bulbs, health)
  spotify_client.py       Spotipy wrapper with auth_manager token refresh
  tapo_client.py          Async TP-Link Tapo client with reconnection
  static/                 JS + CSS for touch UI
  templates/              index.html
scripts/                  Shell entry points
  start-kiosk.sh          Launches Flask, waits for health, opens Chromium
  brightness-helper.sh    sysfs brightness daemon
  display-schedule.sh     Cron-driven display on/off at 07:00 / 19:00
  sync-photos.sh          rclone sync from Google Drive
systemd/                  systemd unit files
  photovault-kiosk.service
  photovault-brightness.service
run.sh                    Activates venv, loads .env, runs the Flask app
install_venv.sh           Creates the venv and installs requirements
requirements.txt
.env.example
```

All paths default to paths derived from the repo root, so the install location is not hardcoded.

## Install (Raspberry Pi)

Clone to `/home/<user>/photovault` and run:

```bash
./install_venv.sh
cp .env.example .env       # fill in Spotify credentials

# Install systemd units
sudo cp systemd/photovault-kiosk.service /etc/systemd/system/
sudo cp systemd/photovault-brightness.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now photovault-kiosk.service photovault-brightness.service

# Install cron entries
( crontab -l 2>/dev/null; \
  echo "*/30 * * * * $(pwd)/scripts/sync-photos.sh"; \
  echo "* * * * * $(pwd)/scripts/display-schedule.sh" \
) | crontab -
```

Visit `http://<pi>:5000` and click "Connect Spotify" once to authorise.

## Running Locally

```bash
./install_venv.sh
cp .env.example .env       # fill in Spotify credentials
./run.sh                   # Flask on :5000
```

## Configuration

Environment variables via `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `SPOTIFY_CLIENT_ID` | | Spotify app Client ID |
| `SPOTIFY_CLIENT_SECRET` | | Spotify app Client Secret |
| `SPOTIFY_REDIRECT_URI` | `http://localhost:5000/callback` | Must match the Spotify app redirect URI |
| `PHOTOS_DIR` | `<repo>/photos` | Photo directory |
| `SPOTIFY_CACHE` | `<repo>/.cache/spotify_token` | Token cache file |
| `BRIGHTNESS_PATH` | `/sys/class/backlight/10-0045/brightness` | sysfs brightness |
| `DISPLAY_POWER_PATH` | `/sys/class/backlight/10-0045/bl_power` | sysfs backlight power |
| `MAX_BRIGHTNESS_PATH` | `/sys/class/backlight/10-0045/max_brightness` | sysfs max brightness |

## Google Drive sync

Configure rclone once with a remote named `gdrive` and a folder `PhotoFrame`:

```bash
rclone config              # create remote "gdrive", type Google Drive
./scripts/sync-photos.sh   # manual sync; cron handles the rest
```

## HTTP API

| Route | Purpose |
|---|---|
| `GET /api/health` | Status and Spotify auth check |
| `GET /api/now-playing` | Current track, progress, saved flag |
| `POST /api/skip` / `pause` / `resume` / `like` | Playback controls |
| `GET /api/queue` | Next up to five tracks |
| `GET\|POST /api/volume` | Playback volume |
| `GET\|POST /api/brightness` | Screen brightness |
| `GET\|POST /api/display` | Backlight power |
| `GET /api/sync-status` | Photo sync status |
| `GET\|POST /api/theme` | UI theme |
| `GET /api/bulbs` | Tapo bulb list and state |
| `POST /api/bulbs/<id>/power\|colour\|brightness\|reconnect` | Per-bulb control |
| `POST /api/bulbs/all/power\|colour\|brightness` | Bulk control |
| `GET /auth/spotify` | Start OAuth flow |
| `GET /callback` | OAuth redirect target |

## Troubleshooting

**Spotify overlay shows "Not Playing" while music is playing.** Check `journalctl -u photovault-kiosk -f` for `401 The access token expired`. Visit `/auth/spotify` to re-authenticate.

**Photos not appearing.** Run `./scripts/sync-photos.sh` manually and check the `photos/` directory.

**Screen not dimming.** Confirm `photovault-brightness.service` is active and `BRIGHTNESS_PATH` matches your panel's sysfs path.

**Kiosk not loading.** `systemctl status photovault-kiosk.service` and `journalctl -u photovault-kiosk -f`.

## Runtime State

The app reads and writes the following runtime state:

| Path | Purpose |
|---|---|
| `<repo>/photos/` | Photo library (synced from Google Drive) |
| `<repo>/.cache/spotify_token` | Spotify OAuth token cache |
| `<repo>/geocode_cache.json` | Reverse-geocoding cache |
| `/tmp/photovault_heic_cache/` | HEIC → JPEG conversion cache |
| `/tmp/photovault_flag_cache/` | Country flag SVG cache |
| `/tmp/photovault_brightness` | Requested brightness (read by the helper daemon) |
| `/tmp/photovault_display_state` | Current backlight state |
| `/tmp/photovault_sync_status` | Last sync result |
