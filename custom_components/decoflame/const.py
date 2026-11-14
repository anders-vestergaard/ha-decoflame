"""Constants for the Decoflame integration."""

DOMAIN = "decoflame"

# BLE
DEFAULT_NAME = "Decoflame"
DECOFLAME_NAME_PREFIX = "decoflame"

# Config entry keys
CONF_ADDRESS = "address"
CONF_WRITE_CHAR_UUID = "write_char_uuid"
CONF_READ_CHAR_UUID = "read_char_uuid"

# BLE commands (2-byte)
CMD_ON:  bytes = bytes([0x00, 0x10])
CMD_OFF: bytes = bytes([0x00, 0x20])

# Flame levels 1–5 map to 0x01–0x05. ECO is the lowest output (0.4 L/h, like
# level 1) even though the fireplace and the app number it 6 (0x06).
# Ordered by output, so the select lists ECO first.
FLAME_LEVEL_COMMANDS: dict[str, bytes] = {
    "ECO": bytes([0x00, 0x06]),
    "1":   bytes([0x00, 0x01]),
    "2":   bytes([0x00, 0x02]),
    "3":   bytes([0x00, 0x03]),
    "4":   bytes([0x00, 0x04]),
    "5":   bytes([0x00, 0x05])}

FLAME_LEVELS = list(FLAME_LEVEL_COMMANDS.keys())

# Timing
BLE_DELAY_AFTER_CONNECT_S = 0.2
BLE_DELAY_AFTER_WRITE_S   = 0.5

# Reverse-mapping from read-char echo (last 2 bytes) → (is_on, flame_level or None)
ECHO_TO_STATE: dict[bytes, tuple[bool, str | None]] = {
    bytes([0x00, 0x10]): (True, None),    # CMD_ON — preserve existing flame level
    bytes([0x00, 0x20]): (False, None),   # CMD_OFF
    bytes([0x00, 0x01]): (True, "1"),
    bytes([0x00, 0x02]): (True, "2"),
    bytes([0x00, 0x03]): (True, "3"),
    bytes([0x00, 0x04]): (True, "4"),
    bytes([0x00, 0x05]): (True, "5"),
    bytes([0x00, 0x06]): (True, "ECO")}

# Connectivity
PING_INTERVAL_SECONDS = 60       # periodic presence check; first GATT read backoff
READ_BACKOFF_MAX_SECONDS = 600   # GATT read backoff doubles up to this while the device is gone
READ_BACKOFF_SLACK_SECONDS = 5   # the update tick can fire slightly early

# Advertisement
ADV_COMPANY_ID = 0x017F  # bytes: 7F 01

# mfr_data[13]: fuel level in percent (confirmed against the app: 96 % = 0x60).
# It jitters by one between adverts (0x5F/0x60).
ADV_FUEL_LEVEL_INDEX = 13
# mfr_data[14]: current fuel consumption in tenths of a litre per hour
# (confirmed against the app: ECO 0x04 = 0.4 L/h, level 5 0x09 = 0.9 L/h);
# 0 while warming up and when off.
ADV_FUEL_RATE_INDEX = 14

ADV_FLAME_LEVEL: dict[int, str] = {
    0x01: "1",
    0x02: "2",
    0x03: "3",
    0x04: "4",
    0x05: "5",
    0x06: "ECO"}

ADV_FLAME_TURNING_OFF = 0x1E  # mfr_data[12]: turning off
ADV_FLAME_WARMING     = 0x07  # mfr_data[12]: warmup phase 1 OR completely off (see ADV_STATUS_OFF)
ADV_FLAME_WARMING2    = 0x10  # mfr_data[12]: warmup phase 2 (ramping up)
ADV_STATUS_OFF        = 0x1C  # mfr_data[13]: completely off (paired with ADV_FLAME_WARMING)
