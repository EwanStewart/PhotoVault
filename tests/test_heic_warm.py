import os
import threading
import time

import photovault.main as main


def test_cache_dirs_are_persistent_not_tmpfs():
    for cache_dir in (main.HEIC_CACHE_DIR, main.VIDEO_CACHE_DIR, main.FLAG_CACHE_DIR):
        assert not cache_dir.startswith('/tmp'), cache_dir
        assert cache_dir.startswith(main.CACHE_ROOT), cache_dir


def test_resolve_cache_root_honours_env(monkeypatch):
    monkeypatch.setenv('PHOTOVAULT_CACHE_DIR', '/mnt/persistent/cache')
    assert main._resolve_cache_root() == '/mnt/persistent/cache'


def test_resolve_cache_root_defaults_under_repo(monkeypatch):
    monkeypatch.delenv('PHOTOVAULT_CACHE_DIR', raising=False)
    assert main._resolve_cache_root() == str(main.REPO_ROOT / 'cache')


def _use_tmp_dirs(monkeypatch, tmp_path):
    photos_dir = tmp_path / 'photos'
    heic_cache = tmp_path / 'heic_cache'
    video_cache = tmp_path / 'video_cache'
    photos_dir.mkdir()
    heic_cache.mkdir()
    video_cache.mkdir()
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(photos_dir))
    monkeypatch.setattr(main, 'HEIC_CACHE_DIR', str(heic_cache))
    monkeypatch.setattr(main, 'VIDEO_CACHE_DIR', str(video_cache))
    return photos_dir, heic_cache, video_cache


def _reset_photo_cache(monkeypatch):
    monkeypatch.setattr(main, '_start_enrich_thread_if_idle', lambda: None)
    monkeypatch.setattr(main, '_photo_cache', [])
    monkeypatch.setattr(main, '_photo_cache_fileset', set())
    monkeypatch.setattr(main, '_video_fileset', set())


def test_warm_single_heic_converts_when_cache_is_stale(monkeypatch, tmp_path):
    photos_dir, _, _ = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'a.heic').write_bytes(b'heic')
    converted = []
    monkeypatch.setattr(main, '_convert_heic', lambda src, dst: converted.append(dst))

    main._warm_single_heic('a.heic')

    assert len(converted) == 1
    assert converted[0].endswith('a.jpg')


def test_warm_single_heic_skips_fresh_cache(monkeypatch, tmp_path):
    photos_dir, heic_cache, _ = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'a.heic').write_bytes(b'heic')
    (heic_cache / 'a.jpg').write_bytes(b'jpeg')
    converted = []
    monkeypatch.setattr(main, '_convert_heic', lambda src, dst: converted.append(dst))

    main._warm_single_heic('a.heic')

    assert converted == []


def test_warm_single_heic_swallows_conversion_errors(monkeypatch, tmp_path):
    photos_dir, _, _ = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'a.heic').write_bytes(b'heic')

    def broken(src, dst):
        raise OSError('disk full')

    monkeypatch.setattr(main, '_convert_heic', broken)

    main._warm_single_heic('a.heic')


def test_warm_single_video_transcodes_when_cache_is_stale(monkeypatch, tmp_path):
    photos_dir, _, _ = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'clip.mov').write_bytes(b'hevc')
    transcoded = []
    monkeypatch.setattr(main, '_transcode_video', lambda src, dst: transcoded.append(dst))

    main._warm_single_video('clip.mov')

    assert len(transcoded) == 1
    assert transcoded[0].endswith('clip.mp4')


def test_transcode_video_runs_one_at_a_time(monkeypatch, tmp_path):
    _, _, video_cache = _use_tmp_dirs(monkeypatch, tmp_path)
    active = {'now': 0, 'max': 0}
    counter_lock = threading.Lock()

    def fake_run(command, **kwargs):
        with counter_lock:
            active['now'] += 1
            active['max'] = max(active['max'], active['now'])
        time.sleep(0.05)
        with counter_lock:
            active['now'] -= 1
        open(command[-1], 'wb').close()
        return None

    monkeypatch.setattr(main.subprocess, 'run', fake_run)

    threads = [
        threading.Thread(
            target=main._transcode_video,
            args=(f'src{i}.mov', str(video_cache / f'out{i}.mp4')),
        )
        for i in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert active['max'] == 1


def test_warm_single_video_skips_fresh_cache(monkeypatch, tmp_path):
    photos_dir, _, video_cache = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'clip.mov').write_bytes(b'hevc')
    (video_cache / 'clip.mp4').write_bytes(b'h264')
    transcoded = []
    monkeypatch.setattr(main, '_transcode_video', lambda src, dst: transcoded.append(dst))

    main._warm_single_video('clip.mov')

    assert transcoded == []


def test_warm_media_cache_covers_heics_and_videos(monkeypatch, tmp_path):
    photos_dir, _, _ = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'a.heic').write_bytes(b'heic')
    (photos_dir / 'b.jpg').write_bytes(b'jpeg')
    (photos_dir / 'clip.mov').write_bytes(b'hevc')
    _reset_photo_cache(monkeypatch)
    warmed = []
    monkeypatch.setattr(main, '_warm_single_heic', lambda name: warmed.append(name))
    monkeypatch.setattr(main, '_warm_single_video', lambda name: warmed.append(name))

    main._warm_media_cache()

    assert warmed == ['a.heic', 'clip.mov']


def test_serve_video_prefers_transcoded_cache(monkeypatch, tmp_path):
    photos_dir, _, video_cache = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'clip.mov').write_bytes(b'hevc')
    (video_cache / 'clip.mp4').write_bytes(b'h264')
    client = main.app.test_client()

    response = client.get('/photos/video/clip.mov')

    assert response.status_code == 200
    assert response.data == b'h264'
    assert response.mimetype == 'video/mp4'


def test_serve_video_falls_back_to_original(monkeypatch, tmp_path):
    photos_dir, _, _ = _use_tmp_dirs(monkeypatch, tmp_path)
    (photos_dir / 'clip.mov').write_bytes(b'hevc')
    client = main.app.test_client()

    response = client.get('/photos/video/clip.mov')

    assert response.status_code == 200
    assert response.data == b'hevc'


def test_warm_cache_endpoint_reports_started_then_already_running(monkeypatch):
    release = threading.Event()
    running = threading.Event()

    def slow_warm():
        running.set()
        release.wait(timeout=5)

    monkeypatch.setattr(main, '_warm_media_cache', slow_warm)
    monkeypatch.setattr(main, '_heic_warm_thread', None)
    client = main.app.test_client()

    first = client.post('/api/photos/warm-cache')
    assert first.get_json()['status'] == 'started'
    assert running.wait(timeout=5)

    second = client.post('/api/photos/warm-cache')
    assert second.get_json()['status'] == 'already_running'

    release.set()
