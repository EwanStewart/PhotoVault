#!/bin/bash
set -e

PROJECT_DIR="/home/ewastewa/photoframe"

echo "=== Creating Project Structure ==="

mkdir -p "$PROJECT_DIR/app/static"
mkdir -p "$PROJECT_DIR/app/templates"
mkdir -p "$PROJECT_DIR/photos"

# --- docker-compose.yml ---
cat > "$PROJECT_DIR/docker-compose.yml" << 'EOF'
version: '3.8'

services:
  photoframe:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./photos:/app/photos:ro
      - spotify_cache:/app/.cache
    env_file:
      - .env
    restart: unless-stopped

volumes:
  spotify_cache:
EOF

# --- Dockerfile ---
cat > "$PROJECT_DIR/Dockerfile" << 'EOF'
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask spotipy

COPY app/ /app/

EXPOSE 5000

CMD ["python", "main.py"]
EOF

# --- app/main.py ---
cat > "$PROJECT_DIR/app/main.py" << 'EOF'
import os
from flask import Flask, render_template, jsonify, send_from_directory, redirect, request, session
from spotify_client import SpotifyClient

app = Flask(__name__)
app.secret_key = os.urandom(24)

PHOTOS_DIR = '/app/photos'
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

spotify = SpotifyClient()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/photos')
def list_photos():
    """Return list of photo filenames."""
    photos = []
    if os.path.exists(PHOTOS_DIR):
        for f in os.listdir(PHOTOS_DIR):
            ext = os.path.splitext(f)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                photos.append(f)
    photos.sort()
    return jsonify(photos)


@app.route('/photos/<path:filename>')
def serve_photo(filename):
    """Serve a photo file."""
    return send_from_directory(PHOTOS_DIR, filename)


@app.route('/api/now-playing')
def now_playing():
    """Get currently playing track from Spotify."""
    if not spotify.is_authenticated():
        return jsonify({'error': 'not_authenticated', 'auth_url': '/auth/spotify'})

    track = spotify.get_now_playing()
    return jsonify(track)


@app.route('/api/skip', methods=['POST'])
def skip_track():
    """Skip to next track."""
    if not spotify.is_authenticated():
        return jsonify({'error': 'not_authenticated'}), 401

    success = spotify.skip_track()
    return jsonify({'success': success})


@app.route('/auth/spotify')
def spotify_auth():
    """Redirect to Spotify authorization."""
    auth_url = spotify.get_auth_url()
    return redirect(auth_url)


@app.route('/callback')
def spotify_callback():
    """Handle Spotify OAuth callback."""
    code = request.args.get('code')
    if code:
        spotify.handle_callback(code)
    return redirect('/')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
EOF

# --- app/spotify_client.py ---
cat > "$PROJECT_DIR/app/spotify_client.py" << 'EOF'
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPE = 'user-read-playback-state user-modify-playback-state user-read-currently-playing'
CACHE_PATH = '/app/.cache/spotify_token'


class SpotifyClient:
    def __init__(self):
        self.client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        self.client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        self.redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://localhost:5000/callback')

        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

        self.sp_oauth = None
        self.sp = None

        if self.client_id and self.client_secret:
            self.sp_oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=SCOPE,
                cache_path=CACHE_PATH,
                open_browser=False
            )
            self._try_load_cached_token()

    def _try_load_cached_token(self):
        """Try to load and use cached token."""
        if self.sp_oauth:
            token_info = self.sp_oauth.get_cached_token()
            if token_info:
                self.sp = spotipy.Spotify(auth=token_info['access_token'])

    def is_authenticated(self):
        """Check if we have a valid Spotify connection."""
        if not self.sp_oauth:
            return False

        token_info = self.sp_oauth.get_cached_token()
        if not token_info:
            return False

        # Refresh token if needed
        if self.sp_oauth.is_token_expired(token_info):
            token_info = self.sp_oauth.refresh_access_token(token_info['refresh_token'])
            self.sp = spotipy.Spotify(auth=token_info['access_token'])

        return True

    def get_auth_url(self):
        """Get Spotify authorization URL."""
        if self.sp_oauth:
            return self.sp_oauth.get_authorize_url()
        return None

    def handle_callback(self, code):
        """Handle OAuth callback and get token."""
        if self.sp_oauth:
            token_info = self.sp_oauth.get_access_token(code)
            self.sp = spotipy.Spotify(auth=token_info['access_token'])

    def get_now_playing(self):
        """Get currently playing track."""
        if not self.sp:
            return {'playing': False}

        try:
            current = self.sp.current_playback()

            if not current or not current.get('is_playing'):
                return {'playing': False}

            item = current.get('item')
            if not item:
                return {'playing': False}

            artists = ', '.join([a['name'] for a in item.get('artists', [])])
            album_art = None
            images = item.get('album', {}).get('images', [])
            if images:
                album_art = images[0]['url']

            return {
                'playing': True,
                'name': item.get('name', 'Unknown'),
                'artist': artists or 'Unknown Artist',
                'album': item.get('album', {}).get('name', ''),
                'album_art': album_art,
                'progress_ms': current.get('progress_ms', 0),
                'duration_ms': item.get('duration_ms', 0)
            }
        except Exception as e:
            print(f"Spotify error: {e}")
            return {'playing': False, 'error': str(e)}

    def skip_track(self):
        """Skip to next track."""
        if not self.sp:
            return False

        try:
            self.sp.next_track()
            return True
        except Exception as e:
            print(f"Skip error: {e}")
            return False
EOF

# --- app/templates/index.html ---
cat > "$PROJECT_DIR/app/templates/index.html" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Frame</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div id="slideshow">
        <img id="photo-current" class="photo active" src="" alt="">
        <img id="photo-next" class="photo" src="" alt="">
    </div>

    <div id="overlay" class="hidden">
        <div id="now-playing">
            <img id="album-art" src="" alt="">
            <div id="track-info">
                <div id="track-name">Not Playing</div>
                <div id="track-artist"></div>
            </div>
            <button id="skip-btn" title="Skip">⏭</button>
        </div>
    </div>

    <div id="auth-prompt" class="hidden">
        <a href="/auth/spotify">Connect Spotify</a>
    </div>

    <script src="/static/script.js"></script>
</body>
</html>
EOF

# --- app/static/style.css ---
cat > "$PROJECT_DIR/app/static/style.css" << 'EOF'
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html, body {
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #000;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

#slideshow {
    width: 100%;
    height: 100%;
    position: relative;
}

.photo {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
    opacity: 0;
    transition: opacity 1s ease-in-out;
}

.photo.active {
    opacity: 1;
}

#overlay {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 100;
    transition: opacity 0.3s ease;
}

#overlay.hidden {
    opacity: 0;
    pointer-events: none;
}

#now-playing {
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(10px);
    padding: 10px 15px;
    border-radius: 12px;
    color: white;
    min-width: 280px;
    max-width: 90vw;
}

#album-art {
    width: 50px;
    height: 50px;
    border-radius: 6px;
    object-fit: cover;
    flex-shrink: 0;
}

#track-info {
    flex: 1;
    min-width: 0;
    overflow: hidden;
}

#track-name {
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

#track-artist {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.7);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

#skip-btn {
    background: rgba(255, 255, 255, 0.2);
    border: none;
    color: white;
    font-size: 20px;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    cursor: pointer;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s;
}

#skip-btn:hover {
    background: rgba(255, 255, 255, 0.3);
}

#skip-btn:active {
    background: rgba(255, 255, 255, 0.4);
}

#auth-prompt {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 200;
}

#auth-prompt.hidden {
    display: none;
}

#auth-prompt a {
    display: block;
    padding: 20px 40px;
    background: #1DB954;
    color: white;
    text-decoration: none;
    border-radius: 30px;
    font-size: 18px;
    font-weight: 600;
}

/* No photos message */
#slideshow:empty::after {
    content: 'No photos found. Add photos to Google Drive.';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: rgba(255, 255, 255, 0.5);
    font-size: 18px;
}
EOF

# --- app/static/script.js ---
cat > "$PROJECT_DIR/app/static/script.js" << 'EOF'
const SLIDE_INTERVAL = 30000; // 30 seconds per photo
const POLL_INTERVAL = 5000;   // Poll Spotify every 5 seconds
const OVERLAY_TIMEOUT = 10000; // Hide overlay after 10 seconds

let photos = [];
let currentIndex = 0;
let overlayVisible = false;
let overlayTimer = null;
let isPlaying = false;

const photoCurrent = document.getElementById('photo-current');
const photoNext = document.getElementById('photo-next');
const overlay = document.getElementById('overlay');
const albumArt = document.getElementById('album-art');
const trackName = document.getElementById('track-name');
const trackArtist = document.getElementById('track-artist');
const skipBtn = document.getElementById('skip-btn');
const authPrompt = document.getElementById('auth-prompt');

// Load photos list
async function loadPhotos() {
    try {
        const response = await fetch('/photos');
        photos = await response.json();
        if (photos.length > 0) {
            showPhoto(0);
            startSlideshow();
        }
    } catch (error) {
        console.error('Failed to load photos:', error);
    }
}

// Show a specific photo
function showPhoto(index) {
    if (photos.length === 0) return;

    const nextImg = photoCurrent.classList.contains('active') ? photoNext : photoCurrent;
    const currentImg = photoCurrent.classList.contains('active') ? photoCurrent : photoNext;

    nextImg.src = `/photos/${photos[index]}`;
    nextImg.onload = () => {
        nextImg.classList.add('active');
        currentImg.classList.remove('active');
    };
}

// Start slideshow
function startSlideshow() {
    setInterval(() => {
        currentIndex = (currentIndex + 1) % photos.length;
        showPhoto(currentIndex);
    }, SLIDE_INTERVAL);
}

// Poll Spotify for now playing
async function pollNowPlaying() {
    try {
        const response = await fetch('/api/now-playing');
        const data = await response.json();

        if (data.error === 'not_authenticated') {
            authPrompt.classList.remove('hidden');
            return;
        }

        authPrompt.classList.add('hidden');

        if (data.playing) {
            isPlaying = true;
            trackName.textContent = data.name;
            trackArtist.textContent = data.artist;
            if (data.album_art) {
                albumArt.src = data.album_art;
                albumArt.style.display = 'block';
            } else {
                albumArt.style.display = 'none';
            }
        } else {
            isPlaying = false;
            trackName.textContent = 'Not Playing';
            trackArtist.textContent = '';
            albumArt.style.display = 'none';
        }
    } catch (error) {
        console.error('Failed to poll now playing:', error);
    }
}

// Toggle overlay visibility
function toggleOverlay() {
    overlayVisible = !overlayVisible;

    if (overlayVisible) {
        overlay.classList.remove('hidden');
        resetOverlayTimer();
    } else {
        overlay.classList.add('hidden');
        clearOverlayTimer();
    }
}

// Show overlay temporarily
function showOverlayTemporarily() {
    overlay.classList.remove('hidden');
    overlayVisible = true;
    resetOverlayTimer();
}

// Reset overlay auto-hide timer
function resetOverlayTimer() {
    clearOverlayTimer();
    overlayTimer = setTimeout(() => {
        overlay.classList.add('hidden');
        overlayVisible = false;
    }, OVERLAY_TIMEOUT);
}

// Clear overlay timer
function clearOverlayTimer() {
    if (overlayTimer) {
        clearTimeout(overlayTimer);
        overlayTimer = null;
    }
}

// Skip track
async function skipTrack(e) {
    e.stopPropagation();
    resetOverlayTimer();

    try {
        await fetch('/api/skip', { method: 'POST' });
        // Poll immediately to update display
        setTimeout(pollNowPlaying, 500);
    } catch (error) {
        console.error('Failed to skip:', error);
    }
}

// Event listeners
document.body.addEventListener('click', toggleOverlay);
skipBtn.addEventListener('click', skipTrack);

// Prevent overlay clicks from toggling
overlay.addEventListener('click', (e) => {
    e.stopPropagation();
    resetOverlayTimer();
});

// Initialize
loadPhotos();
pollNowPlaying();
setInterval(pollNowPlaying, POLL_INTERVAL);

// Refresh photos list periodically (every 5 minutes)
setInterval(loadPhotos, 300000);
EOF

# --- .env.example ---
cat > "$PROJECT_DIR/.env.example" << 'EOF'
# Spotify API Credentials
# Get these from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:5000/callback
EOF

# Copy .env.example to .env if it doesn't exist
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
fi

# --- Setup cron job for photo sync ---
echo "Setting up cron job for photo sync..."
CRON_CMD="*/30 * * * * /home/ewastewa/photoframe/sync-photos.sh >> /home/ewastewa/photoframe/sync.log 2>&1"
(crontab -l 2>/dev/null | grep -v "sync-photos.sh"; echo "$CRON_CMD") | crontab -

# Copy scripts to project directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$SCRIPT_DIR" != "$PROJECT_DIR" ]; then
    cp "$SCRIPT_DIR/05-start.sh" "$PROJECT_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/sync-photos.sh" "$PROJECT_DIR/" 2>/dev/null || true
fi

# Make scripts executable
chmod +x "$PROJECT_DIR"/*.sh 2>/dev/null || true

echo ""
echo "=== Project Created! ==="
echo ""
echo "Next steps:"
echo "1. Edit $PROJECT_DIR/.env with your Spotify credentials"
echo "   - Go to https://developer.spotify.com/dashboard"
echo "   - Create an app and get Client ID & Secret"
echo "   - Add http://localhost:5000/callback as Redirect URI"
echo ""
echo "2. Run 04-configure-autostart.sh to set up kiosk mode"
echo "3. Run 05-start.sh to start the container"
echo "4. Visit http://localhost:5000 and click 'Connect Spotify'"
echo "5. Reboot - everything will start automatically"
