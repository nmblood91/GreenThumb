#!/usr/bin/env python3
"""Send a gcode command to Klipper and print everything it says back.

    ./send-gcode.py QUERY_ENDSTOPS
    ./send-gcode.py "SET_TMC_FIELD STEPPER=stepper_x FIELD=SGTHRS VALUE=90"

Klipper answers commands like QUERY_ENDSTOPS with an async notification rather
than in the RPC result, so both have to be read off the socket.
"""

import json
import socket
import sys

SOCKET_PATH = "/run/klipper/uds"


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

    request = {
        "jsonrpc": "2.0",
        "method": "gcode/script",
        "params": {"script": script},
        "id": 1,
    }
    sock.sendall((json.dumps(request) + "\x03").encode())

    buffer = b""
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                print("Klipper closed the connection")
                return 1
            buffer += data
            while b"\x03" in buffer:
                raw, buffer = buffer.split(b"\x03", 1)
                message = json.loads(raw.decode())
                if message.get("method") == "notify_gcode_response":
                    print("".join(message.get("params", [])))
                elif message.get("id") == 1:
                    if "error" in message:
                        print(f"ERROR: {message['error'].get('message', message['error'])}")
                        return 1
                    print(f"{script}: ok")
                    return 0
    except socket.timeout:
        print(f"No reply within {timeout:.0f}s")
        return 1
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
