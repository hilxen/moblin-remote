"""Local-only fan-in for anything that wants to push a toast or a server-side
bitrate reading to the phone.

Bound to 127.0.0.1 - never exposed publicly. Any process on the same box
(twitch-delay-bot's chat commands, bitrate-alert-watcher, ad-hoc curl for
testing) just POSTs here; none of them need to know about Moblin's
remote-control protocol or manage the connection themselves.
"""

from __future__ import annotations

from aiohttp import web

from .assistant_server import AssistantServer

TOAST_TYPES = {"info", "warning", "error"}


def make_app(assistant: AssistantServer) -> web.Application:
    app = web.Application()

    async def post_toast(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except ValueError:
            return web.json_response({"error": "Body must be JSON"}, status=400)

        title = body.get("title")
        if not isinstance(title, str) or not title:
            return web.json_response({"error": "'title' is required"}, status=400)

        sub_title = body.get("subTitle")
        if sub_title is not None and not isinstance(sub_title, str):
            return web.json_response({"error": "'subTitle' must be a string"}, status=400)

        toast_type = body.get("type", "info")
        if toast_type not in TOAST_TYPES:
            return web.json_response({"error": f"'type' must be one of {sorted(TOAST_TYPES)}"}, status=400)

        ok = await assistant.show_toast(title=title, sub_title=sub_title, toast_type=toast_type)
        if not ok:
            return web.json_response({"error": "Phone not connected or did not acknowledge"}, status=503)
        return web.json_response({"ok": True})

    async def post_server_bitrate(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except ValueError:
            return web.json_response({"error": "Body must be JSON"}, status=400)

        bits_per_second = body.get("bitsPerSecond")
        if bits_per_second is not None and not isinstance(bits_per_second, int):
            return web.json_response({"error": "'bitsPerSecond' must be an integer or null"}, status=400)

        ok = await assistant.set_server_bitrate(bits_per_second)
        if not ok:
            return web.json_response({"error": "Phone not connected or did not acknowledge"}, status=503)
        return web.json_response({"ok": True})

    async def get_health(_request: web.Request) -> web.Response:
        return web.json_response({"phoneConnected": assistant.is_connected()})

    app.router.add_post("/toast", post_toast)
    app.router.add_post("/server-bitrate", post_server_bitrate)
    app.router.add_get("/health", get_health)
    return app
