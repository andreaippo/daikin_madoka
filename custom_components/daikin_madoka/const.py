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
    Platform.NUMBER,
    Platform.SELECT,
]

DEFAULT_ADAPTER = "hci0"
CONNECT_TIMEOUT = 15
SCAN_INTERVAL = timedelta(seconds=30)

# How many poll cycles to skip between two reads of the ring behaviour. The
# device only returns it with the edit session open, which makes the read cost
# three BLE round-trips against one for every other feature, so it is not read
# on every cycle. Once every twenty keeps it in step with the official app
# within ten minutes.
RING_MODE_POLL_CYCLES = 20

MANUFACTURER = "DAIKIN"
MODEL_PREFIX = "BRC1H"

MIN_TEMP = 16
MAX_TEMP = 32
TARGET_TEMP_STEP = 1
