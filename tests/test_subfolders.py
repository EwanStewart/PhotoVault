import photovault.main as main


def _use_tmp_photos(monkeypatch, tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(photos_dir))
    monkeypatch.setattr(main, '_start_enrich_thread_if_idle', lambda: None)
    monkeypatch.setattr(main, '_photo_cache', [])
    monkeypatch.setattr(main, '_photo_cache_fileset', set())
    monkeypatch.setattr(main, '_video_fileset', set())
    return photos_dir


def test_validate_filename_accepts_location_subfolders():
    assert main.validate_filename('Angus, Scotland/a.heic')


def test_validate_filename_rejects_traversal_and_bad_paths():
    assert not main.validate_filename('../secrets.txt')
    assert not main.validate_filename('a/../b.jpg')
    assert not main.validate_filename('/etc/passwd')
    assert not main.validate_filename('a//b.jpg')
    assert not main.validate_filename('a\\b.jpg')
    assert not main.validate_filename('')


def test_photo_cache_finds_photos_in_subfolders(monkeypatch, tmp_path):
    photos_dir = _use_tmp_photos(monkeypatch, tmp_path)
    (photos_dir / 'Fife, Scotland').mkdir()
    (photos_dir / 'Fife, Scotland' / 'a.jpg').write_bytes(b'jpeg')
    (photos_dir / 'Fife, Scotland' / 'clip.mov').write_bytes(b'mov')
    (photos_dir / 'root.jpg').write_bytes(b'jpeg')

    main.refresh_photo_cache()

    names = {p['filename'] for p in main._photo_cache}
    assert names == {'Fife, Scotland/a.jpg', 'root.jpg'}
    assert main._video_fileset == {'Fife, Scotland/clip.mov'}


def test_serve_photo_from_subfolder(monkeypatch, tmp_path):
    photos_dir = _use_tmp_photos(monkeypatch, tmp_path)
    (photos_dir / 'Fife, Scotland').mkdir()
    (photos_dir / 'Fife, Scotland' / 'a.jpg').write_bytes(b'jpeg')
    client = main.app.test_client()

    response = client.get('/photos/Fife, Scotland/a.jpg')

    assert response.status_code == 200
    assert response.data == b'jpeg'


def test_enrichment_drain_organises_the_remote(monkeypatch, tmp_path):
    _use_tmp_photos(monkeypatch, tmp_path)
    monkeypatch.setattr(main, '_photo_cache', [
        {'filename': 'a.jpg', 'location': 'Angus, Scotland', '_enriched': True},
    ])
    calls = []

    def fake_organise(remote, photos):
        calls.append((remote, [p['filename'] for p in photos]))
        return 0

    monkeypatch.setattr(main.photo_organiser, 'organise', fake_organise)

    main._enrich_pending_photos()

    assert calls == [(main.PHOTO_REMOTE, ['a.jpg'])]
