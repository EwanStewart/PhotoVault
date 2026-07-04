from datetime import datetime

import photovault.live_photos as live_photos
import photovault.main as main


def entry(source_file, content_id=None, taken=None, creation=None):
    data = {'SourceFile': source_file}
    if content_id:
        data['ContentIdentifier'] = content_id
    if taken:
        data['DateTimeOriginal'] = taken
    if creation:
        data['CreationDate'] = creation
    return data


def test_pairs_by_content_identifier():
    entries = [
        entry('/p/a.heic', content_id='UUID-1', taken='2026:07:04 13:09:18'),
        entry('/p/clip.mov', content_id='UUID-1', creation='2026:07:04 20:00:00+01:00'),
    ]

    pairs = live_photos._build_pairs(entries, '/p')

    assert pairs == {'a.heic': 'clip.mov'}


def test_pairs_by_capture_time_within_tolerance():
    entries = [
        entry('/p/a.heic', taken='2026:07:04 13:09:18'),
        entry('/p/clip.mov', creation='2026:07:04 13:09:16+01:00'),
    ]

    pairs = live_photos._build_pairs(entries, '/p')

    assert pairs == {'a.heic': 'clip.mov'}


def test_no_pair_outside_tolerance():
    entries = [
        entry('/p/a.heic', taken='2026:07:04 13:09:18'),
        entry('/p/clip.mov', creation='2026:07:04 13:10:18+01:00'),
    ]

    pairs = live_photos._build_pairs(entries, '/p')

    assert pairs == {}


def test_video_pairs_with_nearest_photo_only():
    entries = [
        entry('/p/near.heic', taken='2026:07:04 13:09:18'),
        entry('/p/far.heic', taken='2026:07:04 13:09:25'),
        entry('/p/clip.mov', creation='2026:07:04 13:09:18'),
    ]

    pairs = live_photos._build_pairs(entries, '/p')

    assert pairs == {'near.heic': 'clip.mov'}


def test_content_identifier_beats_capture_time():
    entries = [
        entry('/p/a.heic', content_id='UUID-1', taken='2026:07:04 13:09:18'),
        entry('/p/b.heic', taken='2026:07:04 13:09:18'),
        entry('/p/clip.mov', content_id='UUID-1', creation='2026:07:04 13:09:18'),
    ]

    pairs = live_photos._build_pairs(entries, '/p')

    assert pairs == {'a.heic': 'clip.mov'}


def test_parse_timestamp_ignores_timezone_suffix():
    parsed = live_photos._parse_timestamp('2026:07:04 13:09:18+01:00')

    assert parsed == datetime(2026, 7, 4, 13, 9, 18)


def test_find_paired_video_skips_scan_when_no_videos(monkeypatch, tmp_path):
    (tmp_path / 'a.heic').write_bytes(b'heic')
    scans = []
    monkeypatch.setattr(live_photos, '_scan_metadata', lambda d: scans.append(d) or [])
    monkeypatch.setattr(live_photos, '_cache', {'signature': None, 'pairs': {}})

    assert live_photos.find_paired_video(str(tmp_path), 'a.heic') is None
    assert scans == []


def test_find_paired_video_scans_once_per_directory_state(monkeypatch, tmp_path):
    (tmp_path / 'a.heic').write_bytes(b'heic')
    (tmp_path / 'clip.mov').write_bytes(b'mov')
    scans = []

    def fake_scan(photos_dir):
        scans.append(photos_dir)
        return [
            entry(str(tmp_path / 'a.heic'), taken='2026:07:04 13:09:18'),
            entry(str(tmp_path / 'clip.mov'), creation='2026:07:04 13:09:18'),
        ]

    monkeypatch.setattr(live_photos, '_scan_metadata', fake_scan)
    monkeypatch.setattr(live_photos, '_cache', {'signature': None, 'pairs': {}})

    assert live_photos.find_paired_video(str(tmp_path), 'a.heic') == 'clip.mov'
    assert live_photos.find_paired_video(str(tmp_path), 'a.heic') == 'clip.mov'
    assert len(scans) == 1


def test_find_live_photo_video_falls_back_to_matcher(monkeypatch, tmp_path):
    photo = tmp_path / 'a.heic'
    photo.write_bytes(b'heic')
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(tmp_path))
    monkeypatch.setattr(
        main.live_photos, 'find_paired_video',
        lambda photos_dir, name: 'clip.mov' if name == 'a.heic' else None
    )

    assert main.find_live_photo_video(str(photo)) == 'clip.mov'


def test_basename_match_wins_over_matcher(monkeypatch, tmp_path):
    photo = tmp_path / 'a.heic'
    photo.write_bytes(b'heic')
    (tmp_path / 'a.mov').write_bytes(b'mov')
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(tmp_path))
    monkeypatch.setattr(
        main.live_photos, 'find_paired_video',
        lambda photos_dir, name: 'wrong.mov'
    )

    assert main.find_live_photo_video(str(photo)) == 'a.mov'


def test_new_video_triggers_re_enrichment(monkeypatch, tmp_path):
    (tmp_path / 'a.jpg').write_bytes(b'jpeg')
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(tmp_path))
    monkeypatch.setattr(main, '_start_enrich_thread_if_idle', lambda: None)
    monkeypatch.setattr(main, '_photo_cache', [])
    monkeypatch.setattr(main, '_photo_cache_fileset', set())
    monkeypatch.setattr(main, '_video_fileset', set())

    main.refresh_photo_cache()
    for photo in main._photo_cache:
        photo['_enriched'] = True

    (tmp_path / 'clip.mov').write_bytes(b'mov')
    main.refresh_photo_cache()

    assert all(not p['_enriched'] for p in main._photo_cache)
