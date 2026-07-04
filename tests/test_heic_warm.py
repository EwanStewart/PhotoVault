import threading

import photovault.main as main


def _use_tmp_dirs(monkeypatch, tmp_path):
    photos_dir = tmp_path / 'photos'
    cache_dir = tmp_path / 'cache'
    photos_dir.mkdir()
    cache_dir.mkdir()
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(photos_dir))
    monkeypatch.setattr(main, 'HEIC_CACHE_DIR', str(cache_dir))
    return photos_dir, cache_dir


def test_warm_single_heic_converts_when_cache_is_stale(monkeypatch, tmp_path):
    photos_dir, _ = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'a.heic').write_bytes(b'heic')
    converted = []
    monkeypatch.setattr(main, '_convert_heic', lambda src, dst: converted.append(dst))

    main._warm_single_heic('a.heic')

    assert len(converted) == 1
    assert converted[0].endswith('a.jpg')


def test_warm_single_heic_skips_fresh_cache(monkeypatch, tmp_path):
    photos_dir, cache_dir = _use_tmp_dirs(monkeypatch, tmp_path)
    source = photos_dir / 'a.heic'
    source.write_bytes(b'heic')
    cache = cache_dir / 'a.jpg'
    cache.write_bytes(b'jpeg')
    cache.touch()
    converted = []
    monkeypatch.setattr(main, '_convert_heic', lambda src, dst: converted.append(dst))

    main._warm_single_heic('a.heic')

    assert converted == []


def test_warm_single_heic_swallows_conversion_errors(monkeypatch, tmp_path):
    photos_dir, _ = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'a.heic').write_bytes(b'heic')

    def broken(src, dst):
        raise OSError('disk full')

    monkeypatch.setattr(main, '_convert_heic', broken)

    main._warm_single_heic('a.heic')


def test_warm_heic_cache_only_touches_heic_files(monkeypatch, tmp_path):
    photos_dir, _ = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'a.heic').write_bytes(b'heic')
    (photos_dir / 'b.jpg').write_bytes(b'jpeg')
    monkeypatch.setattr(main, '_start_enrich_thread_if_idle', lambda: None)
    monkeypatch.setattr(main, '_photo_cache', [])
    monkeypatch.setattr(main, '_photo_cache_fileset', set())
    warmed = []
    monkeypatch.setattr(main, '_warm_single_heic', lambda name: warmed.append(name))

    main._warm_heic_cache()

    assert warmed == ['a.heic']


def test_warm_cache_endpoint_reports_started_then_already_running(monkeypatch):
    release = threading.Event()
    running = threading.Event()

    def slow_warm():
        running.set()
        release.wait(timeout=5)

    monkeypatch.setattr(main, '_warm_heic_cache', slow_warm)
    monkeypatch.setattr(main, '_heic_warm_thread', None)
    client = main.app.test_client()

    first = client.post('/api/photos/warm-cache')
    assert first.get_json()['status'] == 'started'
    assert running.wait(timeout=5)

    second = client.post('/api/photos/warm-cache')
    assert second.get_json()['status'] == 'already_running'

    release.set()
