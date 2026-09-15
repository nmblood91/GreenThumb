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
        return {"ok": True, "status": "connected"}

    def home_gantry(self) -> dict[str, Any]:
        return self._send_gcode("G28 X")

    def move_gantry_relative(self, distance_mm: float) -> dict[str, Any]:
        gcode = f"G91\nG1 X{distance_mm} F6000\nG90"
        return self._send_gcode(gcode)

    def _send_gcode(self, gcode: str) -> dict[str, Any]:
        return self._send_command("gcode.run_script", {"script": gcode})

    def _send_command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(self.socket_path)
            request = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
            sock.sendall((json.dumps(request) + "\x03").encode())

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
                return json.loads(response_str)
            return {"ok": True}
        except (socket.error, json.JSONDecodeError, OSError) as exc:
            logger.warning("Klipper request failed: %s", exc)
            return {"ok": False, "error": str(exc)}
