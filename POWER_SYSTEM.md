# GreenThumb Power System

## Overview
GreenThumb uses a 12V primary bus with a DC-DC converter for 5V logic. All components draw from a central busbar with fused circuits.

## Power Supply Specifications

### Main Charger
- **Input:** AC wall power
- **Output:** 12V DC @ minimum 5A (60W)
- **Recommended:** 12V @ 7A (84W) for headroom
- **Type:** Standard barrel jack or XT60 connector

**Why 5A minimum?**
- Pump (12V peristaltic, 100 mL/min): 0.2-0.3A
- LED strip (60 LEDs, 12V WS2811): ~1.2A @ full white
- SKR + Pi + sensors: ~0.5-1A
- Total peak: ~25W, so 5A (60W) is generous headroom rather than a floor

## Busbar Setup

```
12V Charger
    └─→ [5A Inline Fuse Holder] ─→ Busbar
                                      ├─→ [1A Inline Fuse Holder] ─→ 12V Peristaltic Pump
                                      ├─→ 12V-to-5V DC-DC Converter (3A output) ─→ Raspberry Pi
                                      └─→ BTT SKR Mini E3 V2 Board
```

## Fuse Specifications

### Main Circuit Protection
- **Location:** Charger output → Busbar input
- **Type:** Fast-blow glass fuse (automotive style)
- **Rating:** 5A
- **Purpose:** Protects entire system from shorts in busbar or downstream

### Pump Circuit Protection
- **Location:** Busbar → Pump positive wire
- **Type:** Fast-blow glass fuse
- **Rating:** 1A
- **Purpose:** Protects pump circuit; allows pump failure without killing entire system
- **Optional but recommended:** Provides granular protection and easier troubleshooting

**Why 1A and not 2A.** The pump draws 0.2-0.3A running. A 2A fuse would let a
fault pull nearly 2A indefinitely without ever blowing, which is barely
protection at all. 1A sits above the stall current of a motor this small — so a
jammed pump trips it, which is the point — while leaving room for start-up
inrush. Size a pump fuse against the pump, not against the supply.

## Power Budget

| Component | Voltage | Current | Power |
|-----------|---------|---------|-------|
| SKR Mini E3 V2 | 12V | 0.3A | 3.6W |
| Raspberry Pi 4 | 5V | 0.6A | 3W |
| Pi Camera | 5V | 0.1A | 0.5W |
| Soil Moisture Sensors (4x) | 3.3V | 0.05A | 0.15W |
| Addressable LEDs (60x WS2811, 12V) | 12V | ~1.2A (peak full white) | ~14W |
| Peristaltic Pump (12V, 100 mL/min) | 12V | 0.2-0.3A | ~3.6W |
| **Total Peak** | — | **~2.1A @ 12V** | **~25W** |
| **Typical Operation** | — | **~1A @ 12V** | **~12W** |

**Notes:**
- LEDs typically don't run at full brightness; realistic average is 20-30% brightness
- Pump runs in short bursts; not continuous
- Peak draw occurs if everything runs simultaneously (rare)

**Why the LED figure is lower than 5V strips:**

A 12V WS2811 strip wires the LEDs in groups of three in series, so one
controller IC and one current path light three LEDs instead of one. Sixty LEDs
is twenty groups drawing roughly 60 mA each, about 1.2A total — a third of the
~3.6A the same LED count would pull on a 5V WS2812B strip.

This also means **the strip addresses 20 pixels, not 60.** The three LEDs in a
group always show the same colour. Set `LED_COUNT` to the number of addressable
pixels, not the number of LEDs you can count.

## DC-DC Converter Specifications

- **Input:** 12V DC (8-18V range typical)
- **Output:** 5V DC @ 3A (15W continuous)
- **Efficiency:** ~85-90%
- **Purpose:** Powers Raspberry Pi, camera, and sensors
- **Mounting:** Secure with thermal paste or small heatsink to prevent shutdown under load

## Wiring & Connectors

### Main Busbar
- Use a **3-pad solder busbar** or **distribution block** (commonly called "power distribution board")
- Pads: +12V, Ground, Ground (or +12V, +5V, Ground if integrating 5V rail)
- Wire gauge: **14 AWG minimum** (10 AWG recommended for 12V runs > 2 meters)

### Fuse Holders
- Inline fuse holders with **16 AWG or larger wire leads**
- Crimp or solder connections; avoid push-in connectors for safety
- Keep fuses accessible for quick replacement

### Pump Wiring
- 14-16 AWG wire rated for 12V
- Use either the pump's native connector or solder with heat shrink tubing
- Keep pump power isolated on its own fused circuit

## Safety Considerations

1. **Always fuse the main charger output** — protects against internal shorts
2. **Use fast-blow fuses** — electronics need quick response; slow-blow is for motors
3. **Capacitor across pump input** — Add a 1000µF capacitor to smooth voltage spikes when pump starts
4. **Label all circuits** — Use tape/labels on busbar pads and fuse holders
5. **No bare connections** — Use heat shrink, electrical tape, or shrouded connectors
6. **Check voltage under load** — Monitor Pi voltage; it should not drop below 4.75V

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Pi won't boot / reboots randomly | Low 5V voltage | Check DC-DC input/output; may need heatsink |
| Pump doesn't run | Blown 1A fuse | Check for shorts in pump wiring |
| LEDs flicker or dim | Voltage sag under LED draw | Upgrade charger or add capacitor |
| LEDs do nothing at all | Pi and strip grounds not tied together | Run a ground wire from a Pi GND pin to the busbar ground |
| LEDs flicker or show junk on the first pixels | 3.3V data is marginal for WS2811 | Add a 74AHCT125 level shifter on the data line |
| Red and green are swapped | Strip uses a different channel order | Change LED colour order in the settings page |
| Charger warm/hot | Overload or internal short | Reduce load; check for shorts; consider larger PSU |
| Fuses blow immediately | Direct short somewhere | Inspect all wiring for damage before replacing |

## Future Expansion

If adding more components (second pump, more LEDs, etc.):
1. Recalculate total current draw
2. Upgrade charger amperage if needed
3. Potentially upgrade fuse ratings proportionally
4. Consider a separate 12V supply for power-hungry subsystems

