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

# Known UUIDs — confirmed via PacketLogger + working ESPHome config
KNOWN_SERVICE_UUID    = "0e6f3b07-c6fd-401b-9d25-496491dfa3d6"
KNOWN_WRITE_CHAR_UUID = "da16b070-1fb1-11e4-8c21-0800200c9a66"
READ_CHAR_UUID        = "e7add780-b042-4876-aae1-112855353cc1"

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

# Timing — proxy path adds WiFi latency on top of BLE; use conservative values
BLE_DELAY_AFTER_CONNECT_S = 0.5   # wait for MTU + proxy setup before write
BLE_DELAY_AFTER_WRITE_S   = 1.0   # let device process before disconnect

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
PING_INTERVAL_SECONDS   = 30 * 60   # 30 minutes
OFFLINE_TIMEOUT_SECONDS = 60 * 60   # 60 minutes without response → offline
