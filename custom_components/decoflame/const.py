"""Constants for the Decoflame integration."""

DOMAIN = "decoflame"

# BLE
DEFAULT_NAME = "Decoflame"
DECOFLAME_NAME_PREFIX = "decoflame"

# Config entry keys
CONF_ADDRESS = "address"
CONF_SERVICE_UUID = "service_uuid"
CONF_WRITE_CHAR_UUID = "write_char_uuid"
CONF_READ_CHAR_UUID = "read_char_uuid"

# BLE commands (2-byte)
CMD_ON:  bytes = bytes([0x00, 0x10])
CMD_OFF: bytes = bytes([0x00, 0x20])

# Flame levels 1–5 map to 0x01–0x05; ECO is the highest setting (0x06)
FLAME_LEVEL_COMMANDS: dict[str, bytes] = {
    "1":   bytes([0x00, 0x01]),
    "2":   bytes([0x00, 0x02]),
    "3":   bytes([0x00, 0x03]),
    "4":   bytes([0x00, 0x04]),
    "5":   bytes([0x00, 0x05]),
    "ECO": bytes([0x00, 0x06])}

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

# Connectivity ping/timeout
PING_INTERVAL_SECONDS   = 60        # 60 seconds — fallback when advertisements are missed
OFFLINE_TIMEOUT_SECONDS = 60 * 60   # 60 minutes without response → offline

# Advertisement
ADV_COMPANY_ID = 0x017F  # bytes: 7F 01

ADV_FLAME_LEVEL: dict[int, str] = {
    0x01: "1",
    0x02: "2",
    0x03: "3",
    0x04: "4",
    0x05: "5",
    0x06: "ECO"}

ADV_FLAME_OFF    = 0x1E
ADV_FLAME_WARMING = 0x07

ADV_TIMEOUT_SECONDS = 120  # 2 minutes without advertisement → unavailable
