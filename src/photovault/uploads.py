"""Accept photos uploaded from the phone and put them on Google Drive.

An upload goes to Drive before it appears in the local photos directory.
The sync watcher mirrors Drive onto the Pi and deletes anything local
that the remote does not hold, so a file placed locally first would
vanish on the next sync.

A Live Photo arrives as two parts in one request. The clip is renamed
after the still, which puts both halves on the same basename and lets
the pairing in live_photos match them without falling back to capture
time.
"""

import logging
import os
import re
import time

import photovault.drive as drive

logger = logging.getLogger(__name__)

PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.heic'}
VIDEO_EXTENSIONS = {'.mov'}
STAGING_DIR_NAME = '.uploads'
STAGING_SUFFIX = '.part'
MAX_STEM_LENGTH = 80
STAGING_MAX_AGE_SECONDS = 3600
UNSAFE_CHARACTERS = re.compile(r'[^A-Za-z0-9._-]')


class RejectedUpload(Exception):
    """Raised when an uploaded file is not a photo or clip we will store."""


def _safe_stem(filename):
    """Filename stem reduced to characters that are safe in a path.

    @param filename The name as the client sent it
    @returns A sanitised stem
    """
    stem = os.path.splitext(os.path.basename(filename.replace('\\', '/')))[0]
    return UNSAFE_CHARACTERS.sub('', stem.replace(' ', '_'))[:MAX_STEM_LENGTH]


def _checked_extension(filename, allowed, label):
    """Extension of an uploaded file, rejecting anything not allowed.

    @param filename The name as the client sent it
    @param allowed Extensions this kind of upload may use
    @param label Word for this kind of upload, used in the error
    @returns The extension as sent, including the leading dot
    """
    extension = os.path.splitext(filename)[1]
    if extension.lower() not in allowed:
        raise RejectedUpload(f'{label} must be one of: {", ".join(sorted(allowed))}')
    return extension


def _stem_is_free(stem, extensions, existing):
    """True when no stored file already uses this stem for these extensions.

    @param stem Candidate filename stem
    @param extensions Extensions the upload will occupy
    @param existing Basenames already stored
    @returns True when the stem is unused
    """
    wanted = {f'{stem}{extension}'.lower() for extension in extensions}
    return not (wanted & existing)


def _free_stem(stem, extensions, existing):
    """First unused stem, suffixing a counter when the plain stem is taken.

    @param stem Preferred filename stem
    @param extensions Extensions the upload will occupy
    @param existing Basenames already stored
    @returns A stem no stored file uses
    """
    lowered = {name.lower() for name in existing}
    candidate = stem
    counter = 0
    while not _stem_is_free(candidate, extensions, lowered):
        counter += 1
        candidate = f'{stem}-{counter}'
    return candidate


def plan_names(photo_filename, video_filename, existing):
    """Decide the stored names for an uploaded still and its optional clip.

    @param photo_filename Name of the still as the client sent it
    @param video_filename Name of the clip as the client sent it, or None
    @param existing Basenames already stored under the photos directory
    @returns Tuple of the still's stored name and the clip's, the clip None when absent
    """
    photo_extension = _checked_extension(photo_filename, PHOTO_EXTENSIONS, 'Photo')
    video_extension = None
    if video_filename:
        video_extension = _checked_extension(video_filename, VIDEO_EXTENSIONS, 'Video')

    stem = _safe_stem(photo_filename)
    if not stem:
        raise RejectedUpload('Photo needs a name')

    extensions = [photo_extension] + ([video_extension] if video_extension else [])
    stem = _free_stem(stem, extensions, existing)
    video_name = f'{stem}{video_extension}' if video_extension else None
    return f'{stem}{photo_extension}', video_name


def existing_basenames(photos_dir):
    """Basenames of every file stored under the photos directory.

    @param photos_dir Root of the local photos directory
    @returns Set of basenames, ignoring which folder each file sits in
    """
    names = set()
    for root, _, files in os.walk(photos_dir):
        if os.path.basename(root) != STAGING_DIR_NAME:
            names.update(files)
    return names


def _stage(photos_dir, upload_file, name):
    """Write one uploaded file into the staging directory.

    @param photos_dir Root of the local photos directory
    @param upload_file The uploaded file, with a save method
    @param name Name the file will take once published
    @returns Path of the staged file
    """
    staging_dir = os.path.join(photos_dir, STAGING_DIR_NAME)
    os.makedirs(staging_dir, exist_ok=True)
    staged_path = os.path.join(staging_dir, name + STAGING_SUFFIX)
    upload_file.save(staged_path)
    return staged_path


def _discard(staged):
    """Remove staged files after a failure.

    @param staged Paths of the staged files
    """
    for path in staged:
        try:
            os.remove(path)
        except OSError:
            pass


def _publish(photos_dir, staged_path, name):
    """Move a staged file into the photos directory under its final name.

    @param photos_dir Root of the local photos directory
    @param staged_path Path of the staged file
    @param name Final name for the file
    """
    os.replace(staged_path, os.path.join(photos_dir, name))


def save(photos_dir, remote, photo, video=None, upload=None):
    """Store an uploaded still, and its clip when one came with it.

    @param photos_dir Root of the local photos directory
    @param remote The rclone remote root, such as gdrive:PhotoFrame
    @param photo The uploaded still, with a filename and a save method
    @param video The uploaded clip, or None
    @param upload Remote upload function, injectable for tests
    @returns Dict of the stored still and clip names
    """
    push = upload or drive.upload
    existing = existing_basenames(photos_dir)
    video_filename = video.filename if video else None
    photo_name, video_name = plan_names(photo.filename, video_filename, existing)

    parts = [(photo, photo_name)]
    if video_name:
        parts.append((video, video_name))
    _store_parts(photos_dir, remote, parts, push)

    logger.info("Stored upload %s%s", photo_name, f' with {video_name}' if video_name else '')
    return {'photo': photo_name, 'video': video_name}


def _store_parts(photos_dir, remote, parts, push):
    """Stage the parts, push them to the remote, then publish them locally.

    Nothing appears in the photos directory until every part has reached
    the remote, so a failed push leaves no local file for the next sync
    to delete again.

    @param photos_dir Root of the local photos directory
    @param remote The rclone remote root
    @param parts Pairs of uploaded file and the name it will take
    @param push Remote upload function
    """
    staged = [(_stage(photos_dir, item, name), name) for item, name in parts]
    try:
        for staged_path, name in staged:
            push(remote, staged_path, name)
    except Exception:
        _discard(path for path, _ in staged)
        raise

    for staged_path, name in staged:
        _publish(photos_dir, staged_path, name)


def save_clip(photos_dir, remote, video, upload=None):
    """Store a Live Photo clip that arrived without its still.

    The clip keeps its own name, so pairing falls back to the capture
    time comparison in live_photos once the still turns up.

    @param photos_dir Root of the local photos directory
    @param remote The rclone remote root, such as gdrive:PhotoFrame
    @param video The uploaded clip, with a filename and a save method
    @param upload Remote upload function, injectable for tests
    @returns Dict of the stored still and clip names, the still always None
    """
    push = upload or drive.upload
    extension = _checked_extension(video.filename, VIDEO_EXTENSIONS, 'Video')
    stem = _safe_stem(video.filename)
    if not stem:
        raise RejectedUpload('Clip needs a name')

    name = f'{_free_stem(stem, [extension], existing_basenames(photos_dir))}{extension}'
    _store_parts(photos_dir, remote, [(video, name)], push)

    logger.info("Stored clip %s awaiting its still", name)
    return {'photo': None, 'video': name}


def sweep_staging(photos_dir):
    """Delete staged files a crash left behind mid-upload.

    A part file is removed only once it is too old to belong to an
    upload still in flight.

    @param photos_dir Root of the local photos directory
    @returns Count of stale files removed
    """
    staging_dir = os.path.join(photos_dir, STAGING_DIR_NAME)
    cutoff = time.time() - STAGING_MAX_AGE_SECONDS
    removed = 0
    try:
        for name in os.listdir(staging_dir):
            path = os.path.join(staging_dir, name)
            if name.endswith(STAGING_SUFFIX) and os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
    except OSError:
        removed = removed
    if removed:
        logger.info("Swept %d stale staged upload(s)", removed)
    return removed
