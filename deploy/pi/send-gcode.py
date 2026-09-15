#!/usr/bin/env python3
"""Send a gcode command to Klipper and print everything it says back.

    ./send-gcode.py QUERY_ENDSTOPS
    ./send-gcode.py "FORCE_MOVE STEPPER=stepper_x DISTANCE=10 VELOCITY=20"

Klipper reports the output of commands like QUERY_ENDSTOPS separately from the
RPC result, and only to connections that have subscribed to gcode output, so
this subscribes first and drains anything still in flight after the reply.
"""

import json
import socket
import sys

SOCKET_PATH = "/run/klipper/uds"
OUTPUT_KEY = "gcode_output"
DRAIN_SECONDS = 0.5


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    script = " ".join(sys.argv[1:])
    timeout = 180.0 if script.upper().startswith(("G28", "G1", "G0")) else 10.0

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(SOCKET_PATH)
    except OSError as exc:
        print(f"Cannot reach Klipper at {SOCKET_PATH}: {exc}")
        return 1

    def send(payload: dict) -> None:
        sock.sendall((json.dumps(payload) + "\x03").encode())

    def finish(code: int) -> int:
        if code == 0:
            print(f"{script}: ok")
        return code

    send({
        "id": 0,
        "method": "gcode/subscribe_output",
        "params": {"response_template": {"key": OUTPUT_KEY}},
    })
    send({
        "jsonrpc": "2.0",
        "method": "gcode/script",
        "params": {"script": script},
        "id": 1,
    })

    buffer = b""
    outcome: int | None = None
    try:
        while True:
            try:
                data = sock.recv(4096)
            except socket.timeout:
                if outcome is None:
                    print(f"No reply within {timeout:.0f}s")
                    return 1
                return finish(outcome)

            if not data:
                if outcome is None:
                    print("Klipper closed the connection")
                    return 1
                return finish(outcome)

            buffer += data
            while b"\x03" in buffer:
                raw, buffer = buffer.split(b"\x03", 1)
                message = json.loads(raw.decode())

                if message.get("key") == OUTPUT_KEY:
                    print(message.get("params", {}).get("response", "").rstrip())
                elif message.get("id") == 1:
                    if "error" in message:
                        print(f"ERROR: {message['error'].get('message', message['error'])}")
                        outcome = 1
                    else:
                        outcome = 0
                    # Output can still be in flight behind the reply.
                    sock.settimeout(DRAIN_SECONDS)
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
