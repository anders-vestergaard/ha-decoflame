# ha-decoflame

Home Assistant custom integration for Decoflame bio-fireplaces via Bluetooth Low Energy (BLE).

## Features

- **Switch** — turn the fireplace on/off. Usable as long as Home Assistant can reach the fireplace, so you can always try a command; a failing command shows an error message
- **Select** — set flame level: ECO, 1–5. ECO is the lowest output, so it is listed first. Unavailable while the fireplace is off, warming up or shutting down
- **Binary sensor** — connection status
- **Sensor: state** — `off`, `warming_up` (about 6½ minutes after turning on), `on`, `turning_off` (about 7 minutes after turning off)
- **Sensor: fuel level** — in %
- **Sensor: fuel consumption** — in L/h, from 0.4 L/h (ECO and level 1) to 0.9 L/h (level 5); 0 while warming up, turning off and off
- **Diagnostics** — download a diagnostics file for troubleshooting
- **Languages** — English and Danish

## How the connection works

State is driven by BLE advertisements — no persistent connection required. Connection status follows Home Assistant's own Bluetooth tracking:

- The fireplace is **connected** as long as Home Assistant sees it through an adapter or proxy — also while it keeps sending the same advertisement, which it does while burning steadily.
- It goes **offline** only when Home Assistant itself reports it unavailable. In practice that is 3–8 minutes after the fireplace disappears (Home Assistant's own timeouts).
- It is **connected again** at the next advertisement or after a successful command.
- Commands reuse the cached list of Bluetooth services, which is faster over a proxy. If the fireplace's services have changed, the cache is cleared and the command is retried once.
- While Home Assistant cannot see the fireplace, no connection is attempted, so proxy connection slots are not used up.

## Requirements

- Home Assistant with Bluetooth support
- ESPHome BLE proxy (recommended) or a Bluetooth adapter close to the fireplace
- Decoflame fireplace with BLE module

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Install "Decoflame"
3. Restart Home Assistant

### Manual

1. Copy `custom_components/decoflame/` to your HA `custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "Decoflame"
3. The integration will automatically discover the fireplace via BLE — or enter the MAC address manually
4. GATT characteristics are discovered automatically during pairing

## BLE Proxy (ESPHome)

Minimal ESPHome configuration:

```yaml
bluetooth_proxy:
  active: true
```

Tested with ESPHome active BLE proxy. A direct Bluetooth adapter on the HA host should also work if it can reach the fireplace.

## Troubleshooting

### Debug logging

Add this to `configuration.yaml` and restart Home Assistant:

```yaml
logger:
  logs:
    custom_components.decoflame: debug
```

Every minute the log shows the latest advertisement Home Assistant has received — which scanner or proxy saw it, the signal strength, and the raw bytes — so you can see whether the fireplace is still sending, even when nothing changes. Failed reads and commands are logged with the reason.

### Diagnostics

**Settings → Devices & Services → Decoflame → ⋮ → Download diagnostics.** The file contains the latest raw advertisement data, which scanner or proxy last saw the fireplace, signal strength, time since the last advertisement and the last Bluetooth error. The fireplace's own address is removed; the name and address of your proxy remain, so you can see which one saw it.

## Known limitations

- When the fireplace disappears, it takes 3–8 minutes before Home Assistant reports it offline.
- ESPHome proxies have a limited number of connection slots. Commands use one briefly.
- The fuel level may vary by 1 % between updates.

## Development

Tests use `pytest-homeassistant-custom-component`:

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements_test.txt
.venv/bin/python -m pytest
```

## Roadmap

- Timer commands
- Model information
- Support for additional Decoflame models

## License

MIT
