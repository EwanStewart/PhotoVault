"""Place names should come back in English, not the local language.

Nominatim answers in the local language unless asked otherwise, which
put Greek, Czech and Gaelic names on the frame.
"""

import json

import photovault.main as main


def test_the_nominatim_request_asks_for_english():
    url = main.nominatim_url(39.6758, 19.8371)

    assert 'accept-language=en' in url
    assert 'lat=39.6758' in url
    assert 'lon=19.8371' in url


def test_a_cache_written_before_english_was_asked_for_is_discarded(monkeypatch, tmp_path):
    path = tmp_path / 'geocode_cache.json'
    path.write_text(json.dumps({'39.6758,19.8371': {'text': 'Γουβιά, Greece'}}))
    monkeypatch.setattr(main, 'GEOCODE_CACHE_FILE', str(path))
    monkeypatch.setattr(main, '_geocode_cache', {})

    main.load_geocode_cache_from_disk()

    assert main._geocode_cache == {}


def test_a_cache_written_in_english_is_kept(monkeypatch, tmp_path):
    path = tmp_path / 'geocode_cache.json'
    entries = {'50.0815,14.4125': {'text': 'Prague, Czechia', 'country_code': 'cz'}}
    path.write_text(json.dumps({'version': main.GEOCODE_CACHE_VERSION, 'entries': entries}))
    monkeypatch.setattr(main, 'GEOCODE_CACHE_FILE', str(path))
    monkeypatch.setattr(main, '_geocode_cache', {})

    main.load_geocode_cache_from_disk()

    assert main._geocode_cache == entries


def test_the_cache_round_trips_with_its_version(monkeypatch, tmp_path):
    path = tmp_path / 'geocode_cache.json'
    monkeypatch.setattr(main, 'GEOCODE_CACHE_FILE', str(path))
    monkeypatch.setattr(main, '_geocode_cache', {'1,2': {'text': 'Corfu, Greece'}})

    main.save_geocode_cache_to_disk()
    monkeypatch.setattr(main, '_geocode_cache', {})
    main.load_geocode_cache_from_disk()

    assert main._geocode_cache == {'1,2': {'text': 'Corfu, Greece'}}
    assert json.loads(path.read_text())['version'] == main.GEOCODE_CACHE_VERSION


def test_a_corrupt_cache_file_leaves_no_entries(monkeypatch, tmp_path):
    path = tmp_path / 'geocode_cache.json'
    path.write_text('{not json')
    monkeypatch.setattr(main, 'GEOCODE_CACHE_FILE', str(path))
    monkeypatch.setattr(main, '_geocode_cache', {})

    main.load_geocode_cache_from_disk()

    assert main._geocode_cache == {}
