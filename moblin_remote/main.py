from __future__ import annotations

import asyncio
import logging
import os
import ssl

import websockets
from aiohttp import web

from .assistant_server import AssistantServer
from .http_api import make_app


def _build_ssl_context() -> ssl.SSLContext:
    cert_path = os.environ["MOBLIN_REMOTE_CERT"]
    key_path = os.environ["MOBLIN_REMOTE_KEY"]
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    return context


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    password = os.environ["MOBLIN_REMOTE_PASSWORD"]
    ws_port = int(os.environ.get("MOBLIN_REMOTE_WS_PORT", "443"))
    http_port = int(os.environ.get("MOBLIN_REMOTE_HTTP_PORT", "8990"))

    assistant = AssistantServer(password=password)

    await websockets.serve(assistant.handler, "0.0.0.0", ws_port, ssl=_build_ssl_context())
    logging.info("Listening for the phone on wss://0.0.0.0:%d", ws_port)

    runner = web.AppRunner(make_app(assistant))
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", http_port).start()
    logging.info("Local toast API listening on http://127.0.0.1:%d/toast", http_port)

    await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
