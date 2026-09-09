from __future__ import annotations

from fastapi import FastAPI

from greenthumb.config import settings
from greenthumb.services.automation import GreenThumbAutomation

app = FastAPI(
    title=settings.app_name,
    description="Smart planter automation platform for the GreenThumb hardware stack.",
    version="0.1.0",
)

automation = GreenThumbAutomation()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.get(f"{settings.api_prefix}/overview")
async def get_overview() -> dict[str, object]:
    return automation.get_overview()


@app.get(f"{settings.api_prefix}/sensors")
async def read_sensors() -> list[dict[str, object]]:
    return automation.read_sensors()


@app.post(f"{settings.api_prefix}/water/{{zone_id}}")
async def water_zone(zone_id: str, volume_ml: int = 180) -> dict[str, object]:
    return automation.water_zone(zone_id, volume_ml)


@app.post(f"{settings.api_prefix}/lights/{{mode}}")
async def set_light_mode(mode: str) -> dict[str, object]:
    return automation.set_light_mode(mode)


@app.post(f"{settings.api_prefix}/motion/home/{{axis}}")
async def home_axis(axis: str) -> dict[str, object]:
    return automation.home_motion_axis(axis)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("greenthumb.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
