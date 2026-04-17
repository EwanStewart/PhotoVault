# PhotoVault

A Raspberry Pi photo frame with Spotify "Now Playing" overlay and Tapo smart bulb control. Runs as a Flask app on a Pi 3B+ with a 7" DSI touchscreen in Chromium kiosk mode.

![PhotoVault kiosk showing an Angus hillside with the Spotify overlay](docs/screenshot.png)

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


## Google Drive sync

Configure rclone once with a remote named `gdrive` and a folder `PhotoFrame`:

```bash
rclone config              # create remote "gdrive", type Google Drive
./scripts/sync-photos.sh   # manual sync; cron handles the rest
```

