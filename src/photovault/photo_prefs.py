"""Remember which photos the slideshow is allowed to show.

Flags key on the file's basename rather than its path, because the
organiser moves a photo into a location folder once enrichment finds its
coordinates. Keying on the path would lose the flag on that move.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


def key_for(filename):
    """Preference key for a photos-relative path.

    @param filename Photos-relative path of the photo
    @returns The basename used as the preference key
    """
    return os.path.basename(filename)


def is_enabled(prefs, filename):
    """True unless the photo has been switched off.

    @param prefs Preference mapping
    @param filename Photos-relative path of the photo
    @returns True when the slideshow may show the photo
    """
    entry = prefs.get(key_for(filename), {})
    return entry.get('enabled', True)


def set_enabled(prefs, filename, enabled):
    """Record whether the slideshow may show a photo.

    @param prefs Preference mapping to update in place
    @param filename Photos-relative path of the photo
    @param enabled True to allow the photo, False to hold it back
    @returns The updated preference mapping
    """
    prefs[key_for(filename)] = {'enabled': bool(enabled)}
    return prefs


def forget(prefs, filename):
    """Drop any flag held for a photo, for use once it is deleted.

    @param prefs Preference mapping to update in place
    @param filename Photos-relative path of the photo
    @returns The updated preference mapping
    """
    prefs.pop(key_for(filename), None)
    return prefs


def filter_enabled(prefs, photos):
    """Keep only the photos the slideshow may show.

    @param prefs Preference mapping
    @param photos Photo dicts carrying a filename
    @returns A new list holding the enabled photos
    """
    return [photo for photo in photos if is_enabled(prefs, photo.get('filename', ''))]


def load(path):
    """Read the flags from disk, treating a missing or broken file as none.

    @param path Path of the preferences file
    @returns The preference mapping
    """
    prefs = {}
    try:
        with open(path, 'r') as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            prefs = loaded
    except FileNotFoundError:
        prefs = {}
    except (OSError, ValueError) as e:
        logger.warning("Could not read photo preferences from %s: %s", path, e)
    return prefs


def save(path, prefs):
    """Write the flags to disk atomically.

    @param path Path of the preferences file
    @param prefs Preference mapping to write
    """
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w') as handle:
        json.dump(prefs, handle)
    os.replace(tmp_path, path)
