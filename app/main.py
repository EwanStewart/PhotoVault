import os
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, send_from_directory, redirect, request, session
from spotify_client import SpotifyClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

PHOTOS_DIR = '/app/photos'
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

# Hardware paths - configurable via environment variables
BRIGHTNESS_PATH = os.environ.get('BRIGHTNESS_PATH', '/sys/class/backlight/10-0045/brightness')
DISPLAY_POWER_PATH = os.environ.get('DISPLAY_POWER_PATH', '/sys/class/backlight/10-0045/bl_power')
MAX_BRIGHTNESS_PATH = os.environ.get('MAX_BRIGHTNESS_PATH', '/sys/class/backlight/10-0045/max_brightness')
BRIGHTNESS_DESIRED = '/tmp/photoframe_brightness'

# Sync status file
SYNC_STATUS_FILE = '/tmp/photoframe_sync_status'

# Adaptive brightness schedule (hour: brightness level 0-255)
BRIGHTNESS_SCHEDULE = {
    0: 30, 1: 30, 2: 30, 3: 30, 4: 30, 5: 30,
    6: 60, 7: 100, 8: 150, 9: 180, 10: 200, 11: 220,
    12: 255, 13: 255, 14: 255, 15: 255, 16: 220, 17: 200,
    18: 180, 19: 150, 20: 120, 21: 80, 22: 50, 23: 40
}

spotify = SpotifyClient()


def validate_filename(filename):
    """Validate filename to prevent directory traversal attacks."""
    if not filename:
        return False
    # Reject any path separators or parent directory references
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    # Only allow files in the photos directory
    return os.path.basename(filename) == filename


def get_json_or_error():
    """Safely get JSON from request, returning None if invalid."""
    if not request.is_json:
        return None
    try:
        return request.get_json()
    except Exception:
        return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/photos')
def list_photos():
    """Return list of photo filenames with metadata."""
    photos = []
    if os.path.exists(PHOTOS_DIR):
        for f in os.listdir(PHOTOS_DIR):
            ext = os.path.splitext(f)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filepath = os.path.join(PHOTOS_DIR, f)
                try:
                    stat = os.stat(filepath)
                    photos.append({
                        'filename': f,
                        'modified': stat.st_mtime,
                        'size': stat.st_size
                    })
                except OSError:
                    photos.append({'filename': f, 'modified': 0, 'size': 0})
    # Sort by modification time (newest first)
    photos.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify(photos)


@app.route('/photos/<path:filename>')
def serve_photo(filename):
    """Serve a photo file."""
    if not validate_filename(filename):
        logger.warning(f"Invalid filename requested: {filename}")
        return jsonify({'error': 'Invalid filename'}), 400
    return send_from_directory(PHOTOS_DIR, filename)


@app.route('/api/now-playing')
def now_playing():
    """Get currently playing track from Spotify."""
    if not spotify.is_authenticated():
        return jsonify({'error': 'not_authenticated', 'error_type': 'auth', 'auth_url': '/auth/spotify'})

    try:
        track = spotify.get_now_playing()
        return jsonify(track)
    except Exception as e:
        logger.error(f"Now playing error: {e}")
        return jsonify({'error': str(e), 'error_type': 'api', 'playing': False})


@app.route('/api/skip', methods=['POST'])
def skip_track():
    """Skip to next track."""
    if not spotify.is_authenticated():
        return jsonify({'error': 'not_authenticated', 'error_type': 'auth'}), 401

    try:
        success = spotify.skip_track()
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Skip error: {e}")
        return jsonify({'error': str(e), 'error_type': 'api'}), 500


@app.route('/api/pause', methods=['POST'])
def pause_track():
    """Pause playback."""
    if not spotify.is_authenticated():
        return jsonify({'error': 'not_authenticated', 'error_type': 'auth'}), 401

    try:
        success = spotify.pause_playback()
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Pause error: {e}")
        return jsonify({'error': str(e), 'error_type': 'api'}), 500


@app.route('/api/resume', methods=['POST'])
def resume_track():
    """Resume playback."""
    if not spotify.is_authenticated():
        return jsonify({'error': 'not_authenticated', 'error_type': 'auth'}), 401

    try:
        success = spotify.resume_playback()
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Resume error: {e}")
        return jsonify({'error': str(e), 'error_type': 'api'}), 500


@app.route('/api/like', methods=['POST'])
def like_track():
    """Save current track to user's library."""
    if not spotify.is_authenticated():
        return jsonify({'error': 'not_authenticated', 'error_type': 'auth'}), 401

    try:
        success = spotify.save_current_track()
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Like error: {e}")
        return jsonify({'error': str(e), 'error_type': 'api'}), 500


@app.route('/api/queue')
def get_queue():
    """Get upcoming tracks in queue."""
    if not spotify.is_authenticated():
        return jsonify({'error': 'not_authenticated', 'error_type': 'auth'}), 401

    try:
        queue = spotify.get_queue()
        return jsonify(queue)
    except Exception as e:
        logger.error(f"Queue error: {e}")
        return jsonify({'error': str(e), 'error_type': 'api', 'tracks': []})


@app.route('/api/brightness', methods=['GET', 'POST'])
def brightness():
    """Get or set display brightness (0-255)."""
    if request.method == 'GET':
        try:
            # Try to read actual brightness first
            with open(BRIGHTNESS_PATH, 'r') as f:
                level = int(f.read().strip())
            return jsonify({'level': level})
        except (IOError, ValueError) as e:
            # Fall back to desired file
            try:
                with open(BRIGHTNESS_DESIRED, 'r') as f:
                    level = int(f.read().strip())
                return jsonify({'level': level})
            except (IOError, ValueError):
                logger.warning(f"Could not read brightness: {e}")
                return jsonify({'level': 128})  # Default fallback

    # POST - set brightness via helper file
    data = get_json_or_error()
    if data is None:
        return jsonify({'error': 'Invalid JSON', 'error_type': 'request'}), 400

    try:
        level = data.get('level', 128)
        level = max(0, min(255, int(level)))
        with open(BRIGHTNESS_DESIRED, 'w') as f:
            f.write(str(level))
        logger.info(f"Brightness set to {level}")
        return jsonify({'success': True, 'level': level})
    except (ValueError, TypeError) as e:
        return jsonify({'error': f'Invalid brightness value: {e}', 'error_type': 'request'}), 400
    except IOError as e:
        logger.error(f"Brightness write error: {e}")
        return jsonify({'error': str(e), 'error_type': 'hardware'}), 500


@app.route('/api/brightness/auto', methods=['GET'])
def auto_brightness():
    """Get recommended brightness based on time of day."""
    hour = datetime.now().hour
    recommended = BRIGHTNESS_SCHEDULE.get(hour, 128)
    return jsonify({'recommended': recommended, 'hour': hour})


@app.route('/api/volume', methods=['GET', 'POST'])
def volume():
    """Get or set Spotify playback volume (0-100%)."""
    if not spotify.is_authenticated():
        return jsonify({'error': 'not_authenticated', 'error_type': 'auth'}), 401

    if request.method == 'GET':
        try:
            level = spotify.get_volume()
            if level is not None:
                return jsonify({'level': level})
            return jsonify({'level': 50})  # Default if not available
        except Exception as e:
            logger.error(f"Get volume error: {e}")
            return jsonify({'error': str(e), 'error_type': 'api'}), 500

    # POST - set volume
    data = get_json_or_error()
    if data is None:
        return jsonify({'error': 'Invalid JSON', 'error_type': 'request'}), 400

    try:
        level = data.get('level', 50)
        level = max(0, min(100, int(level)))
        success = spotify.set_volume(level)
        if success:
            return jsonify({'success': True, 'level': level})
        return jsonify({'error': 'Failed to set volume', 'error_type': 'api'}), 500
    except (ValueError, TypeError) as e:
        return jsonify({'error': f'Invalid volume value: {e}', 'error_type': 'request'}), 400
    except Exception as e:
        logger.error(f"Set volume error: {e}")
        return jsonify({'error': str(e), 'error_type': 'api'}), 500


@app.route('/api/display', methods=['GET', 'POST'])
def display():
    """Get or set display power state (on/off)."""
    if request.method == 'GET':
        try:
            with open(DISPLAY_POWER_PATH, 'r') as f:
                power = int(f.read().strip())
            # 0 = on, 1 = off
            state = 'on' if power == 0 else 'off'
            return jsonify({'state': state})
        except (IOError, ValueError) as e:
            logger.error(f"Display read error: {e}")
            return jsonify({'error': str(e), 'error_type': 'hardware'}), 500

    # POST - set display state
    data = get_json_or_error()
    if data is None:
        return jsonify({'error': 'Invalid JSON', 'error_type': 'request'}), 400

    try:
        state = data.get('state', 'on')
        # 0 = on, 1 = off
        power = 0 if state == 'on' else 1
        with open(DISPLAY_POWER_PATH, 'w') as f:
            f.write(str(power))
        logger.info(f"Display set to {state}")
        return jsonify({'success': True, 'state': state})
    except IOError as e:
        logger.error(f"Display write error: {e}")
        return jsonify({'error': str(e), 'error_type': 'hardware'}), 500


@app.route('/api/sync-status')
def sync_status():
    """Get photo sync status."""
    try:
        if os.path.exists(SYNC_STATUS_FILE):
            with open(SYNC_STATUS_FILE, 'r') as f:
                content = f.read().strip()
                parts = content.split('|')
                return jsonify({
                    'last_sync': parts[0] if len(parts) > 0 else None,
                    'status': parts[1] if len(parts) > 1 else 'unknown',
                    'count': int(parts[2]) if len(parts) > 2 else 0
                })
        return jsonify({'last_sync': None, 'status': 'never', 'count': 0})
    except Exception as e:
        logger.error(f"Sync status error: {e}")
        return jsonify({'last_sync': None, 'status': 'error', 'error': str(e)})


@app.route('/api/theme', methods=['GET', 'POST'])
def theme():
    """Get or set theme preferences."""
    theme_file = '/tmp/photoframe_theme'

    if request.method == 'GET':
        try:
            if os.path.exists(theme_file):
                with open(theme_file, 'r') as f:
                    import json
                    return jsonify(json.load(f))
        except Exception:
            pass
        # Default theme
        return jsonify({
            'accent_color': '#1DB954',
            'overlay_opacity': 0.8,
            'indicator_style': 'gradient'
        })

    # POST - save theme
    data = get_json_or_error()
    if data is None:
        return jsonify({'error': 'Invalid JSON', 'error_type': 'request'}), 400

    try:
        import json
        with open(theme_file, 'w') as f:
            json.dump(data, f)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Theme save error: {e}")
        return jsonify({'error': str(e), 'error_type': 'io'}), 500


@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'spotify_authenticated': spotify.is_authenticated(),
        'photos_dir_exists': os.path.exists(PHOTOS_DIR)
    })


@app.route('/auth/spotify')
def spotify_auth():
    """Redirect to Spotify authorization."""
    auth_url = spotify.get_auth_url()
    if auth_url:
        return redirect(auth_url)
    return jsonify({'error': 'Spotify not configured'}), 500


@app.route('/callback')
def spotify_callback():
    """Handle Spotify OAuth callback."""
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        logger.error(f"Spotify auth error: {error}")
        return redirect('/?auth_error=' + error)

    if code:
        try:
            spotify.handle_callback(code)
            logger.info("Spotify authentication successful")
        except Exception as e:
            logger.error(f"Spotify callback error: {e}")
            return redirect('/?auth_error=callback_failed')

    return redirect('/')


if __name__ == '__main__':
    logger.info("Starting Photo Frame server")
    app.run(host='0.0.0.0', port=5000, debug=False)
