import pytest

import photovault.drive as drive


def _record(calls):
    def runner(args):
        calls.append(args)
    return runner


def test_upload_copies_one_file_to_the_remote_path():
    calls = []

    drive.upload('gdrive:PhotoFrame', '/tmp/a.heic', 'a.heic', run=_record(calls))

    assert calls == [['copyto', '/tmp/a.heic', 'gdrive:PhotoFrame/a.heic']]


def test_delete_removes_one_file_from_the_remote():
    calls = []

    drive.delete('gdrive:PhotoFrame', 'Angus/a/a.heic', run=_record(calls))

    assert calls == [['deletefile', 'gdrive:PhotoFrame/Angus/a/a.heic']]


def test_remove_empty_dir_ignores_a_directory_that_is_not_empty():
    def failing(args):
        raise RuntimeError('directory not empty')

    drive.remove_empty_dir('gdrive:PhotoFrame', 'Angus/a', run=failing)


def test_remove_empty_dir_does_nothing_at_the_remote_root():
    calls = []

    drive.remove_empty_dir('gdrive:PhotoFrame', '', run=_record(calls))
    drive.remove_empty_dir('gdrive:PhotoFrame', '.', run=_record(calls))

    assert calls == []


def test_run_raises_with_rclone_own_error(monkeypatch):
    class Completed:
        returncode = 1
        stderr = 'trouble\ndirectory not found\n'

    monkeypatch.setattr(drive.subprocess, 'run', lambda *a, **k: Completed())

    with pytest.raises(RuntimeError, match='directory not found'):
        drive.run_rclone(['deletefile', 'gdrive:PhotoFrame/a.heic'])


def test_remove_empty_dirs_sweeps_the_whole_remote_but_keeps_the_root():
    calls = []

    drive.remove_empty_dirs('gdrive:PhotoFrame', run=_record(calls))

    assert calls == [['rmdirs', '--leave-root', 'gdrive:PhotoFrame']]


def test_remove_empty_dirs_tolerates_a_failure():
    def failing(args):
        raise RuntimeError('rate limited')

    drive.remove_empty_dirs('gdrive:PhotoFrame', run=failing)
