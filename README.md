# Iotics Smart Home - Home Assistant Integration

Custom integration for [Iotics](https://iotics.com) smart home devices (switches, fans, dimmers, LED lights).

> **Fork** of [keithcardozo10-dev/ha-iotics-addon](https://github.com/keithcardozo10-dev/ha-iotics-addon), maintained by [Kriday5262](https://github.com/Kriday5262) and [keithcardozo10-dev](https://github.com/keithcardozo10-dev) with the assistance of opencode.

## Installation

### Option 1: HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=Kriday5262/ha-iotics&category=integration)

1. Click the badge above (or open HACS manually: **HACS > Integrations > ⋯ > Custom repositories**)
2. Add `https://github.com/Kriday5262/ha-iotics` with category **Integration**
3. Click **Download** on the Iotics card
4. Restart Home Assistant

### Option 2: Manual

1. Download the [latest release](https://github.com/Kriday5262/ha-iotics/releases/latest) zip
2. Extract the `iotics` folder into `<config>/custom_components/`
3. Restart Home Assistant

## Setup

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Iotics**
3. Enter the email and password you use in the Iotics mobile app
4. Your devices (switches, fans, dimmers, lights) are discovered automatically

## Notes

- The integration bridges the shared Iotics AWS IoT broker (MQTT) and the local REST API on each device.
- Device states are tracked via MQTT; commands are sent over HTTP to the device's local IP.
- The broker is shared with all Iotics customers, so the integration only reacts to MQTT messages from your own devices.

## Support

Open an [issue](https://github.com/Kriday5262/ha-iotics/issues) for bugs or feature requests.
