"""Daikin Madoka consts."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "daikin_madoka"

CONF_MAC = "address"
CONF_FRIENDLY_NAME = "friendly_name"

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

DEFAULT_ADAPTER = "hci0"
CONNECT_TIMEOUT = 15
SCAN_INTERVAL = timedelta(seconds=30)

MANUFACTURER = "DAIKIN"
MODEL_PREFIX = "BRC1H"

MIN_TEMP = 16
MAX_TEMP = 32
TARGET_TEMP_STEP = 1
