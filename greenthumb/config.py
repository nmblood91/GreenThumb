from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GreenThumb"
    api_prefix: str = "/api/v1"
    klipper_host: str = "/run/klipper/uds"
    moisture_sensor_addresses: str = "54,55,56,57"
    # Name of the [output_pin] section in printer.cfg, not a GPIO number: the
    # pump hangs off the SKR's HE0 MOSFET and is switched by Klipper.
    pump_pin_name: str = "pump"
    # 100 mL/min rated, and that rating assumes no head pressure. Real delivery
    # through lift and tubing runs lower, so measure against a real dose: this
    # converts millilitres into a run time, and an error here scales every
    # watering by the same factor while still reporting success.
    pump_flow_ml_per_second: float = 1.67
    # Addressable pixels, not physical LEDs. A 12V WS2811 strip drives three
    # LEDs per controller, so a 60-LED strip addresses 20 pixels.
    led_count: int = 20
    # WS2811 is usually RGB where WS2812B is GRB; if red and green swap, fix here.
    led_color_order: str = "RGB"
    led_spi_bus: int = 0
    led_spi_device: int = 0
    gantry_rail_length_mm: float = 1000.0
    gantry_position_margin_mm: float = 20.0
    debug: bool = False

    # Control loop
    sensor_poll_seconds: int = 60
    # Watering decisions use the mean of this many polls, so at a 60s interval
    # the loop acts on a 10 minute trend rather than a single noisy reading.
    moisture_window_size: int = 10

    # Shared calibration for all probes. Raw capacitance, not per sensor: the
    # spread between probes is far smaller than the margin a watering decision
    # needs. Wet is the reading in plain water, which soil never quite reaches.
    moisture_raw_dry: int = 350
    moisture_raw_wet: int = 1016

    # Off by default: the pump driver is still a stub, and an unattended pump
    # is the one failure here that can drown a plant or run itself dry.
    auto_watering_enabled: bool = False
    watering_cooldown_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def moisture_sensor_addresses_list(self) -> list[int]:
        """Parse comma-separated sensor addresses to list of integers."""
        return [int(addr.strip()) for addr in self.moisture_sensor_addresses.split(",")]


settings = Settings()
