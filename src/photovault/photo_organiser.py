"""Move located photos into per-location folders on Google Drive.

Once enrichment reverse-geocodes a photo, the file still sits at the
root of the Drive folder. This module plans and runs server-side rclone
moves into a folder named after the location. The sync watcher then
mirrors the new layout locally.
"""

import logging
import subprocess

logger = logging.getLogger(__name__)

RCLONE_TIMEOUT_SECONDS = 60


def _folder_name(location):
    """Location string as a safe single folder name."""
    return location.replace('/', '-').replace('\\', '-').strip()


def plan_moves(photos):
    """List (source, destination) moves for located photos still at the root."""
    moves = []
    for photo in photos:
        location = photo.get('location')
        filename = photo.get('filename', '')
        if not location or '/' in filename:
            continue
        folder = _folder_name(location)
        moves.append((filename, f'{folder}/{filename}'))
        video = photo.get('videoFilename')
        if video and '/' not in video:
            moves.append((video, f'{folder}/{video}'))
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
