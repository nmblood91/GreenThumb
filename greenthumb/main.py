from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, time
from typing import AsyncIterator

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Body, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from greenthumb.config import settings
from greenthumb.logging_setup import log_event, read_recent_logs, setup_logging
from greenthumb.services.automation import GreenThumbAutomation, HardwareBusyError

setup_logging()

automation = GreenThumbAutomation()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        automation.tick,
        "interval",
        seconds=settings.sensor_poll_seconds,
        next_run_time=datetime.now(),
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    description="Smart planter automation platform for the GreenThumb hardware stack.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})


@app.exception_handler(HardwareBusyError)
async def handle_hardware_busy(request: Request, exc: HardwareBusyError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"ok": False, "error": str(exc)})


def log_motion(result: dict[str, object], action: str) -> dict[str, object]:
    if result.get("ok"):
        log_event(f"{action}: ok")
    else:
        log_event(f"{action}: failed - {result.get('error')}")
    return result


@app.get("/")
async def index() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "ui": "React frontend served from http://localhost:5173",
        "api": "http://localhost:8000/api/v1",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


# Endpoints that reach hardware are sync so FastAPI runs them in its threadpool;
# as coroutines their blocking socket and I2C calls would stall the event loop.
@app.get(f"{settings.api_prefix}/overview")
def get_overview() -> dict[str, object]:
    return automation.get_overview()


@app.get(f"{settings.api_prefix}/sensors")
async def read_sensors() -> list[dict[str, object]]:
    return automation.read_sensors()


@app.get(f"{settings.api_prefix}/logs")
async def get_logs(lines: int = 100) -> list[str]:
    return read_recent_logs(lines)


@app.post(f"{settings.api_prefix}/logs/write")
async def write_log(payload: dict[str, str] = Body(default_factory=dict)) -> dict[str, str]:
    message = str(payload.get("message", "")).strip()
    if not message:
        return {"status": "ignored", "message": "empty"}
    log_event(message)
    return {"status": "ok", "message": message}


@app.post(f"{settings.api_prefix}/water/{{zone_id}}")
def water_zone(zone_id: str, volume_ml: int = 180) -> dict[str, object]:
    result = automation.water_zone(zone_id, volume_ml)
    log_event(f"Zone {zone_id} watered with {volume_ml} mL")
    return result


@app.post(f"{settings.api_prefix}/lights/{{mode}}")
async def set_light_mode(mode: str) -> dict[str, object]:
    result = automation.set_light_mode(mode)
    log_event(f"LED mode changed to {mode}")
    return result


@app.post(f"{settings.api_prefix}/lights/mode")
async def set_light_mode_from_body(payload: dict[str, str] = Body(default_factory=dict)) -> dict[str, object]:
    mode = str(payload.get("mode", "schedule")).strip().lower()
    result = automation.set_light_mode(mode)
    log_event(f"LED mode changed to {mode}")
    return result


@app.post(f"{settings.api_prefix}/lights/color")
async def set_light_color(payload: dict[str, int] = Body(default_factory=dict)) -> dict[str, object]:
    red = int(payload.get("r", 0))
    green = int(payload.get("g", 255))
    blue = int(payload.get("b", 128))
    color = (max(0, min(red, 255)), max(0, min(green, 255)), max(0, min(blue, 255)))
    result = automation.set_light_color(color)
    log_event(f"LED color set to {color}")
    return result


@app.post(f"{settings.api_prefix}/lights/brightness")
async def set_light_brightness(payload: dict[str, int] = Body(default_factory=dict)) -> dict[str, object]:
    brightness = int(payload.get("brightness", 75))
    result = automation.set_light_brightness(brightness)
    log_event(f"LED brightness set to {result['brightness']}%")
    return result


@app.get(f"{settings.api_prefix}/zones")
async def list_zones() -> list[dict[str, object]]:
    zones = automation.zones
    return [
        {
            "zone_id": zone.zone_id,
            "name": zone.name,
            "position_mm": zone.position_mm,
            "light_start_time": zone.light_start_time.isoformat(timespec="minutes"),
            "light_stop_time": zone.light_stop_time.isoformat(timespec="minutes"),
            "moisture_target": zone.moisture_target,
            "led_start_index": zone.led_start_index,
            "led_end_index": zone.led_end_index,
        }
        for zone in zones
    ]


@app.post(f"{settings.api_prefix}/zones/{{zone_id}}/plant")
async def update_zone_plant(zone_id: str, payload: dict[str, str] = Body(default_factory=dict)) -> dict[str, object]:
    name = str(payload.get("name", "")).strip()
    result = automation.update_zone_plant(zone_id, name)
    log_event(f"Zone {zone_id} plant name updated to {name}")
    return result


@app.post(f"{settings.api_prefix}/zones/{{zone_id}}/lighting")
async def update_light_schedule(zone_id: str, payload: dict[str, str] = Body(default_factory=dict)) -> dict[str, object]:
    start_time = time.fromisoformat(str(payload.get("start_time", "08:00")))
    stop_time = time.fromisoformat(str(payload.get("stop_time", "20:00")))
    result = automation.update_light_schedule(zone_id, start_time, stop_time)
    log_event(f"Zone {zone_id} light schedule set to {result['light_start_time']} - {result['light_stop_time']}")
    return result


@app.post(f"{settings.api_prefix}/zones/{{zone_id}}/moisture")
async def update_moisture_target(zone_id: str, payload: dict[str, float] = Body(default_factory=dict)) -> dict[str, object]:
    moisture_target = float(payload.get("moisture_target", 45.0))
    result = automation.update_moisture_target(zone_id, moisture_target)
    log_event(f"Zone {zone_id} moisture target set to {result['moisture_target']}%")
    return result


@app.post(f"{settings.api_prefix}/zones/{{zone_id}}/position")
async def set_zone_position(zone_id: str, payload: dict[str, float] = Body(default_factory=dict)) -> dict[str, object]:
    position_mm = float(payload.get("position_mm", 0.0))
    result = automation.set_zone_position(zone_id, position_mm)
    log_event(f"Zone {zone_id} position set to {position_mm} mm")
    return result


@app.post(f"{settings.api_prefix}/zones/{{zone_id}}/move")
def move_to_zone(zone_id: str) -> dict[str, object]:
    return log_motion(automation.move_to_zone(zone_id), f"Move gantry to zone {zone_id}")


@app.post(f"{settings.api_prefix}/gantry/home")
def home_gantry() -> dict[str, object]:
    return log_motion(automation.home_gantry(), "Home gantry")


@app.post(f"{settings.api_prefix}/gantry/move")
def move_gantry(payload: dict[str, float] = Body(default_factory=dict)) -> dict[str, object]:
    distance_mm = float(payload.get("distance_mm", 0.0))
    return log_motion(
        automation.move_gantry_relative(distance_mm), f"Move gantry by {distance_mm} mm"
    )


@app.post(f"{settings.api_prefix}/motion/home/{{axis}}")
def home_axis(axis: str) -> dict[str, object]:
    return log_motion(automation.home_motion_axis(axis), f"Home axis {axis}")


@app.post(f"{settings.api_prefix}/motion/move")
def move_axis(payload: dict[str, float] = Body(default_factory=dict)) -> dict[str, object]:
    x_mm = float(payload.get("x_mm", 0.0))
    y_mm = float(payload.get("y_mm", 0.0))
    z_mm = float(payload.get("z_mm", 0.0))
    return log_motion(
        automation.move_axis_relative(x_mm=x_mm, y_mm=y_mm, z_mm=z_mm),
        f"Manual axis move x={x_mm} y={y_mm} z={z_mm}",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("greenthumb.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
