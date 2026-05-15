# ha-decoflame

Home Assistant custom integration for Decoflame bio-fireplaces via Bluetooth Low Energy (BLE).

## Features

- **Switch** — tænd/sluk pejsen
- **Select** — vælg flammeniveau (1–5 + ECO)
- **Binary sensor** — forbindelsesstatus

## Requirements

- Home Assistant med Bluetooth-understøttelse
- ESPHome BLE proxy (anbefalet) eller direkte Bluetooth-adapter tæt på pejsen
- Decoflame pejs med BLE-modul

## Installation

### HACS (anbefalet)

1. Tilføj dette repository som custom repository i HACS
2. Installer "Decoflame"
3. Genstart Home Assistant

### Manuelt

1. Kopiér `custom_components/decoflame/` til din HA's `custom_components/`-mappe
2. Genstart Home Assistant

## Setup

1. Gå til **Indstillinger → Enheder og tjenester → Tilføj integration**
2. Søg efter "Decoflame"
3. Integrationen finder automatisk pejsen via BLE — eller indtast MAC-adressen manuelt
4. GATT-karakteristikker opdages automatisk ved pairing

## BLE Proxy (ESPHome)

Minimal ESPHome-konfiguration:

```yaml
bluetooth_proxy:
  active: true
```

## License

MIT
