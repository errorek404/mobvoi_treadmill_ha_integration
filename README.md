# Mobvoi Home Treadmill Plus – Home Assistant Integration

Custom Home Assistant integration for **Mobvoi Home Treadmill Plus** over Bluetooth Low Energy (FTMS).

## Features
- **Controls:** Start/Stop belt (`switch`), Target speed 1.0–12.0 km/h (`number`), Emergency stop (`button`).
- **Sensors:** Speed (`km/h`), Distance (`m`), Calories (`kcal`), Elapsed time (`s`).
- Automatic Bluetooth discovery (`Mobvoi*` / `FS-*`) and manual MAC configuration.

## Installation (HACS)
1. Open HACS in Home Assistant.
2. Add `https://github.com/errorek404/mobvoi_treadmill_ha_integration` as a custom repository (Category: **Integration**).
3. Download **Mobvoi Home Treadmill Plus** and restart Home Assistant.
4. Wake up the treadmill (ensure the display is lit) and add the integration via **Settings -> Devices & services**.
