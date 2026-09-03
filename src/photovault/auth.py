"""Gate the upload and manage endpoints behind a PIN.

The frame itself runs Chromium against localhost, so requests from the
loopback address pass straight through and the kiosk needs no PIN. Any
other address has to present the PIN from the environment, either as a
header on each request or once through the manage page's sign-in form.
With no PIN configured, nothing off the loopback address can write.
"""

import hmac
import os

PIN_ENV_VAR = 'PHOTOVAULT_PIN'
PIN_HEADER = 'X-PhotoVault-Pin'
SESSION_KEY = 'manage_authed'
LOCAL_ADDRESSES = {'127.0.0.1', '::1', 'localhost'}
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}
GATED_PREFIXES = ('/manage', '/api/manage', '/api/upload')
OPEN_PATHS = ('/api/manage/login', '/callback', '/auth/spotify')
SHELL_PATHS = ('/manage',)
ALLOW = 'allow'
LOGIN = 'login'
REFUSE = 'refuse'


def configured_pin():
    """The PIN from the environment, or None when none is set.

    @returns The configured PIN with surrounding whitespace removed, else None
    """
    value = (os.environ.get(PIN_ENV_VAR) or '').strip()
    return value or None


def is_local(remote_address):
    """True when a request came from the loopback address.

    @param remote_address The client address Flask reported
    @returns True for a loopback client
    """
    return remote_address in LOCAL_ADDRESSES


def pin_matches(supplied, configured):
    """Compare a supplied PIN against the configured one in constant time.

    @param supplied The PIN the client sent
    @param configured The PIN from the environment
    @returns True when both are present and equal
    """
    result = False
    if supplied and configured:
        result = hmac.compare_digest(str(supplied), str(configured))
    return result


def is_authorised(remote_address, session, header_pin, configured):
    """Decide whether one request may reach a gated endpoint.

    @param remote_address The client address Flask reported
    @param session The Flask session mapping for this client
    @param header_pin The PIN sent on this request, if any
    @param configured The PIN from the environment
    @returns True when the request may proceed
    """
    result = False
    if is_local(remote_address):
        result = True
    elif configured:
        result = bool(session.get(SESSION_KEY)) or pin_matches(header_pin, configured)
    return result


def path_needs_pin(path, method):
    """True when a request path and method fall behind the gate.

    Every write is gated, as is the whole manage surface, so putting the
    frame on the home network does not hand the neighbours the lights,
    the volume or the photo library.

    @param path The request path
    @param method The HTTP method
    @returns True when the request needs authorisation
    """
    result = False
    if path not in OPEN_PATHS:
        gated_area = path.startswith(GATED_PREFIXES)
        result = gated_area or method not in SAFE_METHODS
    return result


def gate_decision(path, method, remote_address, session, header_pin, configured):
    """Decide what to do with one request: serve it, ask for the PIN, or refuse.

    A browser asking for the manage page gets the sign-in form rather
    than a bare refusal, so long as a PIN exists to sign in with. The
    data behind that page stays gated either way.

    @param path The request path
    @param method The HTTP method
    @param remote_address The client address Flask reported
    @param session The Flask session mapping for this client
    @param header_pin The PIN sent on this request, if any
    @param configured The PIN from the environment
    @returns One of the ALLOW, LOGIN or REFUSE constants
    """
    decision = REFUSE
    if not path_needs_pin(path, method):
        decision = ALLOW
    elif is_authorised(remote_address, session, header_pin, configured):
        decision = ALLOW
    elif configured and path in SHELL_PATHS:
        decision = LOGIN
    return decision
