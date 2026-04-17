import os
import json
import logging
import time
import urllib.request
import urllib.error
from pathlib import Path
from flask import Flask, render_template, jsonify, send_from_directory, redirect, request, send_file
from photovault.spotify_client import SpotifyClient
from photovault.tapo_client import TapoBulbClient, COLOUR_PRESETS
import pycountry
from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIF/HEIC opener with Pillow
register_heif_opener()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

REPO_ROOT = Path(__file__).resolve().parents[2]

PHOTOS_DIR = os.environ.get('PHOTOS_DIR', str(REPO_ROOT / 'photos'))
HEIC_CACHE_DIR = '/tmp/photovault_heic_cache'
FLAG_CACHE_DIR = '/tmp/photovault_flag_cache'
GEOCODE_CACHE_FILE = str(REPO_ROOT / 'geocode_cache.json')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.heic'}
VIDEO_EXTENSIONS = {'.mov'}

# Nominatim rate limiting (1 request per second)
NOMINATIM_LAST_REQUEST_TIME = 0
NOMINATIM_MIN_INTERVAL = 1.0

# In-memory caches
_geocode_cache = {}
_photo_cache = []
_photo_cache_fileset = set()

# Ensure cache directories exist
os.makedirs(HEIC_CACHE_DIR, exist_ok=True)
os.makedirs(FLAG_CACHE_DIR, exist_ok=True)

# Hardware paths - configurable via environment variables
BRIGHTNESS_PATH = os.environ.get('BRIGHTNESS_PATH', '/sys/class/backlight/10-0045/brightness')
DISPLAY_POWER_PATH = os.environ.get('DISPLAY_POWER_PATH', '/sys/class/backlight/10-0045/bl_power')
MAX_BRIGHTNESS_PATH = os.environ.get('MAX_BRIGHTNESS_PATH', '/sys/class/backlight/10-0045/max_brightness')
BRIGHTNESS_DESIRED = '/tmp/photovault_brightness'

# Sync status file
SYNC_STATUS_FILE = '/tmp/photovault_sync_status'


spotify = SpotifyClient()
tapo = TapoBulbClient()


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




def gps_to_decimal(gps_coords, gps_ref):
    """Convert GPS coordinates from EXIF format to decimal degrees."""
    try:
        degrees = float(gps_coords[0])
        minutes = float(gps_coords[1])
        seconds = float(gps_coords[2])
        decimal = degrees + minutes / 60 + seconds / 3600
        if gps_ref in ['S', 'W']:
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None


def get_photo_metadata(filepath):
    """
    Extract GPS and date metadata from photo file.

    @param filepath Path to the photo file
    @returns Dictionary with 'lat', 'lon', and 'date_taken' keys or None
    """
    metadata = {}

    try:
        with Image.open(filepath) as img:
            exif = img.getexif()
            if not exif:
                return None

            # Extract date taken (tag 36867 = DateTimeOriginal, 306 = DateTime)
            exif_ifd = exif.get_ifd(34665)  # EXIF IFD
            date_taken = None
            if exif_ifd:
                date_taken = exif_ifd.get(36867)  # DateTimeOriginal
            if not date_taken:
                date_taken = exif.get(306)  # DateTime fallback

            if date_taken:
                metadata['date_taken'] = date_taken

            # GPS info is in tag 34853
            gps_ifd = exif.get_ifd(34853)
            if gps_ifd:
                # GPS tags: 1=LatRef, 2=Lat, 3=LonRef, 4=Lon
                lat_ref = gps_ifd.get(1)
                lat = gps_ifd.get(2)
                lon_ref = gps_ifd.get(3)
                lon = gps_ifd.get(4)

                if lat and lon and lat_ref and lon_ref:
                    lat_decimal = gps_to_decimal(lat, lat_ref)
                    lon_decimal = gps_to_decimal(lon, lon_ref)
                    if lat_decimal is not None and lon_decimal is not None:
                        metadata['lat'] = lat_decimal
                        metadata['lon'] = lon_decimal

    except Exception as e:
        logger.debug(f"Failed to extract metadata from {filepath}: {e}")

    return metadata if metadata else None
def get_country_name(country_code):
    """Get country name from ISO country code using pycountry."""
    country_name = None

    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if country:
            country_name = country.name
    except Exception:
        pass

    return country_name


def get_flag_code(country_code, admin1):
    """Get flag code, using regional flags for UK nations."""
    flag_code = country_code.lower() if country_code else None

    # Use regional flags for UK nations
    if country_code == 'GB' and admin1:
        uk_region_flags = {
            'Scotland': 'gb-sct',
            'Wales': 'gb-wls',
            'England': 'gb-eng',
            'Northern Ireland': 'gb-nir',
        }
        flag_code = uk_region_flags.get(admin1, 'gb')

    return flag_code


def get_display_country(country_code, admin1):
    """Get display name for country, using region name for UK nations."""
    display_name = None

    # For UK, show the nation name instead of United Kingdom
    if country_code == 'GB' and admin1 in ('Scotland', 'Wales', 'England', 'Northern Ireland'):
        display_name = admin1
    else:
        display_name = get_country_name(country_code)

    return display_name


def load_geocode_cache_from_disk():
    """Load geocode cache from disk into memory at startup."""
    global _geocode_cache

    try:
        if os.path.exists(GEOCODE_CACHE_FILE):
            with open(GEOCODE_CACHE_FILE, 'r') as f:
                _geocode_cache = json.load(f)
    except Exception as e:
        logger.warning("Failed to load geocode cache: %s", e)


def save_geocode_cache_to_disk():
    """Flush in-memory geocode cache to disk."""
    try:
        with open(GEOCODE_CACHE_FILE, 'w') as f:
            json.dump(_geocode_cache, f)
    except Exception as e:
        logger.warning("Failed to save geocode cache: %s", e)


def get_uk_nation_from_state(state_name):
    """Extract UK nation from state name returned by Nominatim."""
    uk_nation = None

    if not state_name:
        uk_nation = None
    elif 'Scotland' in state_name or 'Alba' in state_name:
        uk_nation = 'Scotland'
    elif 'Wales' in state_name or 'Cymru' in state_name:
        uk_nation = 'Wales'
    elif 'Northern Ireland' in state_name:
        uk_nation = 'Northern Ireland'
    else:
        uk_nation = 'England'

    return uk_nation


def nominatim_reverse_geocode(lat, lon):
    """
    Reverse geocode using Nominatim (OpenStreetMap) API.

    @param lat Latitude in decimal degrees
    @param lon Longitude in decimal degrees
    @returns Dictionary with location data or None on failure
    """
    global NOMINATIM_LAST_REQUEST_TIME
    result_data = None

    # Rate limiting - ensure at least 1 second between requests
    elapsed = time.time() - NOMINATIM_LAST_REQUEST_TIME
    if elapsed < NOMINATIM_MIN_INTERVAL:
        time.sleep(NOMINATIM_MIN_INTERVAL - elapsed)

    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"

    try:
        request_obj = urllib.request.Request(
            url,
            headers={'User-Agent': 'PhotoFrame/1.0 (Raspberry Pi photo frame)'}
        )
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        NOMINATIM_LAST_REQUEST_TIME = time.time()

        address = data.get('address', {})
        country_code = address.get('country_code', '').upper()

        # Get the most appropriate place name (city > town > village > suburb)
        city = (
            address.get('city') or
            address.get('town') or
            address.get('village') or
            address.get('suburb') or
            address.get('municipality') or
            address.get('county') or
            ''
        )

        state = address.get('state', '')

        # Handle UK nations specially
        admin1 = None
        if country_code == 'GB':
            admin1 = get_uk_nation_from_state(state)
        else:
            admin1 = state

        # Get country/region display name
        country_display = get_display_country(country_code, admin1)

        # Format as "City, Country"
        if city and country_display:
            location_text = f"{city}, {country_display}"
        elif city:
            location_text = city
        elif country_display:
            location_text = country_display
        else:
            location_text = None

        if location_text:
            result_data = {
                'text': location_text,
                'country_code': get_flag_code(country_code, admin1)
            }

    except urllib.error.URLError as e:
        logger.debug("Nominatim request failed for %s,%s: %s", lat, lon, e)
    except Exception as e:
        logger.debug("Nominatim geocoding failed for %s,%s: %s", lat, lon, e)

    return result_data


def reverse_geocode(lat, lon):
    """
    Reverse geocode coordinates to location name using Nominatim with caching.

    @param lat Latitude in decimal degrees
    @param lon Longitude in decimal degrees
    @returns Dictionary with 'text' and 'country_code' keys or None
    """
    global _geocode_cache
    result_data = None

    # Round coordinates for cache key (4 decimal places ~ 11m precision)
    cache_key = f"{round(lat, 4)},{round(lon, 4)}"

    if cache_key in _geocode_cache:
        result_data = _geocode_cache[cache_key]
    else:
        result_data = nominatim_reverse_geocode(lat, lon)

        if result_data:
            _geocode_cache[cache_key] = result_data
            save_geocode_cache_to_disk()

    return result_data


def find_live_photo_video(photo_path):
    """Check if a matching MOV file exists for Live Photo."""
    base_name = os.path.splitext(photo_path)[0]
    for ext in ['.MOV', '.mov']:
        video_path = base_name + ext
        if os.path.exists(video_path):
            return os.path.basename(video_path)
    return None


@app.route('/')
def index():
    return render_template('index.html')


def build_photo_data(filename):
    """Build metadata dict for a single photo file."""
    filepath = os.path.join(PHOTOS_DIR, filename)
    photo_data = None

    try:
        stat = os.stat(filepath)
        photo_data = {
            'filename': filename,
            'modified': stat.st_mtime,
            'size': stat.st_size
        }

        metadata = get_photo_metadata(filepath)
        if metadata:
            if metadata.get('date_taken'):
                photo_data['date_taken'] = metadata['date_taken']

            if metadata.get('lat') and metadata.get('lon'):
                photo_data['coords'] = {
                    'lat': metadata['lat'],
                    'lon': metadata['lon']
                }
                location_data = reverse_geocode(metadata['lat'], metadata['lon'])
                if location_data:
                    photo_data['location'] = location_data['text']
                    if location_data.get('country_code'):
                        photo_data['country_code'] = location_data['country_code']

        video_filename = find_live_photo_video(filepath)
        if video_filename:
            photo_data['isLivePhoto'] = True
            photo_data['videoFilename'] = video_filename

    except OSError:
        photo_data = {'filename': filename, 'modified': 0, 'size': 0}

    return photo_data


def refresh_photo_cache():
    """Rebuild photo cache only when the file set changes."""
    global _photo_cache, _photo_cache_fileset

    if not os.path.exists(PHOTOS_DIR):
        _photo_cache = []
        _photo_cache_fileset = set()
        return

    current_files = set()
    for f in os.listdir(PHOTOS_DIR):
        ext = os.path.splitext(f)[1].lower()
        if ext in ALLOWED_EXTENSIONS:
            current_files.add(f)

    if current_files == _photo_cache_fileset:
        return

    added = current_files - _photo_cache_fileset
    removed = _photo_cache_fileset - current_files

    if removed:
        _photo_cache = [p for p in _photo_cache if p['filename'] not in removed]

    for filename in added:
        photo_data = build_photo_data(filename)
        if photo_data:
            _photo_cache.append(photo_data)

    _photo_cache.sort(key=lambda x: x['modified'], reverse=True)
    _photo_cache_fileset = current_files


@app.route('/photos')
def list_photos():
    """Return cached list of photo filenames with metadata."""
    refresh_photo_cache()

    return jsonify(_photo_cache)


@app.route('/photos/<path:filename>')
def serve_photo(filename):
    """Serve a photo file, converting HEIC to JPEG on the fly."""
    if not validate_filename(filename):
        logger.warning(f"Invalid filename requested: {filename}")
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(PHOTOS_DIR, filename)
    ext = os.path.splitext(filename)[1].lower()

    # Convert HEIC to JPEG for browser compatibility
    if ext == '.heic':
        # Check cache first
        cache_filename = os.path.splitext(filename)[0] + '.jpg'
        cache_path = os.path.join(HEIC_CACHE_DIR, cache_filename)

        if not os.path.exists(cache_path) or os.path.getmtime(filepath) > os.path.getmtime(cache_path):
            try:
                with Image.open(filepath) as img:
                    # Convert to RGB (HEIC may have alpha)
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    img.save(cache_path, 'JPEG', quality=90)
                logger.info(f"Converted HEIC to JPEG: {filename}")
            except Exception as e:
                logger.error(f"Failed to convert HEIC {filename}: {e}")
                return jsonify({'error': 'Failed to convert image'}), 500

        return send_file(cache_path, mimetype='image/jpeg')

    return send_from_directory(PHOTOS_DIR, filename)


@app.route('/photos/video/<path:filename>')
def serve_video(filename):
    """Serve a video file for Live Photos."""
    if not validate_filename(filename):
        logger.warning(f"Invalid video filename requested: {filename}")
        return jsonify({'error': 'Invalid filename'}), 400

    # Validate video extension
    ext = os.path.splitext(filename)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        return jsonify({'error': 'Invalid file type'}), 400

    return send_from_directory(PHOTOS_DIR, filename)


@app.route('/flags/<country_code>.svg')
def serve_flag(country_code):
    """Serve country flag SVG with local caching."""
    import re

    # Validate country code (2 lowercase letters only)
    if not re.match(r'^[a-z]{2}(-[a-z]{3})?$', country_code):
        return jsonify({'error': 'Invalid country code'}), 400

    cache_path = os.path.join(FLAG_CACHE_DIR, f"{country_code}.svg")

    # Check cache first
    if os.path.exists(cache_path):
        return send_file(cache_path, mimetype='image/svg+xml')

    # Fetch from FlagCDN
    flag_url = f"https://flagcdn.com/{country_code}.svg"
    try:
        request_obj = urllib.request.Request(
            flag_url,
            headers={'User-Agent': 'PhotoFrame/1.0'}
        )
        with urllib.request.urlopen(request_obj, timeout=10) as response:
            svg_data = response.read()

        # Cache locally
        with open(cache_path, 'wb') as f:
            f.write(svg_data)

        logger.info(f"Cached flag for {country_code}")
        return send_file(cache_path, mimetype='image/svg+xml')
    except Exception as e:
        logger.error(f"Failed to fetch flag for {country_code}: {e}")
        return jsonify({'error': 'Failed to fetch flag'}), 500


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
    theme_file = '/tmp/photovault_theme'

    if request.method == 'GET':
        try:
            if os.path.exists(theme_file):
                with open(theme_file, 'r') as f:
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
        with open(theme_file, 'w') as f:
            json.dump(data, f)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Theme save error: {e}")
        return jsonify({'error': str(e), 'error_type': 'io'}), 500


@app.route('/api/bulbs')
def get_bulbs():
    """
    Get states of all connected Tapo bulbs.

    @returns JSON array of bulb states with connection status
    """
    try:
        states = tapo.get_all_bulb_states()
        return jsonify({'bulbs': states, 'presets': COLOUR_PRESETS})
    except Exception as error:
        logger.error("Failed to get bulb states: %s", error)
        return jsonify({'error': str(error), 'error_type': 'bulb'}), 500


@app.route('/api/bulbs/<bulb_id>/power', methods=['POST'])
def set_bulb_power(bulb_id):
    """
    Set power state for a single bulb.

    @param bulb_id The ID of the bulb to control
    @returns JSON result with success status
    """
    data = get_json_or_error()
    if data is None:
        return jsonify({'error': 'Invalid JSON', 'error_type': 'request'}), 400

    power_on = data.get('power', True)

    try:
        result = tapo.set_bulb_power(bulb_id, power_on)
        if result['success']:
            return jsonify(result)
        return jsonify(result), 500
    except Exception as error:
        logger.error("Failed to set bulb %s power: %s", bulb_id, error)
        return jsonify({'error': str(error), 'error_type': 'bulb'}), 500


@app.route('/api/bulbs/<bulb_id>/colour', methods=['POST'])
def set_bulb_colour(bulb_id):
    """
    Set colour for a single bulb.

    Accepts either a preset name or explicit HSB values.

    @param bulb_id The ID of the bulb to control
    @returns JSON result with success status
    """
    data = get_json_or_error()
    if data is None:
        return jsonify({'error': 'Invalid JSON', 'error_type': 'request'}), 400

    # Check for preset name
    preset_name = data.get('preset')
    if preset_name and preset_name in COLOUR_PRESETS:
        preset = COLOUR_PRESETS[preset_name]
        hue = preset['hue']
        saturation = preset['saturation']
        brightness = preset['brightness']
    else:
        hue = data.get('hue', 0)
        saturation = data.get('saturation', 100)
        brightness = data.get('brightness', 100)

    try:
        result = tapo.set_bulb_colour(bulb_id, hue, saturation, brightness)
        if result['success']:
            return jsonify(result)
        return jsonify(result), 500
    except Exception as error:
        logger.error("Failed to set bulb %s colour: %s", bulb_id, error)
        return jsonify({'error': str(error), 'error_type': 'bulb'}), 500


@app.route('/api/bulbs/all/power', methods=['POST'])
def set_all_bulbs_power():
    """
    Set power state for all bulbs.

    @returns JSON result with success count and individual results
    """
    data = get_json_or_error()
    if data is None:
        return jsonify({'error': 'Invalid JSON', 'error_type': 'request'}), 400

    power_on = data.get('power', True)

    try:
        result = tapo.set_all_power(power_on)
        return jsonify(result)
    except Exception as error:
        logger.error("Failed to set all bulbs power: %s", error)
        return jsonify({'error': str(error), 'error_type': 'bulb'}), 500


@app.route('/api/bulbs/all/colour', methods=['POST'])
def set_all_bulbs_colour():
    """
    Set colour for all bulbs.

    Accepts either a preset name or explicit HSB values.

    @returns JSON result with success count and individual results
    """
    data = get_json_or_error()
    if data is None:
        return jsonify({'error': 'Invalid JSON', 'error_type': 'request'}), 400

    # Check for preset name
    preset_name = data.get('preset')
    if preset_name and preset_name in COLOUR_PRESETS:
        preset = COLOUR_PRESETS[preset_name]
        hue = preset['hue']
        saturation = preset['saturation']
        brightness = preset['brightness']
    else:
        hue = data.get('hue', 0)
        saturation = data.get('saturation', 100)
        brightness = data.get('brightness', 100)

    try:
        result = tapo.set_all_colour(hue, saturation, brightness)
        return jsonify(result)
    except Exception as error:
        logger.error("Failed to set all bulbs colour: %s", error)
        return jsonify({'error': str(error), 'error_type': 'bulb'}), 500


@app.route('/api/bulbs/<bulb_id>/brightness', methods=['POST'])
def set_bulb_brightness(bulb_id):
    """
    Set brightness for a single bulb, preserving its current colour.

    @param bulb_id The ID of the bulb to control
    @returns JSON result with success status
    """
    data = get_json_or_error()
    if data is None:
        return jsonify({'error': 'Invalid JSON', 'error_type': 'request'}), 400

    brightness_level = max(1, min(100, int(data.get('brightness', 100))))

    try:
        result = tapo.set_bulb_brightness(bulb_id, brightness_level)
        if result['success']:
            return jsonify(result)
        return jsonify(result), 500
    except Exception as error:
        logger.error("Failed to set bulb %s brightness: %s", bulb_id, error)
        return jsonify({'error': str(error), 'error_type': 'bulb'}), 500


@app.route('/api/bulbs/all/brightness', methods=['POST'])
def set_all_bulbs_brightness():
    """
    Set brightness for all bulbs, preserving their current colours.

    @returns JSON result with success count and individual results
    """
    data = get_json_or_error()
    if data is None:
        return jsonify({'error': 'Invalid JSON', 'error_type': 'request'}), 400

    brightness_level = max(1, min(100, int(data.get('brightness', 100))))

    try:
        result = tapo.set_all_brightness(brightness_level)
        return jsonify(result)
    except Exception as error:
        logger.error("Failed to set all bulbs brightness: %s", error)
        return jsonify({'error': str(error), 'error_type': 'bulb'}), 500


@app.route('/api/bulbs/<bulb_id>/reconnect', methods=['POST'])
def reconnect_bulb(bulb_id):
    """
    Attempt to reconnect a disconnected bulb.

    Uses exponential backoff with up to 3 retry attempts.

    @param bulb_id The ID of the bulb to reconnect
    @returns JSON result with success status
    """
    try:
        result = tapo.reconnect_bulb(bulb_id)
        if result['success']:
            return jsonify(result)
        return jsonify(result), 500
    except Exception as error:
        logger.error("Failed to reconnect bulb %s: %s", bulb_id, error)
        return jsonify({'error': str(error), 'error_type': 'bulb'}), 500


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
    load_geocode_cache_from_disk()
    logger.info("Starting Photo Frame server")
    app.run(host='0.0.0.0', port=5000, debug=False)
