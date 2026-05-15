# ha-decoflame

Home Assistant custom integration for Decoflame bio-fireplaces via Bluetooth Low Energy (BLE).

## Features

- **Switch** — turn the fireplace on/off
- **Select** — set flame level (1–5 + ECO)
- **Binary sensor** — connection status

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

## License

MIT
