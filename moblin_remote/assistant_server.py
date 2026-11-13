"""The WebSocket server Moblin's remote-control "streamer" dials into.

Only one phone is ever expected to connect. A new connection replaces
whatever was there before, same as Moblin's own RemoteControlAssistant.
"""

from __future__ import annotations

import asyncio
import logging
import secrets

from . import protocol

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 5


class AssistantServer:
    def __init__(self, password: str) -> None:
        self._password = password
        self._ws = None
        self._identified = False
        self._challenge = ""
        self._salt = ""
        self._next_id = 0
        self._pending: dict[int, asyncio.Future[str]] = {}

    def is_connected(self) -> bool:
        return self._ws is not None and self._identified

    async def handler(self, websocket) -> None:
        if self._ws is not None:
            logger.info("New streamer connection, closing the previous one")
            await self._ws.close()
        self._ws = websocket
        self._identified = False
        self._challenge = secrets.token_urlsafe(16)
        self._salt = secrets.token_urlsafe(16)
        await self._send(protocol.encode_hello(self._challenge, self._salt))
        try:
            async for raw in websocket:
                await self._handle_message(raw)
        finally:
            if self._ws is websocket:
                self._ws = None
                self._identified = False
            for future in self._pending.values():
                if not future.done():
                    future.set_result("error")
            self._pending.clear()
            logger.info("Streamer disconnected")

    async def _handle_message(self, raw: str) -> None:
        try:
            case, fields = protocol.decode_message(raw)
        except protocol.ProtocolError as e:
            logger.warning("Dropping unparseable message: %s", e)
            return

        if case == "identify":
            await self._handle_identify(fields)
        elif case == "ping":
            await self._send(protocol.encode_pong())
        elif case == "response":
            self._handle_response(fields)
        else:
            logger.debug("Ignoring unhandled message case: %s", case)

    async def _handle_identify(self, fields: dict) -> None:
        authentication = fields.get("authentication", "")
        expected = protocol.hash_password(self._challenge, self._salt, self._password)
        if authentication == expected:
            self._identified = True
            await self._send(protocol.encode_identified_ok())
            logger.info("Streamer identified")
        else:
            logger.warning("Streamer sent the wrong password")
            await self._send(protocol.encode_identified_wrong_password())
            await self._ws.close()

    def _handle_response(self, fields: dict) -> None:
        request_id = fields.get("id")
        future = self._pending.pop(request_id, None)
        if future is None or future.done():
            return
        future.set_result(protocol.decode_result(fields))

    async def _send(self, message: str) -> None:
        if self._ws is None:
            return
        await self._ws.send(message)

    async def _send_request_for_ack(self, build_message, label: str) -> bool:
        if not self.is_connected():
            logger.warning("%s dropped, phone not connected", label)
            return False
        request_id = self._next_id
        self._next_id += 1
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await self._send(build_message(request_id))
        try:
            result = await asyncio.wait_for(future, timeout=REQUEST_TIMEOUT_S)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            logger.warning("%s timed out waiting for ack", label)
            return False
        ok = result == "ok"
        if ok:
            logger.info("%s sent", label)
        else:
            logger.warning("%s acked with result=%s", label, result)
        return ok

    async def show_toast(self, title: str, sub_title: str | None = None, toast_type: str = "info") -> bool:
        label = f"Toast {title!r} ({toast_type})" + (f" - {sub_title}" if sub_title else "")
        return await self._send_request_for_ack(
            lambda request_id: protocol.encode_show_toast_request(request_id, title, sub_title, toast_type),
            label,
        )

    async def set_server_bitrate(self, bits_per_second: int | None) -> bool:
        label = f"Server bitrate {bits_per_second}"
        return await self._send_request_for_ack(
            lambda request_id: protocol.encode_set_server_bitrate_request(request_id, bits_per_second),
            label,
        )
