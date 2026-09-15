from __future__ import annotations

import json
import logging
import socket
from typing import Any

logger = logging.getLogger(__name__)

QUERY_TIMEOUT = 5.0
# gcode/script does not reply until the move completes, so anything that
# physically moves the gantry needs room for the full travel time.
MOTION_TIMEOUT = 180.0


class KlipperClient:
    """Communicate with Klipper via Unix socket."""

    def __init__(self, socket_path: str = "/run/klipper/uds") -> None:
        self.socket_path = socket_path

    def status(self) -> dict[str, Any]:
        response = self._send_command(
            "objects/query", {"objects": {"toolhead": ["position", "homed_axes"]}}
        )
        if not response.get("ok"):
            return {"ok": False, "error": response.get("error"), "position": 0.0, "homed": False}

        toolhead = response.get("result", {}).get("status", {}).get("toolhead", {})
        position = toolhead.get("position") or [0.0]
        return {
            "ok": True,
            "position": round(float(position[0]), 1),
            "homed": "x" in (toolhead.get("homed_axes") or ""),
        }

    def home_gantry(self) -> dict[str, Any]:
        return self._send_gcode("G28 X", timeout=MOTION_TIMEOUT)

    def home_axis(self, axis: str) -> dict[str, Any]:
        letter = axis.strip().upper()
        if letter not in {"X", "Y", "Z"}:
            return {"ok": False, "error": f"Unknown axis: {axis}"}
        return self._send_gcode(f"G28 {letter}", timeout=MOTION_TIMEOUT)

    def move_gantry_relative(self, distance_mm: float) -> dict[str, Any]:
        return self._send_gcode(f"G91\nG1 X{distance_mm} F6000\nG90", timeout=MOTION_TIMEOUT)

    def move_gantry_absolute(self, position_mm: float) -> dict[str, Any]:
        return self._send_gcode(f"G90\nG1 X{position_mm} F6000", timeout=MOTION_TIMEOUT)

    def move_relative(
        self, x_mm: float = 0.0, y_mm: float = 0.0, z_mm: float = 0.0
    ) -> dict[str, Any]:
        axes = "".join(
            f" {name}{value}"
            for name, value in (("X", x_mm), ("Y", y_mm), ("Z", z_mm))
            if value
        )
        if not axes:
            return {"ok": True, "result": {}}
        return self._send_gcode(f"G91\nG1{axes} F6000\nG90", timeout=MOTION_TIMEOUT)

    def _send_gcode(self, gcode: str, timeout: float = QUERY_TIMEOUT) -> dict[str, Any]:
        logger.debug("Sending gcode: %r", gcode)
        return self._send_command("gcode/script", {"script": gcode}, timeout=timeout)

    def _send_command(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = QUERY_TIMEOUT,
    ) -> dict[str, Any]:
        request_id = 1
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(self.socket_path)
            request = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
                "id": request_id,
            }
            sock.sendall((json.dumps(request) + "\x03").encode())

            # Klipper interleaves async notifications with replies on the same
            # socket, so keep reading until the message carrying our id arrives.
            buffer = b""
            try:
                while True:
                    data = sock.recv(4096)
                    if not data:
                        return {"ok": False, "error": "Klipper closed the connection"}
                    buffer += data
                    while b"\x03" in buffer:
                        raw, buffer = buffer.split(b"\x03", 1)
                        message = json.loads(raw.decode())
                        if message.get("id") != request_id:
                            continue
                        if "error" in message:
                            detail = message["error"]
                            text = (
                                detail.get("message", str(detail))
                                if isinstance(detail, dict)
                                else str(detail)
                            )
                            logger.warning("Klipper rejected %s: %s", method, text)
                            return {"ok": False, "error": text}
                        return {"ok": True, "result": message.get("result", {})}
            except socket.timeout:
                logger.warning("Klipper %s timed out after %ss", method, timeout)
                return {"ok": False, "error": f"Klipper did not respond within {timeout:.0f}s"}
            finally:
                sock.close()
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Klipper request failed: %s", exc)
            return {"ok": False, "error": str(exc)}
