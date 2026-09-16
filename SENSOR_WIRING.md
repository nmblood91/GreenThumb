# Moisture Sensor Wiring Guide

## Overview

GreenThumb uses four Adafruit STEMMA soil moisture sensors connected via an I2C hub to the Raspberry Pi. Each sensor reads capacitive moisture and temperature for one plant zone.

## I2C Hub Connection to Raspberry Pi

The I2C hub connects to the Raspberry Pi's I2C Bus 1 using four wires:

| Wire Color | Function | Raspberry Pi Pin |
|-----------|----------|------------------|
| Black | Ground (GND) | Pin 6, 9, 14, 20, 25, 30, 34, or 39 |
| Red | 3.3V Power | Pin 1 or Pin 17 |
| Blue | SDA (Serial Data) | GPIO 2, Pin 3 |
| Yellow | SCL (Serial Clock) | GPIO 3, Pin 5 |

## Sensor Addressing

Each STEMMA soil sensor must be configured with a unique I2C address to prevent collisions on the shared bus. The default addresses are:

| Zone | Address | Hex |
|------|---------|-----|
| Zone 1 | 54 | 0x36 |
| Zone 2 | 55 | 0x37 |
| Zone 3 | 56 | 0x38 |
| Zone 4 | 57 | 0x39 |

Configure sensor addresses using the A0 and A1 address pads on each sensor according to the Adafruit STEMMA documentation.

## Sensor Hub Layout

The 5-port STEMMA QT passive hub distributes I2C signals to:
- 1 port: back to Raspberry Pi
- 4 ports: to each zone's soil moisture sensor

## Configuration

Set sensor addresses in `.env`:

```
MOISTURE_SENSOR_ADDRESSES=54,55,56,57
```

## Testing

Check sensor connectivity before running the app:

```bash
i2cdetect -y 1
```

This should show devices at the configured addresses (e.g., 0x36, 0x37, 0x38, 0x39).

Read sensor values via the API:

```bash
curl http://<pi-host>:8000/api/v1/sensors
```

Raw sensor readings will be returned. If a sensor cannot be read, the value will be `-1`.

### Single Sensor Testing

To test with just one sensor (e.g., 0x36 in Zone 1):

```
MOISTURE_SENSOR_ADDRESSES=54
```

The API will return `-1` for any sensor that fails to initialize or read.
