"""
Tapo Smart Bulb Client

Provides a client for controlling Tapo smart bulbs via the python-kasa
library. Supports connection pooling, automatic reconnection with exponential
backoff, and bulk operations.
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any

from kasa import Discover, Credentials

logger = logging.getLogger(__name__)

# Colour presets with hue, saturation, and brightness values
COLOUR_PRESETS = {
    'warm_white': {'hue': 30, 'saturation': 50, 'brightness': 100},
    'cool_white': {'hue': 220, 'saturation': 20, 'brightness': 100},
    'red': {'hue': 0, 'saturation': 100, 'brightness': 100},
    'orange': {'hue': 30, 'saturation': 100, 'brightness': 100},
    'yellow': {'hue': 60, 'saturation': 100, 'brightness': 100},
    'green': {'hue': 120, 'saturation': 100, 'brightness': 100},
    'blue': {'hue': 240, 'saturation': 100, 'brightness': 100},
    'purple': {'hue': 280, 'saturation': 100, 'brightness': 100},
    'pink': {'hue': 330, 'saturation': 80, 'brightness': 100},
    'night_mode': {'hue': 30, 'saturation': 100, 'brightness': 10},
}

# Retry configuration
MAX_RETRY_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 2


class BulbConnection:
    """
    Represents a connection to a single Tapo bulb.

    Tracks connection state and provides reconnection logic with exponential
    backoff.
    """

    def __init__(self, bulb_id: str, ip_address: str, credentials: Optional[Credentials] = None):
        """
        Initialise a bulb connection.

        @param bulb_id Unique identifier for this bulb
        @param ip_address IP address of the bulb
        @param credentials Tapo account credentials for authentication
        """
        self.bulb_id = bulb_id
        self.ip_address = ip_address
        self.credentials = credentials
        self.device = None
        self.is_connected = False
        self.last_error: Optional[str] = None
        self.retry_count = 0
        self._last_hsv: Optional[tuple] = None

    async def connect(self) -> bool:
        """
        Attempt to connect to the bulb.

        Uses device discovery at the specified IP address and updates the
        device state. Credentials are required for Tapo devices.

        @returns True if connection successful, False otherwise
        """
        result = False

        try:
            self.device = await Discover.discover_single(
                self.ip_address,
                credentials=self.credentials,
                timeout=10
            )
            await self.device.update()
            self.is_connected = True
            self.last_error = None
            self.retry_count = 0
            logger.info("Connected to bulb %s at %s", self.bulb_id, self.ip_address)
            result = True
        except Exception as error:
            self.is_connected = False
            self.last_error = str(error)
            logger.error(
                "Failed to connect to bulb %s at %s: %s",
                self.bulb_id,
                self.ip_address,
                error
            )

        return result

    async def reconnect_with_backoff(self) -> bool:
        """
        Attempt to reconnect with exponential backoff.

        Tries up to MAX_RETRY_ATTEMPTS times with increasing delays between
        attempts (2s, 4s, 8s).

        @returns True if reconnection successful, False otherwise
        """
        result = False

        for attempt in range(MAX_RETRY_ATTEMPTS):
            delay = BASE_RETRY_DELAY_SECONDS * (2 ** attempt)
            logger.info(
                "Reconnection attempt %d/%d for bulb %s (waiting %ds)",
                attempt + 1,
                MAX_RETRY_ATTEMPTS,
                self.bulb_id,
                delay
            )

            if attempt > 0:
                await asyncio.sleep(delay)

            if await self.connect():
                result = True
                break

            self.retry_count = attempt + 1

        return result

    def get_state(self) -> Dict[str, Any]:
        """
        Get the current state of the bulb.

        @returns Dictionary containing bulb state information
        """
        state = {
            'id': self.bulb_id,
            'ip': self.ip_address,
            'connected': self.is_connected,
            'error': self.last_error,
        }

        if self.is_connected and self.device:
            state['is_on'] = self.device.is_on
            state['brightness'] = getattr(self.device, 'brightness', 100)

            # Get colour information if available
            if hasattr(self.device, 'hsv'):
                hsv = self.device.hsv
                if hsv:
                    state['hue'] = hsv[0]
                    state['saturation'] = hsv[1]
                    state['brightness'] = hsv[2]

            # Get device alias/name if available
            if hasattr(self.device, 'alias'):
                state['name'] = self.device.alias
            else:
                state['name'] = f"Bulb {self.bulb_id}"
        else:
            state['is_on'] = False
            state['name'] = f"Bulb {self.bulb_id}"

        return state

    def save_hsv_state(self):
        """
        Save current HSV values from device.

        Stores the current hue, saturation, and brightness values so they can
        be restored after the bulb is turned back on.
        """
        if self.is_connected and self.device and hasattr(self.device, 'hsv'):
            hsv = self.device.hsv
            if hsv:
                self._last_hsv = (hsv[0], hsv[1], hsv[2])
                logger.debug(
                    "Saved HSV state for bulb %s: H=%d S=%d B=%d",
                    self.bulb_id,
                    hsv[0],
                    hsv[1],
                    hsv[2]
                )


class TapoBulbClient:
    """
    Client for managing multiple Tapo smart bulbs.

    Provides connection pooling, bulk operations, and automatic reconnection
    handling.
    """

    def __init__(self):
        """Initialise the Tapo bulb client from environment variables."""
        self._bulbs: Dict[str, BulbConnection] = {}
        self._initialised = False
        self._credentials = None

        # Load Tapo credentials
        tapo_username = os.environ.get('TAPO_USERNAME', '')
        tapo_password = os.environ.get('TAPO_PASSWORD', '')
        if tapo_username and tapo_password:
            self._credentials = Credentials(tapo_username, tapo_password)
            logger.info("Tapo credentials loaded")
        else:
            logger.warning("Tapo credentials not configured - bulb connections may fail")

        bulb_ips_string = os.environ.get('TAPO_BULB_IPS', '')
        if bulb_ips_string:
            ip_list = [ip.strip() for ip in bulb_ips_string.split(',') if ip.strip()]
            for index, ip_address in enumerate(ip_list):
                bulb_id = str(index + 1)
                self._bulbs[bulb_id] = BulbConnection(bulb_id, ip_address, self._credentials)

        logger.info("TapoBulbClient initialised with %d bulbs", len(self._bulbs))

    _loop = None
    def _run_async(self, coroutine):
        if TapoBulbClient._loop is None:
            import threading
            TapoBulbClient._loop = asyncio.new_event_loop()
            thread = threading.Thread(target=TapoBulbClient._loop.run_forever, daemon=True)
            thread.start()
        future = asyncio.run_coroutine_threadsafe(coroutine, TapoBulbClient._loop)
        return future.result(timeout=15)

    async def _connect_all_async(self) -> Dict[str, bool]:
        results = {}
        tasks = {bulb_id: bulb.connect() for bulb_id, bulb in self._bulbs.items()}
        if tasks:
            connection_results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for bulb_id, result in zip(tasks.keys(), connection_results):
                results[bulb_id] = False if isinstance(result, Exception) else result
        self._initialised = True
        return results

    def connect_all(self) -> Dict[str, bool]:
        """Connect to all bulbs using the background event loop."""
        return self._run_async(self._connect_all_async())

    async def _get_all_bulb_states_async(self) -> List[Dict[str, Any]]:
        tasks = []
        for bulb in self._bulbs.values():
            if bulb.is_connected and bulb.device:
                tasks.append(bulb.device.update())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return [bulb.get_state() for bulb in self._bulbs.values()]

    def get_all_bulb_states(self) -> List[Dict[str, Any]]:
        """
        Get states of all bulbs.

        @returns List of bulb state dictionaries
        """
        # Connect if not initialised
        if not self._initialised:
            self.connect_all()

        return self._run_async(self._get_all_bulb_states_async())

    async def _set_bulb_power_async(
        self, bulb_id: str, power_on: bool
    ) -> Dict[str, Any]:
        """
        Set power state for a single bulb asynchronously.

        Preserves brightness by saving HSV state before turning off and
        restoring it after turning on.

        @param bulb_id The ID of the bulb to control
        @param power_on True to turn on, False to turn off
        @returns Result dictionary with success status
        """
        result = {'bulb_id': bulb_id, 'success': False, 'error': None}

        if bulb_id not in self._bulbs:
            result['error'] = f"Bulb {bulb_id} not found"
        else:
            bulb = self._bulbs[bulb_id]

            if not bulb.is_connected or not bulb.device:
                result['error'] = "Bulb not connected"
            else:
                try:
                    if power_on:
                        saved_hsv = bulb._last_hsv
                        if not saved_hsv and hasattr(bulb.device, 'hsv') and bulb.device.hsv:
                            saved_hsv = (
                                bulb.device.hsv[0],
                                bulb.device.hsv[1],
                                bulb.device.hsv[2]
                            )

                        await bulb.device.turn_on()

                        if saved_hsv:
                            await bulb.device.set_hsv(
                                saved_hsv[0],
                                saved_hsv[1],
                                saved_hsv[2]
                            )
                            logger.debug(
                                "Restored HSV for bulb %s: H=%d S=%d B=%d",
                                bulb_id,
                                saved_hsv[0],
                                saved_hsv[1],
                                saved_hsv[2]
                            )
                    else:
                        bulb.save_hsv_state()
                        await bulb.device.turn_off()

                    await bulb.device.update()
                    result['success'] = True
                    result['is_on'] = bulb.device.is_on
                except Exception as error:
                    result['error'] = str(error)
                    bulb.is_connected = False
                    bulb.last_error = str(error)

        return result

    def set_bulb_power(self, bulb_id: str, power_on: bool) -> Dict[str, Any]:
        """
        Set power state for a single bulb.

        @param bulb_id The ID of the bulb to control
        @param power_on True to turn on, False to turn off
        @returns Result dictionary with success status
        """
        return self._run_async(self._set_bulb_power_async(bulb_id, power_on))

    async def _set_bulb_colour_async(
        self,
        bulb_id: str,
        hue: int,
        saturation: int,
        brightness: int
    ) -> Dict[str, Any]:
        """
        Set colour for a single bulb asynchronously.

        @param bulb_id The ID of the bulb to control
        @param hue Colour hue (0-360)
        @param saturation Colour saturation (0-100)
        @param brightness Brightness level (0-100)
        @returns Result dictionary with success status
        """
        result = {'bulb_id': bulb_id, 'success': False, 'error': None}

        if bulb_id not in self._bulbs:
            result['error'] = f"Bulb {bulb_id} not found"
        else:
            bulb = self._bulbs[bulb_id]

            if not bulb.is_connected or not bulb.device:
                result['error'] = "Bulb not connected"
            else:
                try:
                    # Ensure bulb is on before setting colour
                    if not bulb.device.is_on:
                        await bulb.device.turn_on()

                    # Set HSV values
                    await bulb.device.set_hsv(hue, saturation, brightness)
                    await bulb.device.update()
                    result['success'] = True
                except Exception as error:
                    result['error'] = str(error)
                    bulb.is_connected = False
                    bulb.last_error = str(error)

        return result

    def set_bulb_colour(
        self,
        bulb_id: str,
        hue: int,
        saturation: int,
        brightness: int
    ) -> Dict[str, Any]:
        """
        Set colour for a single bulb.

        @param bulb_id The ID of the bulb to control
        @param hue Colour hue (0-360)
        @param saturation Colour saturation (0-100)
        @param brightness Brightness level (0-100)
        @returns Result dictionary with success status
        """
        return self._run_async(
            self._set_bulb_colour_async(bulb_id, hue, saturation, brightness)
        )

    async def _set_bulb_brightness_async(
        self, bulb_id: str, brightness: int
    ) -> Dict[str, Any]:
        """
        Set brightness for a single bulb, preserving its current colour.

        @param bulb_id The ID of the bulb to control
        @param brightness Brightness level (1-100)
        @returns Result dictionary with success status
        """
        result = {'bulb_id': bulb_id, 'success': False, 'error': None}

        if bulb_id not in self._bulbs:
            result['error'] = f"Bulb {bulb_id} not found"
        else:
            bulb = self._bulbs[bulb_id]

            if not bulb.is_connected or not bulb.device:
                result['error'] = "Bulb not connected"
            else:
                try:
                    if not bulb.device.is_on:
                        await bulb.device.turn_on()

                    hue = 0
                    saturation = 0
                    if hasattr(bulb.device, 'hsv') and bulb.device.hsv:
                        hue = bulb.device.hsv[0]
                        saturation = bulb.device.hsv[1]

                    await bulb.device.set_hsv(hue, saturation, brightness)
                    await bulb.device.update()
                    result['success'] = True
                except Exception as error:
                    result['error'] = str(error)
                    bulb.is_connected = False
                    bulb.last_error = str(error)

        return result

    def set_bulb_brightness(self, bulb_id: str, brightness: int) -> Dict[str, Any]:
        """
        Set brightness for a single bulb.

        @param bulb_id The ID of the bulb to control
        @param brightness Brightness level (1-100)
        @returns Result dictionary with success status
        """
        return self._run_async(self._set_bulb_brightness_async(bulb_id, brightness))

    async def _set_all_brightness_async(self, brightness: int) -> Dict[str, Any]:
        """
        Set brightness for all bulbs asynchronously.

        @param brightness Brightness level (1-100)
        @returns Result dictionary with success count and individual results
        """
        tasks = [
            self._set_bulb_brightness_async(bulb_id, brightness)
            for bulb_id in self._bulbs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        resolved = []
        success_count = 0
        for r in results:
            if isinstance(r, Exception):
                resolved.append({'success': False, 'error': str(r)})
            else:
                resolved.append(r)
                if r['success']:
                    success_count += 1

        return {
            'success_count': success_count,
            'total_count': len(self._bulbs),
            'results': resolved
        }

    def set_all_brightness(self, brightness: int) -> Dict[str, Any]:
        """
        Set brightness for all bulbs.

        @param brightness Brightness level (1-100)
        @returns Result dictionary with success count and individual results
        """
        return self._run_async(self._set_all_brightness_async(brightness))

    async def _set_all_power_async(self, power_on: bool) -> Dict[str, Any]:
        """
        Set power state for all bulbs asynchronously.

        @param power_on True to turn on, False to turn off
        @returns Result dictionary with success count and individual results
        """
        tasks = [
            self._set_bulb_power_async(bulb_id, power_on)
            for bulb_id in self._bulbs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        resolved = []
        success_count = 0
        for r in results:
            if isinstance(r, Exception):
                resolved.append({'success': False, 'error': str(r)})
            else:
                resolved.append(r)
                if r['success']:
                    success_count += 1

        return {
            'success_count': success_count,
            'total_count': len(self._bulbs),
            'results': resolved
        }

    def set_all_power(self, power_on: bool) -> Dict[str, Any]:
        """
        Set power state for all bulbs.

        @param power_on True to turn on, False to turn off
        @returns Result dictionary with success count and individual results
        """
        return self._run_async(self._set_all_power_async(power_on))

    async def _set_all_colour_async(
        self,
        hue: int,
        saturation: int,
        brightness: int
    ) -> Dict[str, Any]:
        """
        Set colour for all bulbs asynchronously.

        @param hue Colour hue (0-360)
        @param saturation Colour saturation (0-100)
        @param brightness Brightness level (0-100)
        @returns Result dictionary with success count and individual results
        """
        tasks = [
            self._set_bulb_colour_async(bulb_id, hue, saturation, brightness)
            for bulb_id in self._bulbs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        resolved = []
        success_count = 0
        for r in results:
            if isinstance(r, Exception):
                resolved.append({'success': False, 'error': str(r)})
            else:
                resolved.append(r)
                if r['success']:
                    success_count += 1

        return {
            'success_count': success_count,
            'total_count': len(self._bulbs),
            'results': resolved
        }

    def set_all_colour(
        self,
        hue: int,
        saturation: int,
        brightness: int
    ) -> Dict[str, Any]:
        """
        Set colour for all bulbs.

        @param hue Colour hue (0-360)
        @param saturation Colour saturation (0-100)
        @param brightness Brightness level (0-100)
        @returns Result dictionary with success count and individual results
        """
        return self._run_async(
            self._set_all_colour_async(hue, saturation, brightness)
        )

    async def _reconnect_bulb_async(self, bulb_id: str) -> Dict[str, Any]:
        """
        Attempt to reconnect a single bulb asynchronously.

        @param bulb_id The ID of the bulb to reconnect
        @returns Result dictionary with success status
        """
        result = {'bulb_id': bulb_id, 'success': False, 'error': None}

        if bulb_id not in self._bulbs:
            result['error'] = f"Bulb {bulb_id} not found"
        else:
            bulb = self._bulbs[bulb_id]
            success = await bulb.reconnect_with_backoff()
            result['success'] = success
            if not success:
                result['error'] = bulb.last_error

        return result

    def reconnect_bulb(self, bulb_id: str) -> Dict[str, Any]:
        """
        Attempt to reconnect a single bulb.

        @param bulb_id The ID of the bulb to reconnect
        @returns Result dictionary with success status
        """
        return self._run_async(self._reconnect_bulb_async(bulb_id))

