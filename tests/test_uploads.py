import pytest

import photovault.uploads as uploads


class FakeFile:
    """Stand-in for a Werkzeug FileStorage."""

    def __init__(self, filename, content=b'data'):
        self.filename = filename
        self.content = content
        self.saved_to = None

    def save(self, path):
        self.saved_to = path
        with open(path, 'wb') as handle:
            handle.write(self.content)


def test_plans_a_plain_photo_name():
    names = uploads.plan_names('IMG_1234.HEIC', None, set())

    assert names == ('IMG_1234.HEIC', None)


def test_strips_any_directory_part_from_the_uploaded_name():
    names = uploads.plan_names('../../etc/IMG_1.heic', None, set())

    assert names == ('IMG_1.heic', None)


def test_renames_the_clip_after_the_still_so_pairing_is_deterministic():
    names = uploads.plan_names('IMG_1234.HEIC', 'video_export.MOV', set())

    assert names == ('IMG_1234.HEIC', 'IMG_1234.MOV')


def test_suffixes_a_name_that_is_already_taken():
    names = uploads.plan_names('a.heic', 'a.mov', {'a.heic', 'a-1.heic'})

    assert names == ('a-2.heic', 'a-2.mov')


def test_a_clip_avoids_a_stem_whose_video_half_is_taken():
    names = uploads.plan_names('a.heic', 'a.mov', {'a.mov'})

    assert names == ('a-1.heic', 'a-1.mov')


def test_rejects_a_photo_with_an_unsupported_extension():
    with pytest.raises(uploads.RejectedUpload):
        uploads.plan_names('payload.php', None, set())


def test_rejects_a_clip_that_is_not_a_video():
    with pytest.raises(uploads.RejectedUpload):
        uploads.plan_names('a.heic', 'a.txt', set())


def test_rejects_an_empty_photo_name():
    with pytest.raises(uploads.RejectedUpload):
        uploads.plan_names('', None, set())


def test_sanitises_awkward_characters_but_keeps_the_extension():
    names = uploads.plan_names('my photo (1)!.jpg', None, set())

    assert names == ('my_photo_1.jpg', None)


def test_existing_basenames_ignores_folders(tmp_path):
    (tmp_path / 'Angus').mkdir()
    (tmp_path / 'Angus' / 'a.heic').write_bytes(b'x')
    (tmp_path / 'b.jpg').write_bytes(b'x')

    assert uploads.existing_basenames(str(tmp_path)) == {'a.heic', 'b.jpg'}


def test_save_pushes_to_drive_before_placing_the_file_locally(tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()
    order = []

    def fake_upload(remote, local_path, destination):
        order.append(('drive', destination))

    stored = uploads.save(
        str(photos_dir), 'gdrive:PhotoFrame',
        FakeFile('IMG_1.HEIC'), FakeFile('clip.MOV'),
        upload=fake_upload,
    )

    assert order == [('drive', 'IMG_1.HEIC'), ('drive', 'IMG_1.MOV')]
    assert stored == {'photo': 'IMG_1.HEIC', 'video': 'IMG_1.MOV'}
    assert (photos_dir / 'IMG_1.HEIC').exists()
    assert (photos_dir / 'IMG_1.MOV').exists()


def test_save_leaves_nothing_local_when_the_drive_push_fails(tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()

    def failing_upload(remote, local_path, destination):
        raise RuntimeError('no network')

    with pytest.raises(RuntimeError):
        uploads.save(
            str(photos_dir), 'gdrive:PhotoFrame',
            FakeFile('IMG_1.HEIC'), None,
            upload=failing_upload,
        )

    assert uploads.existing_basenames(str(photos_dir)) == set()
    staging = photos_dir / uploads.STAGING_DIR_NAME
    assert list(staging.iterdir()) == []


def test_a_clip_can_be_stored_on_its_own_for_capture_time_pairing(tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()
    pushed = []

    stored = uploads.save_clip(
        str(photos_dir), 'gdrive:PhotoFrame', FakeFile('IMG_5.MOV'),
        upload=lambda remote, local, dest: pushed.append(dest),
    )

    assert stored == {'photo': None, 'video': 'IMG_5.MOV'}
    assert pushed == ['IMG_5.MOV']
    assert (photos_dir / 'IMG_5.MOV').exists()


def test_a_lone_clip_avoids_a_name_already_taken(tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()
    (photos_dir / 'IMG_5.MOV').write_bytes(b'old')

    stored = uploads.save_clip(
        str(photos_dir), 'gdrive:PhotoFrame', FakeFile('IMG_5.MOV'),
        upload=lambda remote, local, dest: None,
    )

    assert stored['video'] == 'IMG_5-1.MOV'


def test_a_lone_file_that_is_not_a_clip_is_rejected(tmp_path):
    photos_dir = tmp_path / 'photos'
    photos_dir.mkdir()

    with pytest.raises(uploads.RejectedUpload):
        uploads.save_clip(str(photos_dir), 'gdrive:PhotoFrame', FakeFile('a.jpg'),
                          upload=lambda remote, local, dest: None)
