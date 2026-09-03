import photovault.auth as auth


def test_local_requests_bypass_the_pin():
    assert auth.is_authorised('127.0.0.1', {}, None, 'secret')
    assert auth.is_authorised('::1', {}, None, 'secret')


def test_remote_request_without_a_configured_pin_is_refused():
    assert not auth.is_authorised('192.168.1.20', {}, '1234', None)
    assert not auth.is_authorised('192.168.1.20', {}, '1234', '')


def test_remote_request_with_the_right_header_pin_is_allowed():
    assert auth.is_authorised('192.168.1.20', {}, '1234', '1234')


def test_remote_request_with_the_wrong_header_pin_is_refused():
    assert not auth.is_authorised('192.168.1.20', {}, '9999', '1234')
    assert not auth.is_authorised('192.168.1.20', {}, None, '1234')


def test_a_signed_in_session_is_allowed():
    session = {auth.SESSION_KEY: True}

    assert auth.is_authorised('192.168.1.20', session, None, '1234')


def test_a_session_flag_alone_does_not_help_when_no_pin_is_configured():
    session = {auth.SESSION_KEY: True}

    assert not auth.is_authorised('192.168.1.20', session, None, None)


def test_gate_applies_to_writes_and_manage_paths_only():
    assert auth.path_needs_pin('/api/upload', 'POST')
    assert auth.path_needs_pin('/manage', 'GET')
    assert auth.path_needs_pin('/api/manage/photos', 'GET')
    assert auth.path_needs_pin('/api/brightness', 'POST')
    assert not auth.path_needs_pin('/', 'GET')
    assert not auth.path_needs_pin('/photos', 'GET')
    assert not auth.path_needs_pin('/api/brightness', 'GET')


def test_login_and_spotify_callback_are_never_gated():
    assert not auth.path_needs_pin('/api/manage/login', 'POST')
    assert not auth.path_needs_pin('/callback', 'GET')
    assert not auth.path_needs_pin('/auth/spotify', 'GET')


def test_gate_allows_anything_that_is_not_behind_the_pin():
    assert auth.gate_decision('/photos', 'GET', '192.168.1.20', {}, None, None) == auth.ALLOW


def test_gate_allows_the_kiosk_on_the_loopback_address():
    assert auth.gate_decision('/api/upload', 'POST', '127.0.0.1', {}, None, None) == auth.ALLOW


def test_gate_offers_the_sign_in_form_for_the_manage_page():
    decision = auth.gate_decision('/manage', 'GET', '192.168.1.20', {}, None, '1234')

    assert decision == auth.LOGIN


def test_gate_refuses_the_manage_page_when_no_pin_exists_to_sign_in_with():
    decision = auth.gate_decision('/manage', 'GET', '192.168.1.20', {}, None, None)

    assert decision == auth.REFUSE


def test_gate_refuses_gated_data_without_a_session():
    decision = auth.gate_decision('/api/manage/photos', 'GET', '192.168.1.20', {}, None, '1234')

    assert decision == auth.REFUSE
