from __future__ import annotations

from multiprocessing.connection import Client

from .security import issue_token, load_key
from .server import PIPE_ADDRESS


def call(task_id: str, capability: str, params: dict, approval: dict | None = None) -> dict:
    token = issue_token(task_id, capability, params)
    envelope = {"task_id": task_id, "capability": capability, "params": params, **token}
    if approval:
        envelope["approval"] = approval
    return _send(envelope)


def call_approved(task_id: str, capability: str, params: dict) -> dict:
    token = issue_token(task_id, capability, params)
    envelope = {
        "task_id": task_id, "capability": capability, "params": params, **token,
        "approval": {"canonical_sha256": token["canonical_sha256"], "expires_at": token["expires_at"]},
    }
    return _send(envelope)


def _send(envelope: dict) -> dict:
    connection = Client(PIPE_ADDRESS, family="AF_PIPE", authkey=load_key())
    try:
        connection.send(envelope)
        return connection.recv()
    finally:
        connection.close()


def shutdown() -> dict:
    connection = Client(PIPE_ADDRESS, family="AF_PIPE", authkey=load_key())
    try:
        connection.send({"control": "shutdown"})
        return connection.recv()
    finally:
        connection.close()
