from __future__ import annotations

import json
from multiprocessing.connection import Listener

from .dispatcher import dispatch
from .security import initialize, load_key


PIPE_ADDRESS = r"\\.\pipe\paios-windows-capability-v1"


def serve() -> None:
    initialize()
    with Listener(PIPE_ADDRESS, family="AF_PIPE", authkey=load_key()) as listener:
        while True:
            connection = listener.accept()
            try:
                request = connection.recv()
                if request == {"control": "shutdown"}:
                    connection.send({"status": "PASS", "shutdown": True})
                    return
                try:
                    result = dispatch(request)
                    connection.send({"status": "PASS", "result": result})
                except Exception as exc:
                    connection.send({"status": "FAIL", "error": type(exc).__name__})
            finally:
                connection.close()


if __name__ == "__main__":
    serve()
