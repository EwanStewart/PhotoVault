"""Move located photos into per-location folders on Google Drive.

Once enrichment reverse-geocodes a photo, this module plans and runs
server-side rclone moves so the layout matches the location. A plain
photo lands in a folder named after its location. A Live Photo lands in
its own folder, named after the photo, holding just the still and its
clip. Planning is idempotent: a file already in the right place is left
alone. The sync watcher then mirrors the new layout locally.
"""

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

RCLONE_TIMEOUT_SECONDS = 60


def _folder_name(location):
    """Location string as a safe single folder name."""
    return location.replace('/', '-').replace('\\', '-').strip()


def plan_moves(photos):
    """List (source, destination) moves that sort located photos into folders."""
    moves = []
    for photo in photos:
        location = photo.get('location')
        filename = photo.get('filename', '')
        if not location or not filename:
            continue
        folder = _folder_name(location)
        photo_name = os.path.basename(filename)
        video = photo.get('videoFilename')
        if video:
            video_name = os.path.basename(video)
            stem = os.path.splitext(photo_name)[0]
            pair_folder = f'{folder}/{stem}'
            photo_target = f'{pair_folder}/{photo_name}'
            video_target = f'{pair_folder}/{video_name}'
            if filename != photo_target:
                moves.append((filename, photo_target))
            if video != video_target:
                moves.append((video, video_target))
        else:
            photo_target = f'{folder}/{photo_name}'
            if filename != photo_target:
                moves.append((filename, photo_target))
    return moves


def _run_rclone(args):
    """Run one rclone command, raising with rclone's own error on failure."""
    completed = subprocess.run(['rclone'] + args, capture_output=True, text=True,
                               timeout=RCLONE_TIMEOUT_SECONDS)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        detail = stderr.splitlines()[-1] if stderr else f'exit status {completed.returncode}'
        raise RuntimeError(detail)


def organise(remote, photos):
    """Move located root-level photos into location folders on the remote."""
    moved = 0
    for source, destination in plan_moves(photos):
        try:
            _run_rclone(['moveto', f'{remote}/{source}', f'{remote}/{destination}'])
            logger.info("Moved %s to %s on Drive", source, destination)
            moved += 1
        except Exception as e:
            logger.error("Failed to move %s on Drive: %s", source, e)
    return moved
