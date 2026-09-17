"""Tests for the home-screen install metadata.

The library is added to a phone home screen rather than installed from an
app store, so the manifest and its icons have to be served, reachable
without the PIN, and consistent with each other.
"""

import json
from pathlib import Path

import pytest

import photovault.main as main


REMOTE = {'REMOTE_ADDR': '192.168.1.50'}
STATIC_DIR = Path(main.__file__).parent / 'static'


@pytest.fixture
def client():
    main.app.config['TESTING'] = True
    with main.app.test_client() as test_client:
        yield test_client


def test_manifest_is_served_as_json(client):
    response = client.get('/manifest.webmanifest', environ_overrides=REMOTE)
    assert response.status_code == 200
    assert response.mimetype == 'application/manifest+json'


def test_manifest_opens_the_library_not_the_frame(client):
    manifest = client.get('/manifest.webmanifest').get_json()
    assert manifest['name'] == 'PhotoVault'
    assert manifest['display'] == 'standalone'
    assert manifest['start_url'] == '/manage'
    assert manifest['theme_color'] == '#12131a'


def test_every_declared_icon_is_reachable(client):
    manifest = client.get('/manifest.webmanifest').get_json()
    assert manifest['icons']
    for icon in manifest['icons']:
        response = client.get(icon['src'], environ_overrides=REMOTE)
        assert response.status_code == 200, icon['src']
        assert response.mimetype == 'image/png'


def test_manifest_lists_a_maskable_icon(client):
    manifest = client.get('/manifest.webmanifest').get_json()
    purposes = {icon.get('purpose') for icon in manifest['icons']}
    assert 'maskable' in purposes


def test_manifest_covers_both_install_sizes():
    icons = json.loads((STATIC_DIR / 'manifest.webmanifest').read_text())['icons']
    assert {'192x192', '512x512'} <= {icon['sizes'] for icon in icons}


def test_install_metadata_stays_outside_the_pin_gate(client, monkeypatch):
    monkeypatch.setenv('PHOTOVAULT_PIN', '1234')
    for path in ('/manifest.webmanifest', '/static/icons/apple-touch-icon.png'):
        response = client.get(path, environ_overrides=REMOTE)
        assert response.status_code == 200, path


def test_sign_in_page_uses_the_logo_as_its_favicon(client, monkeypatch):
    monkeypatch.setenv('PHOTOVAULT_PIN', '1234')
    page = client.get('/manage', environ_overrides=REMOTE).get_data(as_text=True)
    assert ('<link rel="icon" href="/static/icons/logo.svg" type="image/svg+xml">') in page
    response = client.get('/static/icons/logo.svg', environ_overrides=REMOTE)
    assert response.status_code == 200
    assert response.mimetype == 'image/svg+xml'


def test_sign_in_page_links_the_manifest_and_a_png_touch_icon(client, monkeypatch):
    monkeypatch.setenv('PHOTOVAULT_PIN', '1234')
    page = client.get('/manage', environ_overrides=REMOTE).get_data(as_text=True)
    assert '<link rel="manifest" href="/manifest.webmanifest">' in page
    assert ('<link rel="apple-touch-icon" '
            'href="/static/icons/apple-touch-icon.png">') in page
    assert ('<meta name="apple-mobile-web-app-status-bar-style" '
            'content="black-translucent">') in page
