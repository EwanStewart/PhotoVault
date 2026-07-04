"""Pair Live Photo stills with separately exported video clips.

Apple stores a Live Photo as a still plus a MOV clip. Exports often
rename the clip, so basename matching fails. Both halves usually share
a content identifier; failing that, their capture times sit within a
few seconds of each other. One exiftool pass over the photos directory
reads both fields for every file, and the result is cached until the
directory contents change.
"""

import json
import logging
import os
import re
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)

MATCH_TOLERANCE_SECONDS = 10
EXIFTOOL_TIMEOUT_SECONDS = 120
VIDEO_EXTENSIONS = {'.mov'}

_cache = {'signature': None, 'pairs': {}}


def _scan_metadata(photos_dir):
    """Run one exiftool pass over the directory reading pairing fields."""
    command = [
        'exiftool', '-json',
        '-ContentIdentifier', '-CreationDate', '-DateTimeOriginal',
        photos_dir,
    ]
    entries = []
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=EXIFTOOL_TIMEOUT_SECONDS,
        )
        if completed.stdout:
            entries = json.loads(completed.stdout)
    except Exception as e:
        logger.error("exiftool scan failed: %s", e)
    return entries


def _parse_timestamp(value):
    """Parse an exiftool timestamp as local time, ignoring any timezone suffix."""
    result = None
    if value:
        match = re.match(r'(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})', value)
        if match:
            result = datetime(*(int(part) for part in match.groups()))
    return result


def _split_entries(entries):
    """Split an exiftool scan into photo and video records."""
    photos = []
    videos = []
    for item in entries:
        filename = os.path.basename(item.get('SourceFile', ''))
        ext = os.path.splitext(filename)[1].lower()
        record = {
            'filename': filename,
            'content_id': item.get('ContentIdentifier'),
            'taken': _parse_timestamp(
                item.get('DateTimeOriginal') or item.get('CreationDate')
            ),
        }
        if ext in VIDEO_EXTENSIONS:
            videos.append(record)
        elif filename:
            photos.append(record)
    return photos, videos


def _pair_by_content_id(photos, videos, pairs, used):
    """Pair photos to videos sharing the same Apple content identifier."""
    videos_by_id = {v['content_id']: v['filename'] for v in videos if v['content_id']}
    for photo in photos:
        video_name = videos_by_id.get(photo['content_id'])
        if photo['content_id'] and video_name and video_name not in used:
            pairs[photo['filename']] = video_name
            used.add(video_name)


def _pair_by_capture_time(photos, videos, pairs, used):
    """Pair remaining photos to the nearest video captured within tolerance."""
    candidates = []
    for photo in photos:
        if photo['filename'] in pairs or photo['taken'] is None:
            continue
        for video in videos:
            if video['taken'] is None:
                continue
            delta = abs((photo['taken'] - video['taken']).total_seconds())
            if delta <= MATCH_TOLERANCE_SECONDS:
                candidates.append((delta, photo['filename'], video['filename']))
    for _, photo_name, video_name in sorted(candidates):
        if photo_name not in pairs and video_name not in used:
            pairs[photo_name] = video_name
            used.add(video_name)


def _build_pairs(entries):
    """Match each video to at most one photo: exact id first, then capture time."""
    photos, videos = _split_entries(entries)
    pairs = {}
    used = set()
    _pair_by_content_id(photos, videos, pairs, used)
    _pair_by_capture_time(photos, videos, pairs, used)
    return pairs


def _directory_signature(photos_dir):
    """Names and mtimes of every file in the photos directory."""
    signature = ()
    try:
        with os.scandir(photos_dir) as it:
            signature = tuple(sorted(
                (item.name, item.stat().st_mtime) for item in it if item.is_file()
            ))
    except OSError:
        signature = ()
    return signature


def find_paired_video(photos_dir, photo_filename):
    """Return the video filename paired with the photo, or None."""
    signature = _directory_signature(photos_dir)
    if signature != _cache['signature']:
        has_videos = any(
            os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS
            for name, _ in signature
        )
        _cache['pairs'] = _build_pairs(_scan_metadata(photos_dir)) if has_videos else {}
        _cache['signature'] = signature
        if _cache['pairs']:
            logger.info("Live Photo pairs: %s", _cache['pairs'])
    return _cache['pairs'].get(photo_filename)
