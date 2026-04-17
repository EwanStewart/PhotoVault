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

## Install

```bash
./install_venv.sh
cp .env.example .env   # fill in Spotify credentials, paths
./run.sh               # starts Flask on :5000
```

Visit `http://<pi>:5000` and click "Connect Spotify" the first time to authorise.

## Configuration

Environment variables via `.env`:

| Variable | Purpose |
|---|---|
| `SPOTIFY_CLIENT_ID` | Spotify app Client ID |
| `SPOTIFY_CLIENT_SECRET` | Spotify app Client Secret |
| `SPOTIFY_REDIRECT_URI` | Defaults to `http://localhost:5000/callback` |
| `PHOTOS_DIR` | Photo directory (default `/home/ewastewa/photoframe/photos`) |
| `BRIGHTNESS_PATH` | sysfs brightness (default `/sys/class/backlight/10-0045/brightness`) |
| `DISPLAY_POWER_PATH` | sysfs backlight power (default `/sys/class/backlight/10-0045/bl_power`) |
| `MAX_BRIGHTNESS_PATH` | sysfs max brightness |
| `SPOTIFY_CACHE` | Token cache file (default `/home/ewastewa/photoframe/.cache/spotify_token`) |

Set a Spotify app Redirect URI that matches `SPOTIFY_REDIRECT_URI` exactly.

## Project Layout

```
app/
  main.py            Flask routes (photos, Spotify, hardware, bulbs, health)
  spotify_client.py  Spotipy wrapper with auth_manager-based token refresh
  tapo_client.py     Async TP-Link Tapo client with reconnection
  static/            JS + CSS for touch UI and glassmorphism styling
  templates/         index.html
brightness-helper.sh      sysfs brightness daemon
brightness-helper.service systemd unit for the daemon
display-schedule.sh       cron-driven display on/off at 07:00 / 19:00
start-kiosk.sh            launches Flask, waits for health, opens Chromium
sync-photos.sh            rclone sync from Google Drive
install_venv.sh           creates the venv and installs requirements
run.sh                    activates venv, loads .env, runs main.py
```

## Deployment

Two systemd services run on the Pi:

- `photoframe-kiosk.service` runs `start-kiosk.sh`, which starts Flask via `run.sh`, waits for `/api/health`, then launches Chromium against `http://localhost:5000`.
- `brightness-helper.service` runs the brightness daemon as root so it can write to sysfs.

`display-schedule.sh` runs every minute from cron and toggles the backlight.

## Google Drive sync

Configure rclone once with a remote named `gdrive` and a folder `PhotoFrame`:

```bash
rclone config          # create remote "gdrive", type Google Drive
./sync-photos.sh       # manual sync; also runs on a cron schedule
```

## HTTP API

| Route | Purpose |
|---|---|
| `GET /api/health` | Status and Spotify auth check |
| `GET /api/now-playing` | Current track, progress, saved flag |
| `POST /api/skip` / `pause` / `resume` / `like` | Playback controls |
| `GET /api/queue` | Next up to five tracks |
| `GET|POST /api/volume` | Playback volume |
| `GET|POST /api/brightness` | Screen brightness |
| `GET|POST /api/display` | Backlight power |
| `GET /api/sync-status` | Photo sync status |
| `GET|POST /api/theme` | UI theme |
| `GET /api/bulbs` | Tapo bulb list and state |
| `POST /api/bulbs/<id>/power|colour|brightness|reconnect` | Per-bulb control |
| `POST /api/bulbs/all/power|colour|brightness` | Bulk control |
| `GET /auth/spotify` | Start OAuth flow |
| `GET /callback` | OAuth redirect target |

## Troubleshooting

**Spotify overlay shows "Not Playing" while music is playing.** Check the Flask log for `401 The access token expired`. Spotipy's `auth_manager` refreshes tokens on each call, but if the Pi was briefly offline during refresh the cache file may still be stale. Visit `/auth/spotify` to re-authenticate.

**Photos not appearing.** Run `./sync-photos.sh` manually and check `/home/ewastewa/photoframe/photos`.

**Screen not dimming.** Confirm `brightness-helper.service` is active and `BRIGHTNESS_PATH` matches your panel's sysfs path.

**Kiosk not loading.** `systemctl status photoframe-kiosk.service` and tail `journalctl -u photoframe-kiosk -f`.
