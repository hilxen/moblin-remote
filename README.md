# moblin-remote

A small always-on bridge that lets anything running on this box pop a native
toast alert on the phone running Moblin - a Twitch chat command, a bitrate
monitor, whatever else shows up later - without any of those producers
knowing about Moblin's remote-control protocol.

```
chat bot          ──┐
bitrate monitor   ──┼──► POST 127.0.0.1:8990/{toast,server-bitrate} ──► moblin-remote ──wss──► phone (Moblin)
(anything else)   ──┘
```

Moblin's authenticated remote control is a streamer/assistant pair: the
phone ("streamer") dials *out* to a WebSocket URL, and the assistant runs
the server. `moblin-remote` plays the assistant role, so the phone just
needs a stable public endpoint to connect to - this box.

This depends on the `showToast` and `setServerBitrate` remote-control
commands in [Moblin](https://github.com/eerimoq/moblin).

## Protocol

Reverse-engineered from `Moblin/RemoteControl/RemoteControl.swift` /
`RemoteControlAssistant.swift` and verified against the real Swift code
(see `tests/test_protocol.py` for a known-answer hash vector). Summary:

- Messages are JSON objects with exactly one top-level key naming the case,
  e.g. `{"hello": {"apiVersion": "0.1", "authentication": {...}}}`. A case
  with no fields still encodes as `{}`, e.g. `{"ok": {}}` - not a bare string.
- Handshake: assistant sends `hello` with a random `challenge`/`salt` ->
  streamer computes `SHA256(SHA256(password + salt).base64 + challenge).base64`
  and sends it back as `identify` -> assistant replies `identified`.
- Streamer sends an app-level `ping` roughly every 30s; reply `pong` or it
  will reconnect.
- Requests/responses are matched by an integer `id`.

## Local dev

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 -m unittest discover -s tests -v
```

Running it locally needs a cert/key pair and a password matching whatever
you put in Moblin's own Settings -> Remote control -> password:

```sh
cp moblin-remote.env.example moblin-remote.env   # edit it
export $(cat moblin-remote.env | xargs)
.venv/bin/python3 -m moblin_remote.main
```

## Deploy

1. One-time cert issuance/renewal via DNS-01 (if your domain is on Route53,
   no port 80 needed):
   ```sh
   certbot certonly --dns-route53 -d your-host.example.com
   ```
2. `scp` this repo to `/home/ubuntu/moblin-remote`, create `.venv`, install
   `requirements.txt`, copy `moblin-remote.env.example` to
   `moblin-remote.env` and fill in the real password + cert paths.
3. Install `moblin-remote.service` to `/etc/systemd/system/`, then
   `systemctl daemon-reload && systemctl enable --now moblin-remote`.
4. On the phone: Settings -> Remote control -> set the same password, and
   under "Streamer" set the Assistant URL to `wss://your-host.example.com:443`.

## `POST /toast`

```json
{"title": "Low quality", "subTitle": "640 kbps", "type": "warning"}
```

`type` is one of `info` / `warning` / `error` (default `info`). `subTitle`
is optional. Returns `503` if the phone isn't currently connected, or didn't
acknowledge within 5s.

## `POST /server-bitrate`

```json
{"bitsPerSecond": 4500000}
```

Feeds a server-side bitrate reading into Moblin's own `setServerBitrate`
status indicator, to sit next to its locally-measured one. `bitsPerSecond`
may be `null` (e.g. to indicate "unknown"). Returns `503` under the same
conditions as `/toast`.

### Estimating server-side bitrate

`bitsPerSecond` is yours to define - `moblin-remote` just relays whatever
you send. A few things worth getting right when computing it:

- Count actual bytes received off the wire over a rolling window, rather
  than reading back whatever target bitrate the encoder negotiated - on a
  degraded connection those two numbers can diverge sharply, and the
  received-byte count is the one that reflects what's really getting
  through.
- Pick a window on the order of what a viewer could notice, e.g. a few
  seconds. Much shorter and it's dominated by individual packet/frame
  bursts; much longer and it smooths away exactly the kind of brief dip
  this indicator exists to catch.
- If you're ingesting over something like SRT, its own connection stats
  (e.g. libsrt's receive-rate counters) already account for retransmits -
  that's often closer to perceived quality than counting raw bytes
  yourself.
- If an off-the-shelf media server sits in the path (MediaMTX, nginx-rtmp,
  etc.), check whether it already exposes a bitrate/throughput metric via
  its own API before measuring it again from scratch.
- Treat "nothing received recently" as `null`, not `0`. `0` reads as "the
  stream crashed to nothing"; `null` reads as "not connected / no data
  yet" - worth keeping distinct in whatever ends up showing this value.

`GET /health` returns `{"phoneConnected": true|false}`.
