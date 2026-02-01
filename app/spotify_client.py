import os
import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)

SCOPE = 'user-read-playback-state user-modify-playback-state user-read-currently-playing user-library-modify user-library-read'
CACHE_PATH = '/app/.cache/spotify_token'


class SpotifyClient:
    def __init__(self):
        self.client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        self.client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        self.redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://localhost:5000/callback')

        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

        self._sp_oauth = None
        self._sp = None
        self._current_track_id = None

        if self.client_id and self.client_secret:
            self._sp_oauth = SpotifyOAuth(
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
        if self._sp_oauth:
            token_info = self._sp_oauth.get_cached_token()
            if token_info and 'access_token' in token_info:
                self._sp = spotipy.Spotify(auth=token_info['access_token'])

    def _get_valid_client(self):
        """Get a valid Spotify client, refreshing token if needed."""
        if not self._sp_oauth:
            return None

        token_info = self._sp_oauth.get_cached_token()
        if not token_info or 'access_token' not in token_info:
            return None

        # Refresh token if needed
        if self._sp_oauth.is_token_expired(token_info):
            if 'refresh_token' not in token_info:
                logger.warning("No refresh token available")
                return None
            try:
                token_info = self._sp_oauth.refresh_access_token(token_info['refresh_token'])
                self._sp = spotipy.Spotify(auth=token_info['access_token'])
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                return None

        return self._sp

    def is_authenticated(self):
        """Check if we have a valid Spotify connection."""
        return self._get_valid_client() is not None

    def get_auth_url(self):
        """Get Spotify authorization URL."""
        if self._sp_oauth:
            return self._sp_oauth.get_authorize_url()
        return None

    def handle_callback(self, code):
        """Handle OAuth callback and get token."""
        if not self._sp_oauth:
            raise ValueError("Spotify OAuth not configured")

        token_info = self._sp_oauth.get_access_token(code)
        if not token_info or 'access_token' not in token_info:
            raise ValueError("Failed to get access token")

        self._sp = spotipy.Spotify(auth=token_info['access_token'])

    def get_now_playing(self):
        """Get currently playing track."""
        sp = self._get_valid_client()
        if not sp:
            return {'playing': False}

        try:
            current = sp.current_playback()

            if not current:
                return {'playing': False}

            is_playing = current.get('is_playing', False)
            item = current.get('item')

            if not item:
                return {'playing': False, 'is_playing': is_playing}

            self._current_track_id = item.get('id')

            artists = ', '.join([a['name'] for a in item.get('artists', [])])
            album_art = None
            images = item.get('album', {}).get('images', [])
            if images:
                album_art = images[0]['url']

            # Check if track is saved
            is_saved = False
            if self._current_track_id:
                try:
                    saved = sp.current_user_saved_tracks_contains([self._current_track_id])
                    is_saved = saved[0] if saved else False
                except Exception:
                    pass

            return {
                'playing': True,
                'is_playing': is_playing,
                'name': item.get('name', 'Unknown'),
                'artist': artists or 'Unknown Artist',
                'album': item.get('album', {}).get('name', ''),
                'album_art': album_art,
                'progress_ms': current.get('progress_ms', 0),
                'duration_ms': item.get('duration_ms', 0),
                'track_id': self._current_track_id,
                'is_saved': is_saved
            }
        except Exception as e:
            logger.error(f"Spotify error: {e}")
            return {'playing': False, 'error': str(e)}

    def skip_track(self):
        """Skip to next track."""
        sp = self._get_valid_client()
        if not sp:
            return False

        try:
            sp.next_track()
            return True
        except Exception as e:
            logger.error(f"Skip error: {e}")
            return False

    def pause_playback(self):
        """Pause playback."""
        sp = self._get_valid_client()
        if not sp:
            return False

        try:
            sp.pause_playback()
            return True
        except Exception as e:
            logger.error(f"Pause error: {e}")
            return False

    def resume_playback(self):
        """Resume playback."""
        sp = self._get_valid_client()
        if not sp:
            return False

        try:
            sp.start_playback()
            return True
        except Exception as e:
            logger.error(f"Resume error: {e}")
            return False

    def save_current_track(self):
        """Save current track to user's library."""
        sp = self._get_valid_client()
        if not sp or not self._current_track_id:
            return False

        try:
            sp.current_user_saved_tracks_add([self._current_track_id])
            return True
        except Exception as e:
            logger.error(f"Save track error: {e}")
            return False

    def unsave_current_track(self):
        """Remove current track from user's library."""
        sp = self._get_valid_client()
        if not sp or not self._current_track_id:
            return False

        try:
            sp.current_user_saved_tracks_delete([self._current_track_id])
            return True
        except Exception as e:
            logger.error(f"Unsave track error: {e}")
            return False

    def get_queue(self):
        """Get upcoming tracks in queue."""
        sp = self._get_valid_client()
        if not sp:
            return {'tracks': []}

        try:
            queue = sp.queue()
            tracks = []

            for item in queue.get('queue', [])[:5]:  # Limit to 5 tracks
                artists = ', '.join([a['name'] for a in item.get('artists', [])])
                album_art = None
                images = item.get('album', {}).get('images', [])
                if images:
                    # Use smaller image for queue
                    album_art = images[-1]['url'] if len(images) > 1 else images[0]['url']

                tracks.append({
                    'name': item.get('name', 'Unknown'),
                    'artist': artists or 'Unknown Artist',
                    'album_art': album_art,
                    'duration_ms': item.get('duration_ms', 0)
                })

            return {'tracks': tracks}
        except Exception as e:
            logger.error(f"Get queue error: {e}")
            return {'tracks': [], 'error': str(e)}

    def get_volume(self):
        """Get current playback volume (0-100)."""
        sp = self._get_valid_client()
        if not sp:
            return None

        try:
            playback = sp.current_playback()
            if playback and playback.get('device'):
                return playback['device'].get('volume_percent', 50)
            return None
        except Exception as e:
            logger.error(f"Get volume error: {e}")
            return None

    def set_volume(self, percent):
        """Set playback volume (0-100)."""
        sp = self._get_valid_client()
        if not sp:
            return False

        try:
            percent = max(0, min(100, int(percent)))
            sp.volume(percent)
            return True
        except Exception as e:
            logger.error(f"Set volume error: {e}")
            return False
