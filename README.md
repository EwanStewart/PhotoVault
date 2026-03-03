# Raspberry Pi Photo Frame + Spotify Display

A Docker-based photo frame for Raspberry Pi 3B+ with 7" touchscreen featuring:
- Fullscreen photo slideshow from Google Drive
- "Now Playing" Spotify overlay with skip button

## Quick Start

1. Copy all files to your Raspberry Pi
2. Run the setup scripts in order:

```bash
chmod +x *.sh
./01-install-dependencies.sh
# Log out and back in
./02-configure-rclone.sh
./03-setup-project.sh
# Edit .env with Spotify credentials
./04-configure-autostart.sh
./05-start.sh
```

3. Open browser, go to `http://localhost:5000`, click "Connect Spotify"
4. Reboot - everything starts automatically

## Setup Scripts

| Script | Purpose |
|--------|---------|
| `01-install-dependencies.sh` | Install Docker & rclone |
| `02-configure-rclone.sh` | Interactive Google Drive setup |
| `03-setup-project.sh` | Create all project files |
| `04-configure-autostart.sh` | Set up kiosk mode |
| `05-start.sh` | Start the container |
| `sync-photos.sh` | Manual photo sync |

## Spotify Setup

1. Go to https://developer.spotify.com/dashboard
2. Create a new app
3. Add `http://localhost:5000/callback` as a Redirect URI
4. Copy Client ID and Client Secret to `.env`

## Google Drive Setup

During `02-configure-rclone.sh`:
1. Name your remote: `gdrive`
2. Choose storage type: Google Drive
3. Follow OAuth prompts
4. Create a folder called `PhotoFrame` in Google Drive
5. Add photos to that folder

## Usage

- **Tap screen**: Show/hide Spotify overlay
- **Skip button**: Skip to next track
- Photos sync from Google Drive every 30 minutes
- Manual sync: `./sync-photos.sh`

## Troubleshooting

**Container not starting:**
```bash
cd /home/ewastewa/photoframe
docker-compose logs
```

**Photos not appearing:**
```bash
./sync-photos.sh
ls /home/ewastewa/photoframe/photos
```

**Spotify not connecting:**
- Verify credentials in `.env`
- Check redirect URI matches exactly
- Visit `http://localhost:5000/auth/spotify` to re-authenticate
