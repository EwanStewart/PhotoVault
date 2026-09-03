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


def test_a_heic_preview_builds_from_the_converted_jpeg_when_one_is_cached(monkeypatch, tmp_path):
    photos_dir = tmp_path / 'photos'
    heic_cache = tmp_path / 'heic'
    photos_dir.mkdir()
    heic_cache.mkdir()
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(photos_dir))
    monkeypatch.setattr(main, 'HEIC_CACHE_DIR', str(heic_cache))
    (photos_dir / 'a.heic').write_bytes(b'original heic')
    _write_photo(heic_cache / 'a.jpg')

    assert main._thumbnail_source('a.heic') == str(heic_cache / 'a.jpg')


def test_a_heic_preview_falls_back_to_the_original_when_no_jpeg_is_cached(monkeypatch, tmp_path):
    photos_dir = tmp_path / 'photos'
    heic_cache = tmp_path / 'heic'
    photos_dir.mkdir()
    heic_cache.mkdir()
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(photos_dir))
    monkeypatch.setattr(main, 'HEIC_CACHE_DIR', str(heic_cache))
    (photos_dir / 'a.heic').write_bytes(b'original heic')

    assert main._thumbnail_source('a.heic') == str(photos_dir / 'a.heic')


def test_a_jpeg_preview_builds_from_the_original(monkeypatch, tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()
    monkeypatch.setattr(main, 'PHOTOS_DIR', str(photos_dir))
    _write_photo(photos_dir / 'a.jpg')

    assert main._thumbnail_source('a.jpg') == str(photos_dir / 'a.jpg')


def _write_rotated_photo(path, orientation, size=(900, 600)):
    """Save a landscape photo whose EXIF asks the viewer to rotate it."""
    img = Image.new('RGB', size, 'white')
    img.paste(Image.new('RGB', (120, 120), 'red'), (0, 0))
    exif = img.getexif()
    exif[274] = orientation
    img.save(path, 'JPEG', exif=exif)


def test_a_sideways_photo_yields_an_upright_preview(client):
    _write_rotated_photo(client.photos_dir / 'sideways.jpg', 6)

    client.get('/photos/thumb/sideways.jpg')

    with Image.open(main._thumb_cache_path('sideways.jpg')) as thumb:
        assert thumb.height > thumb.width


def test_an_upside_down_photo_is_turned_the_right_way_up(client):
    _write_rotated_photo(client.photos_dir / 'flipped.jpg', 3)

    client.get('/photos/thumb/flipped.jpg')

    with Image.open(main._thumb_cache_path('flipped.jpg')) as thumb:
        corner = thumb.convert('RGB').getpixel((thumb.width - 4, thumb.height - 4))
        assert corner[0] > 150 and corner[1] < 110
