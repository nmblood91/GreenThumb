from __future__ import annotations

import json
import logging
import socket
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class KlipperClient:
    """Communicate with Klipper via Unix socket."""

    def __init__(self, socket_path: str = "/run/klipper/uds") -> None:
        self.socket_path = socket_path
        self.socket = None

    def status(self) -> dict[str, Any]:
        result = self._send_gcode("M114")
        position = self._parse_position(result)
        return {"ok": True, "position": position}

    def home_gantry(self) -> dict[str, Any]:
        return self._send_gcode("G28 X")

    def move_gantry_relative(self, distance_mm: float) -> dict[str, Any]:
        gcode = f"G91\nG1 X{distance_mm} F6000\nG90"
        return self._send_gcode(gcode)

    def _parse_position(self, response: dict[str, Any]) -> float:
        try:
            msg = response.get("result", "") or ""
            if "X:" in msg:
                x_str = msg.split("X:")[1].split()[0]
                return float(x_str)
        except (ValueError, IndexError, KeyError, AttributeError):
            pass
        return 0.0

    def _send_gcode(self, gcode: str) -> dict[str, Any]:
        logger.info(f"Sending gcode: {repr(gcode)}")
        return self._send_command("gcode/script", {"script": gcode})

    def _send_command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(self.socket_path)
            request = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
            request_json = json.dumps(request) + "\x03"
            logger.info(f"Request: {request_json}")
            sock.sendall(request_json.encode())

            # Read response: Klipper sends messages terminated with 0x03
            response_data = b""
            try:
                while True:
                    data = sock.recv(4096)
                    if not data:
                        break
                    response_data += data
                    if b"\x03" in response_data:
                        break
            except socket.timeout:
                # Timeout is ok for gcode commands that don't return responses
                pass
            finally:
                sock.close()

            if response_data:
                response_str = response_data.decode().split("\x03")[0]
                logger.info(f"Response: {response_str}")
                return json.loads(response_str)
            logger.info("No response data")
            return {"ok": True}
        except (socket.error, json.JSONDecodeError, OSError) as exc:
            logger.warning("Klipper request failed: %s", exc)
            return {"ok": False, "error": str(exc)}
