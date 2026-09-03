import pytest
from PIL import Image

import photovault.main as main


@pytest.fixture
def client(monkeypatch, tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(photos_dir))
    monkeypatch.setattr(main, 'THUMB_CACHE_DIR', str(tmp_path / 'thumb'))
    main.app.config['TESTING'] = True
    with main.app.test_client() as test_client:
        test_client.photos_dir = photos_dir
        yield test_client


def _write_photo(path, size=(1200, 900)):
    Image.new('RGB', size, 'red').save(path, 'JPEG')


def test_thumbnail_is_built_and_shrunk(client):
    _write_photo(client.photos_dir / 'a.jpg')

    response = client.get('/photos/thumb/a.jpg')

    assert response.status_code == 200
    assert response.mimetype == 'image/jpeg'
    cached = main._thumb_cache_path('a.jpg')
    with Image.open(cached) as img:
        assert max(img.size) == main.THUMB_MAX_DIMENSION


def test_thumbnail_works_for_a_photo_in_a_location_folder(client):
    (client.photos_dir / 'Angus, Scotland').mkdir()
    _write_photo(client.photos_dir / 'Angus, Scotland' / 'b.jpg')

    response = client.get('/photos/thumb/Angus, Scotland/b.jpg')

    assert response.status_code == 200


def test_thumbnail_rejects_a_traversal_attempt(client):
    response = client.get('/photos/thumb/../../etc/passwd')

    assert response.status_code in (400, 404)


def test_a_missing_photo_does_not_yield_a_thumbnail(client):
    response = client.get('/photos/thumb/nope.jpg')

    assert response.status_code == 500
