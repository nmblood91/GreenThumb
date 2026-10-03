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

## Calibration

Raw capacitance readings only become a percentage once each sensor's dry and wet
endpoints are known. Measure them per sensor rather than globally: four sensors
in identical conditions read measurably differently — on this build they span
about 25 counts in open air — and one global pair puts that spread straight into
every reported percentage.

Two passes, in either order. Each samples every sensor for 20 seconds and takes
the median, so one bad read cannot skew the result:

```bash
cd /opt/greenthumb

# all four sensors in open air, clean and dry
.venv/bin/python -m greenthumb.hardware.soil_sensors --calibrate dry

# prongs in water
.venv/bin/python -m greenthumb.hardware.soil_sensors --calibrate wet

.venv/bin/python -m greenthumb.hardware.soil_sensors --show-calibration
```

> **Only the prongs go in the water, up to the marked line.** These boards are
> not waterproof. Submerging the PCB or the connector end destroys the sensor,
> and doing all four at once destroys all four.

Results are written to `data/state.json`, which is gitignored and survives both
restarts and `git pull`. Each endpoint is stored separately, so the wet pass can
be redone without losing the dry one, and a sensor with only one endpoint
measured uses the `.env` default for the other.

Both passes can also be run from the web UI, which is the same code path.

### Air and water measure the sensor, not the soil

Calibrating against air and water gives you the sensor's **full electrical
span**. It does not mean 0% is "needs water" and 100% is "saturated" — dry soil
will read somewhere around 30-40% and a well-watered pot perhaps 80%.

That is deliberate. Air and a cup of water are repeatable anywhere, including on
a production line; "soil the plant would want watering in" is not. The
consequence is that a zone's **moisture target is a number you tune by
observation**, not a physical quantity. The History tab exists for exactly that:
watch moisture against watering events over a few days and move the target until
the plant is being watered when you would have watered it.

### When it refuses to store a reading

The calibrator will not write a value it does not believe, and says why:

| Message begins | Cause |
|---|---|
| `No sensor answered at this address` | unplugged, wrong address, or a bus fault — run `--soak` |
| `Readings drifted N counts while sampling` | the sensor had not settled; let it sit and retry |
| `Wet reading X is only N counts above…` | the wet pass ran with the sensor still in air, or it never reached the water |
| `Dry reading X is only N counts below…` | the dry pass ran on a sensor that was still wet |

Each message names the measured value, the gap it fell short by and the gap
expected, so the number tells you whether it was close or nowhere near.

Nothing is stored for that sensor, so a refused pass leaves the previous
calibration intact rather than half-overwriting it.

To start over:

```bash
curl -X POST http://localhost:8000/api/v1/sensors/calibration/reset
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
