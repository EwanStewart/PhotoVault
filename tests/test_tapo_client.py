import asyncio

from photovault.tapo_client import TapoBulbClient


class SlowReconnectBulb:
    """Stub bulb whose reconnect outlasts the default async timeout."""

    def __init__(self):
        self.bulb_id = '1'
        self.last_error = None

    async def reconnect_with_backoff(self):
        await asyncio.sleep(0.3)
        return True


def test_reconnect_outlasts_default_async_timeout(monkeypatch):
    monkeypatch.setattr(TapoBulbClient, '_async_timeout_seconds', 0.1)
    client = TapoBulbClient()
    client._bulbs = {'1': SlowReconnectBulb()}

    result = client.reconnect_bulb('1')

    assert result['success'] is True


def test_reconnect_unknown_bulb_returns_error():
    client = TapoBulbClient()
    client._bulbs = {}

    result = client.reconnect_bulb('99')

    assert result['success'] is False
    assert 'not found' in result['error']
