"""
Interface to the dashboard.

TODO: definition with IDL of the dashboard - backend interface, along with data types
Protocol:
  Server → Dashboard frame:
    JSON: { imu, barometer1, barometer2, accelerometer, other }

  Dashboard → Server commands:
    { "command": "save", "format": "csv"/"json", "path" ? "out.csv" : auto }
    - save to optional path
    { "command": "status" }
    - get recorder status
    { "command": "clear" }
    - clear recorder buffer
    { "command": "stop_recording" }
    - pause recording
    { "command": "start_recording" }
    - resume recording
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional, Set

import websockets
from websockets.server import WebSocketServerProtocol

from pipeline.recorder import Recorder
from typing import Callable, Any

log = logging.getLogger(__name__)


class WSServer:
    def __init__(self, host: str = "localhost", port: int = 8081,
                 recorder: Optional[Recorder] = None,
                 on_uplink_command: Optional[Callable[[int], Any]] = None):
        self.host = host
        self.port = port
        self.recorder = recorder or Recorder(enabled=False)
        self._on_uplink_command = on_uplink_command
        # multiple clients :)
        # so that we can broadcast our dashboard.
        # TODO: is a separate relay necessary for broadcasting?
        self._clients: Set[WebSocketServerProtocol] = set()

    # *** API ***

    async def start(self) -> None:
        log.info("WSServer: listening on ws://%s:%d", self.host, self.port)
        async with websockets.serve(self._handler, self.host, self.port):
            await asyncio.Future()  # block forever

    async def broadcast(self, data: dict) -> None:
        """ Sends a telemetry frame to all connected clients. """
        if not self._clients:
            return
        message = json.dumps(data)
        # asyncio.gather sends everything at once
        await asyncio.gather(
            *(ws.send(message) for ws in self._clients),
            return_exceptions=True,
        )

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # *** internal ***

    async def _handler(self, ws: WebSocketServerProtocol) -> None:
        self._clients.add(ws)
        log.info("WSServer: client connected %s  (total=%d)",
                 ws.remote_address, len(self._clients))
        try:
            async for raw in ws:
                await self._handle_command(ws, raw)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(ws)
            log.info("WSServer: client disconnected %s  (total=%d)",
                     ws.remote_address, len(self._clients))

    async def _handle_command(self, ws: WebSocketServerProtocol, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send(json.dumps({"error": "invalid JSON"}))
            return

        cmd = msg.get("command", "").lower()
        if cmd == "save":
            path = msg.get("path")
            fmt = msg.get("format", "csv")
            try:
                saved_path = self.recorder.save(path=path, fmt=fmt)
                await ws.send(json.dumps({"ok": True, "saved_to": saved_path,
                                          "frames": self.recorder.count}))
            except Exception as exc:
                await ws.send(json.dumps({"error": str(exc)}))

        elif cmd == "status":
            await ws.send(json.dumps({"status": self.recorder.status()}))

        elif cmd == "clear":
            self.recorder.clear()
            await ws.send(json.dumps({"ok": True, "message": "buffer cleared"}))

        elif cmd == "stop_recording":
            self.recorder.stop()
            await ws.send(json.dumps({"ok": True, "recording": False}))

        elif cmd == "start_recording":
            self.recorder.start()
            await ws.send(json.dumps({"ok": True, "recording": True}))

        elif cmd == "transmit":
            _COMMAND_IDS = {"PING": 0x01, "ABORT": 0x02, "EMERG_CHUTE_OPEN": 0x03}
            command_name = str(msg.get("command_id", "")).upper()
            command_id = _COMMAND_IDS.get(command_name)
            if command_id is None:
                await ws.send(json.dumps({"error": f"unknown command: {command_name!r}",
                                          "available": list(_COMMAND_IDS.keys())}))
            elif self._on_uplink_command is None:
                await ws.send(json.dumps({"error": "uplink not available (no serial source)"}))
            else:
                await self._on_uplink_command(command_id)
                await ws.send(json.dumps({"ok": True, "command_id": command_name}))

        else:
            await ws.send(json.dumps({"error": f"unknown command: {cmd!r}"}))
