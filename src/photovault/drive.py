"""Run the rclone commands that read and write the Google Drive remote.

Uploads land on Drive first and deletions go to Drive first, because the
sync watcher mirrors the remote onto the Pi. Writing locally first would
let the next sync undo the change.
"""

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

RCLONE_TIMEOUT_SECONDS = 120


def run_rclone(args):
    """Run one rclone command, raising with rclone's own error on failure.

    @param args Arguments to pass after the rclone executable
    """
    completed = subprocess.run(['rclone'] + args, capture_output=True, text=True,
                               timeout=RCLONE_TIMEOUT_SECONDS)
    if completed.returncode != 0:
        stderr = (completed.stderr or '').strip()
        detail = stderr.splitlines()[-1] if stderr else f'exit status {completed.returncode}'
        raise RuntimeError(detail)


def upload(remote, local_path, destination, run=run_rclone):
    """Copy one local file to a path on the remote.

    @param remote The rclone remote root, such as gdrive:PhotoFrame
    @param local_path Path of the file to copy
    @param destination Remote-relative destination path
    @param run Command runner, injectable for tests
    """
    run(['copyto', local_path, f'{remote}/{destination}'])


def delete(remote, path, run=run_rclone):
    """Delete one file from the remote.

    @param remote The rclone remote root, such as gdrive:PhotoFrame
    @param path Remote-relative path of the file to delete
    @param run Command runner, injectable for tests
    """
    run(['deletefile', f'{remote}/{path}'])


def remove_empty_dir(remote, path, run=run_rclone):
    """Tidy away a remote folder left empty by a deletion.

    rclone refuses to remove a folder that still holds files, so a
    failure here means the folder is still in use and is not an error.

    @param remote The rclone remote root, such as gdrive:PhotoFrame
    @param path Remote-relative folder path
    @param run Command runner, injectable for tests
    """
    if path and path not in ('.', '/'):
        try:
            run(['rmdir', f'{remote}/{path}'])
        except Exception as e:
            logger.debug("Left %s in place on the remote: %s", path, e)


def parent_folder(path):
    """Remote-relative folder holding a file, or an empty string at the root.

    @param path Remote-relative file path
    @returns The parent folder path, empty when the file sits at the root
    """
    return os.path.dirname(path)
