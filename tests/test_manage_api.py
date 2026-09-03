import io

import pytest

import photovault.auth as auth
import photovault.main as main


REMOTE = {'REMOTE_ADDR': '192.168.1.50'}


@pytest.fixture
def client(monkeypatch, tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(photos_dir))
    monkeypatch.setattr(main, 'PHOTO_PREFS_FILE', str(tmp_path / 'prefs.json'))
    monkeypatch.setattr(main, '_photo_prefs', {})
    monkeypatch.setattr(main, '_start_enrich_thread_if_idle', lambda: None)
    monkeypatch.setattr(main, '_photo_cache', [])
    monkeypatch.setattr(main, '_photo_cache_fileset', set())
    monkeypatch.setattr(main, '_video_fileset', set())
    main.app.config['TESTING'] = True
    with main.app.test_client() as test_client:
        test_client.photos_dir = photos_dir
        yield test_client


def _add_photo(client, name='a.jpg'):
    (client.photos_dir / name).write_bytes(b'jpeg')
    main.refresh_photo_cache()


def test_manage_page_is_refused_from_the_network_without_a_pin(client, monkeypatch):
    monkeypatch.delenv(auth.PIN_ENV_VAR, raising=False)

    response = client.get('/manage', environ_base=REMOTE)

    assert response.status_code == 401


def test_a_correct_pin_opens_a_session_for_the_manage_page(client, monkeypatch):
    monkeypatch.setenv(auth.PIN_ENV_VAR, '4321')

    denied = client.get('/api/manage/photos', environ_base=REMOTE)
    login = client.post('/api/manage/login', json={'pin': '4321'}, environ_base=REMOTE)
    allowed = client.get('/api/manage/photos', environ_base=REMOTE)

    assert denied.status_code == 401
    assert login.status_code == 200
    assert allowed.status_code == 200


def test_a_wrong_pin_is_refused(client, monkeypatch):
    monkeypatch.setenv(auth.PIN_ENV_VAR, '4321')

    response = client.post('/api/manage/login', json={'pin': '0000'}, environ_base=REMOTE)

    assert response.status_code == 401
    assert client.get('/api/manage/photos', environ_base=REMOTE).status_code == 401


def test_the_kiosk_on_localhost_needs_no_pin(client, monkeypatch):
    monkeypatch.setenv(auth.PIN_ENV_VAR, '4321')

    assert client.get('/api/manage/photos').status_code == 200


def test_hardware_writes_from_the_network_are_gated(client, monkeypatch):
    monkeypatch.delenv(auth.PIN_ENV_VAR, raising=False)

    response = client.post('/api/brightness', json={'value': 50}, environ_base=REMOTE)

    assert response.status_code == 401


def test_manage_listing_reports_the_enabled_flag(client):
    _add_photo(client, 'a.jpg')

    listing = client.get('/api/manage/photos').get_json()

    assert [p['filename'] for p in listing] == ['a.jpg']
    assert listing[0]['enabled'] is True


def test_disabling_a_photo_removes_it_from_the_slideshow_list(client):
    _add_photo(client, 'a.jpg')

    toggled = client.post('/api/manage/photos/a.jpg/enabled', json={'enabled': False})

    assert toggled.status_code == 200
    assert client.get('/photos').get_json() == []
    assert client.get('/api/manage/photos').get_json()[0]['enabled'] is False


def test_a_disabled_photo_can_be_switched_back_on(client):
    _add_photo(client, 'a.jpg')
    client.post('/api/manage/photos/a.jpg/enabled', json={'enabled': False})

    client.post('/api/manage/photos/a.jpg/enabled', json={'enabled': True})

    assert [p['filename'] for p in client.get('/photos').get_json()] == ['a.jpg']


def test_the_enabled_flag_persists_to_disk(client):
    _add_photo(client, 'a.jpg')

    client.post('/api/manage/photos/a.jpg/enabled', json={'enabled': False})

    import photovault.photo_prefs as photo_prefs
    assert photo_prefs.load(main.PHOTO_PREFS_FILE) == {'a.jpg': {'enabled': False}}


def test_deleting_a_photo_removes_both_halves_from_drive_and_disk(client, monkeypatch):
    _add_photo(client, 'a.heic')
    (client.photos_dir / 'a.mov').write_bytes(b'mov')
    monkeypatch.setattr(main, '_photo_cache', [{
        'filename': 'a.heic', 'modified': 1, 'size': 1,
        'isLivePhoto': True, 'videoFilename': 'a.mov', '_enriched': True,
    }])
    deleted = []
    monkeypatch.setattr(main.drive, 'delete',
                        lambda remote, path: deleted.append(path))
    monkeypatch.setattr(main.drive, 'remove_empty_dir', lambda remote, path: None)

    response = client.delete('/api/manage/photos/a.heic')

    assert response.status_code == 200
    assert deleted == ['a.heic', 'a.mov']
    assert not (client.photos_dir / 'a.heic').exists()
    assert not (client.photos_dir / 'a.mov').exists()


def test_a_failed_drive_delete_leaves_the_local_file_alone(client, monkeypatch):
    _add_photo(client, 'a.jpg')

    def failing(remote, path):
        raise RuntimeError('no network')

    monkeypatch.setattr(main.drive, 'delete', failing)

    response = client.delete('/api/manage/photos/a.jpg')

    assert response.status_code == 502
    assert (client.photos_dir / 'a.jpg').exists()


def test_upload_stores_the_still_and_its_clip(client, monkeypatch):
    pushed = []
    monkeypatch.setattr(main.drive, 'upload',
                        lambda remote, local, dest: pushed.append(dest))

    response = client.post('/api/upload', data={
        'photo': (io.BytesIO(b'heic'), 'IMG_9.HEIC'),
        'video': (io.BytesIO(b'mov'), 'IMG_9.MOV'),
    }, content_type='multipart/form-data')

    assert response.status_code == 201
    assert response.get_json() == {'photo': 'IMG_9.HEIC', 'video': 'IMG_9.MOV'}
    assert pushed == ['IMG_9.HEIC', 'IMG_9.MOV']
    assert (client.photos_dir / 'IMG_9.HEIC').exists()
    assert (client.photos_dir / 'IMG_9.MOV').exists()


def test_upload_rejects_a_file_that_is_not_a_photo(client):
    response = client.post('/api/upload', data={
        'photo': (io.BytesIO(b'x'), 'payload.php'),
    }, content_type='multipart/form-data')

    assert response.status_code == 400


def test_upload_needs_a_photo_part(client):
    response = client.post('/api/upload', data={}, content_type='multipart/form-data')

    assert response.status_code == 400


def test_upload_from_the_network_needs_the_pin_header(client, monkeypatch):
    monkeypatch.setenv(auth.PIN_ENV_VAR, '4321')
    monkeypatch.setattr(main.drive, 'upload', lambda remote, local, dest: None)
    data = {'photo': (io.BytesIO(b'jpeg'), 'IMG_2.jpg')}

    denied = client.post('/api/upload', data=dict(data),
                         content_type='multipart/form-data', environ_base=REMOTE)

    assert denied.status_code == 401


def test_upload_with_the_pin_header_is_accepted(client, monkeypatch):
    monkeypatch.setenv(auth.PIN_ENV_VAR, '4321')
    monkeypatch.setattr(main.drive, 'upload', lambda remote, local, dest: None)

    response = client.post(
        '/api/upload',
        data={'photo': (io.BytesIO(b'jpeg'), 'IMG_2.jpg')},
        content_type='multipart/form-data',
        headers={auth.PIN_HEADER: '4321'},
        environ_base=REMOTE,
    )

    assert response.status_code == 201


def test_the_manage_page_serves_the_sign_in_form_when_a_pin_is_set(client, monkeypatch):
    monkeypatch.setenv(auth.PIN_ENV_VAR, '4321')

    response = client.get('/manage', environ_base=REMOTE)

    assert response.status_code == 200
    assert b'pin' in response.data.lower()


def test_deleting_the_last_photo_in_a_folder_prunes_the_empty_folder(client, monkeypatch):
    folder = client.photos_dir / 'Angus, Scotland'
    folder.mkdir()
    (folder / 'a.jpg').write_bytes(b'jpeg')
    main.refresh_photo_cache()
    monkeypatch.setattr(main.drive, 'delete', lambda remote, path: None)
    monkeypatch.setattr(main.drive, 'remove_empty_dir', lambda remote, path: None)

    client.delete('/api/manage/photos/Angus, Scotland/a.jpg')

    assert not folder.exists()


def test_pruning_leaves_a_folder_that_still_holds_photos(client, monkeypatch):
    folder = client.photos_dir / 'Angus, Scotland'
    folder.mkdir()
    (folder / 'a.jpg').write_bytes(b'jpeg')
    (folder / 'b.jpg').write_bytes(b'jpeg')
    main.refresh_photo_cache()
    monkeypatch.setattr(main.drive, 'delete', lambda remote, path: None)
    monkeypatch.setattr(main.drive, 'remove_empty_dir', lambda remote, path: None)

    client.delete('/api/manage/photos/Angus, Scotland/a.jpg')

    assert (folder / 'b.jpg').exists()


def test_pruning_never_climbs_above_the_photos_directory(client, monkeypatch):
    _add_photo(client, 'a.jpg')
    monkeypatch.setattr(main.drive, 'delete', lambda remote, path: None)
    monkeypatch.setattr(main.drive, 'remove_empty_dir', lambda remote, path: None)

    client.delete('/api/manage/photos/a.jpg')

    assert client.photos_dir.exists()
