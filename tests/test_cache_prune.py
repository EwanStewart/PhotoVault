"""Derived caches should not outlive the photos they came from.

A location rename moves a photo to a new path, so its cached JPEG,
preview and transcode are left behind under the old one. Deletions
leave the same litter. On a Pi that fills its SD card, this matters.
"""

import photovault.main as main


def _dirs(monkeypatch, tmp_path):
    photos = tmp_path / 'photos'
    heic = tmp_path / 'heic'
    thumb = tmp_path / 'thumb'
    video = tmp_path / 'video'
    for path in (photos, heic, thumb, video):
        path.mkdir()
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(photos))
    monkeypatch.setattr(main, 'HEIC_CACHE_DIR', str(heic))
    monkeypatch.setattr(main, 'THUMB_CACHE_DIR', str(thumb))
    monkeypatch.setattr(main, 'VIDEO_CACHE_DIR', str(video))
    return photos, heic, thumb, video


def test_cache_for_a_photo_that_moved_away_is_pruned(monkeypatch, tmp_path):
    photos, heic, thumb, video = _dirs(monkeypatch, tmp_path)
    (photos / 'Gouvia, Greece').mkdir()
    (photos / 'Gouvia, Greece' / 'a.heic').write_bytes(b'photo')
    (photos / 'Gouvia, Greece' / 'a.mov').write_bytes(b'clip')
    # Caches still sitting under the old Greek folder name
    stale_dir = heic / 'Γουβιά, Greece'
    stale_dir.mkdir()
    (stale_dir / 'a.jpg').write_bytes(b'stale')
    (thumb / 'gone.jpg').write_bytes(b'stale')
    (video / 'gone.mp4').write_bytes(b'stale')
    # Caches for the photo at its current path
    live_dir = heic / 'Gouvia, Greece'
    live_dir.mkdir()
    (live_dir / 'a.jpg').write_bytes(b'live')
    live_video = video / 'Gouvia, Greece'
    live_video.mkdir()
    (live_video / 'a.mp4').write_bytes(b'live')

    removed = main._prune_orphaned_cache()

    assert removed == 3
    assert (live_dir / 'a.jpg').exists()
    assert (live_video / 'a.mp4').exists()
    assert not (stale_dir / 'a.jpg').exists()
    assert not (thumb / 'gone.jpg').exists()
    assert not (video / 'gone.mp4').exists()


def test_pruning_clears_the_folders_it_empties(monkeypatch, tmp_path):
    photos, heic, _, _ = _dirs(monkeypatch, tmp_path)
    (photos / 'keep.jpg').write_bytes(b'photo')
    stale_dir = heic / 'Old, Greece'
    stale_dir.mkdir()
    (stale_dir / 'a.jpg').write_bytes(b'stale')

    main._prune_orphaned_cache()

    assert not stale_dir.exists()
    assert heic.exists()


def test_pruning_stops_when_the_photo_directory_looks_empty(monkeypatch, tmp_path):
    """A failed sync must not wipe every cache the frame depends on."""
    _, heic, _, _ = _dirs(monkeypatch, tmp_path)
    (heic / 'a.jpg').write_bytes(b'precious')

    removed = main._prune_orphaned_cache()

    assert removed == 0
    assert (heic / 'a.jpg').exists()
