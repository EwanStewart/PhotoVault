import photovault.photo_prefs as prefs


def test_photos_are_enabled_until_disabled():
    assert prefs.is_enabled({}, 'a.heic')
    assert prefs.is_enabled({'a.heic': {'enabled': True}}, 'a.heic')
    assert not prefs.is_enabled({'a.heic': {'enabled': False}}, 'a.heic')


def test_flags_key_on_the_basename_so_they_survive_the_organiser_move():
    stored = prefs.set_enabled({}, 'a.heic', False)

    assert not prefs.is_enabled(stored, 'Angus, Scotland/a/a.heic')


def test_forgetting_a_photo_drops_its_flag():
    stored = prefs.set_enabled({}, 'a.heic', False)

    prefs.forget(stored, 'Angus, Scotland/a/a.heic')

    assert prefs.is_enabled(stored, 'a.heic')


def test_filter_enabled_keeps_only_photos_left_on():
    stored = prefs.set_enabled({}, 'b.jpg', False)
    photos = [{'filename': 'a.jpg'}, {'filename': 'sub/b.jpg'}]

    kept = prefs.filter_enabled(stored, photos)

    assert [p['filename'] for p in kept] == ['a.jpg']


def test_flags_round_trip_through_disk(tmp_path):
    path = str(tmp_path / 'photo_prefs.json')
    stored = prefs.set_enabled({}, 'a.heic', False)

    prefs.save(path, stored)

    assert prefs.load(path) == {'a.heic': {'enabled': False}}


def test_loading_a_missing_or_corrupt_file_yields_no_flags(tmp_path):
    missing = str(tmp_path / 'nope.json')
    corrupt = tmp_path / 'bad.json'
    corrupt.write_text('{not json')

    assert prefs.load(missing) == {}
    assert prefs.load(str(corrupt)) == {}
