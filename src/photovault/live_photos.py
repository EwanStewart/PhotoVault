"""Pair Live Photo stills with separately exported video clips.

Apple stores a Live Photo as a still plus a MOV clip. The two usually
share a basename, but the iPhone recycles file numbers, so a still and
an unrelated clip can collide on name. Matching runs in three tiers:
same basename first, then a shared content identifier, then the nearest
capture time within a few seconds. Every tier refuses a pair whose two
halves carry different content identifiers, which is how a recycled-name
collision is rejected. One exiftool pass over the photos directory reads
both fields for every file, cached until the directory contents change.
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
        'exiftool', '-json', '-r',
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


def _split_entries(entries, photos_dir):
    """Split an exiftool scan into photo and video records keyed by relative path."""
    photos = []
    videos = []
    for item in entries:
        source_file = item.get('SourceFile')
        if not source_file:
            continue
        filename = os.path.relpath(source_file, photos_dir)
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


def _content_ids_conflict(photo, video):
    """True when both files carry content identifiers and they differ."""
    photo_id = photo['content_id']
    video_id = video['content_id']
    return bool(photo_id and video_id and photo_id != video_id)


def _basename_consistent(photo, video):
    """True unless metadata proves a same-name photo and video are unrelated."""
    consistent = True
    if _content_ids_conflict(photo, video):
        consistent = False
    elif photo['taken'] and video['taken']:
        delta = abs((photo['taken'] - video['taken']).total_seconds())
        consistent = delta <= MATCH_TOLERANCE_SECONDS
    return consistent


def _pair_by_basename(photos, videos, pairs, used):
    """Pair a photo to a same-name video unless metadata contradicts it."""
    videos_by_stem = {}
    for video in videos:
        stem = os.path.splitext(video['filename'])[0]
        videos_by_stem.setdefault(stem, []).append(video)
    for photo in photos:
        stem = os.path.splitext(photo['filename'])[0]
        for video in videos_by_stem.get(stem, []):
            free = video['filename'] not in used and photo['filename'] not in pairs
            if free and _basename_consistent(photo, video):
                pairs[photo['filename']] = video['filename']
                used.add(video['filename'])
                break


def _pair_by_content_id(photos, videos, pairs, used):
    """Pair photos to videos sharing the same Apple content identifier."""
    videos_by_id = {v['content_id']: v['filename'] for v in videos if v['content_id']}
    for photo in photos:
        if photo['filename'] in pairs:
            continue
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
            if video['taken'] is None or _content_ids_conflict(photo, video):
                continue
            delta = abs((photo['taken'] - video['taken']).total_seconds())
            if delta <= MATCH_TOLERANCE_SECONDS:
                candidates.append((delta, photo['filename'], video['filename']))
    for _, photo_name, video_name in sorted(candidates):
        if photo_name not in pairs and video_name not in used:
            pairs[photo_name] = video_name
            used.add(video_name)


def _build_pairs(entries, photos_dir):
    """Match each video to at most one photo: exact id first, then capture time."""
    photos, videos = _split_entries(entries, photos_dir)
    pairs = {}
    used = set()
    _pair_by_basename(photos, videos, pairs, used)
    _pair_by_content_id(photos, videos, pairs, used)
    _pair_by_capture_time(photos, videos, pairs, used)
    return pairs


def _directory_signature(photos_dir):
    """Relative paths and mtimes of every file under the photos directory."""
    signature = ()
    try:
        entries = []
        for root, _, files in os.walk(photos_dir):
            for name in files:
                path = os.path.join(root, name)
                entries.append((os.path.relpath(path, photos_dir), os.path.getmtime(path)))
        signature = tuple(sorted(entries))
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
        _cache['pairs'] = _build_pairs(_scan_metadata(photos_dir), photos_dir) if has_videos else {}
        _cache['signature'] = signature
        if _cache['pairs']:
            logger.info("Live Photo pairs: %s", _cache['pairs'])
    return _cache['pairs'].get(photo_filename)
