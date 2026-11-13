"""Wire format for Moblin's authenticated remote-control protocol, assistant side.

Moblin (the phone, "streamer") dials out to us ("assistant") over a WebSocket.
Messages are JSON objects with exactly one top-level key naming the case, whose
value is an object of that case's fields - this matches Swift's Codable
synthesis for an enum with labeled associated values, e.g.:

    {"hello": {"apiVersion": "0.1", "authentication": {"challenge": "..", "salt": ".."}}}
    {"identified": {"result": {"ok": {}}}}

A case with no associated values still encodes as an empty object, e.g.
{"ok": {}}, not the bare string "ok" - confirmed against the real Swift
implementation (Moblin/RemoteControl/RemoteControl.swift).
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

API_VERSION = "0.1"


def hash_password(challenge: str, salt: str, password: str) -> str:
    """Reproduces Moblin's remoteControlHashPassword(challenge:salt:password:)."""
    first = hashlib.sha256((password + salt).encode()).digest()
    first_b64 = base64.b64encode(first).decode()
    second = hashlib.sha256((first_b64 + challenge).encode()).digest()
    return base64.b64encode(second).decode()


def encode_hello(challenge: str, salt: str) -> str:
    return json.dumps({
        "hello": {
            "apiVersion": API_VERSION,
            "authentication": {"challenge": challenge, "salt": salt},
        }
    })


def encode_identified_ok() -> str:
    return json.dumps({"identified": {"result": {"ok": {}}}})


def encode_identified_wrong_password() -> str:
    return json.dumps({"identified": {"result": {"wrongPassword": {}}}})


def encode_pong() -> str:
    return json.dumps({"pong": {}})


def encode_show_toast_request(request_id: int, title: str, sub_title: str | None, toast_type: str) -> str:
    data: dict[str, Any] = {"title": title, "type": {toast_type: {}}}
    if sub_title is not None:
        data["subTitle"] = sub_title
    return json.dumps({"request": {"id": request_id, "data": {"showToast": data}}})


class ProtocolError(Exception):
    pass


def decode_message(raw: str) -> tuple[str, dict[str, Any]]:
    """Returns (case_name, fields) for a message sent by the streamer."""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"Not valid JSON: {raw!r}") from e
    if not isinstance(obj, dict) or len(obj) != 1:
        raise ProtocolError(f"Expected a single-key object, got: {raw!r}")
    (case_name, fields), = obj.items()
    return case_name, fields or {}


def decode_result(fields: dict[str, Any]) -> str:
    """Extracts the case name out of a RemoteControlResult field, e.g. {"ok": {}} -> "ok"."""
    result = fields.get("result")
    if not isinstance(result, dict) or not result:
        return "error"
    return next(iter(result))
