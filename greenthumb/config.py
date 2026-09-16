from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GreenThumb"
    api_prefix: str = "/api/v1"
    klipper_host: str = "/run/klipper/uds"
    moisture_sensor_addresses: str = "54,55,56,57"
    pump_pin: int = 17
    led_count: int = 60
    gantry_rail_length_mm: float = 1000.0
    gantry_position_margin_mm: float = 20.0
    debug: bool = False

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
