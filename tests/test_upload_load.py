"""Guards on the work a burst of uploads is allowed to trigger.

Pairing runs one exiftool pass over the whole photos directory, which
takes tens of seconds on a Pi. Enriching each photo from its own scan,
and rescanning on every uploaded file, saturated the frame.
"""

import io

import pytest

import photovault.live_photos as live_photos
import photovault.main as main


@pytest.fixture
def photos(monkeypatch, tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(photos_dir))
    monkeypatch.setattr(main, 'PHOTO_PREFS_FILE', str(tmp_path / 'prefs.json'))
    monkeypatch.setattr(main, '_photo_prefs', {})
    monkeypatch.setattr(main, '_photo_cache', [])
    monkeypatch.setattr(main, '_photo_cache_fileset', set())
    monkeypatch.setattr(main, '_video_fileset', set())
    monkeypatch.setattr(main, '_pair_map_cache', {'pairs': {}, 'checked_at': 0.0})
    return photos_dir


def test_the_pair_map_is_reused_rather_than_rescanned_per_photo(monkeypatch, photos):
    scans = []
    monkeypatch.setattr(live_photos, 'pair_map',
                        lambda photos_dir: scans.append(photos_dir) or {'a.heic': 'a.mov'})

    for _ in range(20):
        main._current_pair_map()

    assert len(scans) == 1


def test_the_pair_map_refreshes_once_it_goes_stale(monkeypatch, photos):
    scans = []
    monkeypatch.setattr(live_photos, 'pair_map',
                        lambda photos_dir: scans.append(1) or {})
    clock = [1000.0]
    monkeypatch.setattr(main.time, 'monotonic', lambda: clock[0])

    main._current_pair_map()
    clock[0] += main.PAIR_MAP_MAX_AGE_SECONDS + 1
    main._current_pair_map()

    assert len(scans) == 2


def test_enrichment_uses_the_shared_pair_map_instead_of_its_own_scan(monkeypatch, photos):
    (photos / 'a.jpg').write_bytes(b'jpeg')
    calls = []
    monkeypatch.setattr(main, 'find_live_photo_video',
                        lambda path: calls.append(path))

    data = main.build_photo_data('a.jpg', pairs={'a.jpg': 'a.mov'})

    assert data['isLivePhoto'] is True
    assert data['videoFilename'] == 'a.mov'
    assert calls == []


def test_a_burst_of_uploads_schedules_one_refresh_not_one_each(monkeypatch, photos):
    scheduled = []
    monkeypatch.setattr(main, '_schedule_library_refresh',
                        lambda: scheduled.append(1))
    monkeypatch.setattr(main.drive, 'upload', lambda remote, local, dest: None)
    refreshes = []
    monkeypatch.setattr(main, 'refresh_photo_cache', lambda: refreshes.append(1))
    main.app.config['TESTING'] = True

    with main.app.test_client() as client:
        for i in range(5):
            client.post('/api/upload', data={
                'photo': (io.BytesIO(b'jpeg'), f'IMG_{i}.jpg'),
            }, content_type='multipart/form-data')

    assert len(scheduled) == 5
    assert refreshes == []


def test_the_refresh_debounce_collapses_a_burst_into_one_run(monkeypatch, photos):
    runs = []
    monkeypatch.setattr(main, '_refresh_after_uploads', lambda: runs.append(1))
    monkeypatch.setattr(main, 'UPLOAD_SETTLE_SECONDS', 0.05)
    monkeypatch.setattr(main, '_upload_settle_timer', None)

    for _ in range(6):
        main._schedule_library_refresh()
    main.time.sleep(0.3)

    assert len(runs) == 1
