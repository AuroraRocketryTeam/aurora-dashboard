"""
Aurora Ground Station Backend

Usage examples:
  # Replay a simulation CSV
  python main.py --source file --file ../src/simulation_data.csv

  # Replay at 3× speed, no loop
  python main.py --source file --file ../src/simulation_data.csv --speed 3 --no-loop

  # LoRa receiver connected via USB (try to auto-detect wire format)
  python main.py --source serial --port /dev/ttyUSB0

  # LoRa receiver with explicit text format
  python main.py --source serial --port /dev/ttyUSB0 --serial-format lora_text

  # LoRa receiver with framed binary
  python main.py --source serial --port /dev/ttyUSB0 --serial-format lora_binary

  # Direct serial connection to flight computer
  python main.py --source serial --port COM3 --baud 115200 --serial-format json_line

  # Only broadcast, disable in-memory recording
  python main.py --source serial --port /dev/ttyUSB0 --no-record
"""

import argparse
import asyncio
import logging
import sys

from pipeline.recorder import Recorder
from server.ws_server import WSServer
from sources.file_source import FileSource
from sources.serial_source import SerialFormat, SerialSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Aurora Ground Station Telemetry Backend",
        # prevents argparse from changing our formatting
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Source
    p.add_argument("--source", choices=["file", "serial"], default="file",
                   help="Data source type (default: file)")

    # File source options
    p.add_argument("--file", default="../src/simulation_data.csv",
                   help="Path to CSV file")
    p.add_argument("--loop", action="store_true",
                   help="Loop CSV playback")
    p.add_argument("--speed", type=float, default=1.0,
                   help="CSV playback speed multiplier (default: 1.0)")

    # Serial source options
    p.add_argument("--port", default="/dev/ttyUSB0",
                   help="Serial port (default: /dev/ttyUSB0)")
    p.add_argument("--baud", type=int, default=115200,
                   help="Baud rate (default: 115200)")
    p.add_argument("--serial-format",
                   choices=["auto", "json_line", "lora_text", "lora_binary"],
                   default="auto",
                   help="Wire format for serial source (default: auto)")

    # Server options
    p.add_argument("--ws-host", default="localhost",
                   help="Bind host (default: localhost)")
    p.add_argument("--ws-port", type=int, default=8081,
                   help="Bind port (default: 8081)")

    # Recording options
    p.add_argument("--no-record", action="store_true",
                   help="Disable in-memory recording")
    p.add_argument("--buffer-size", type=int, default=100_000,
                   help="Max frames to keep in memory (default: 100.000)")
    p.add_argument("--autosave-every", type=int, default=0, metavar="N",
                   help="Autosave buffer to CSV every N frames (0: disabled)")

    return p


def create_source(args):
    if args.source == "file":
        return FileSource(
            path=args.file,
            loop=args.loop,
            speed=args.speed,
        )
    if args.source == "serial":
        _map = {
            "auto": SerialFormat.AUTO,
            "json_line": SerialFormat.JSON_LINE,
            "lora_text": SerialFormat.LORA_TEXT,
            "lora_binary": SerialFormat.LORA_BINARY,
        }
        return SerialSource(
            port=args.port,
            baud=args.baud,
            fmt=_map[args.serial_format],
        )
    raise ValueError(f"Unknown source: {args.source}")


async def run(args) -> None:
    source = create_source(args)
    recorder = Recorder(
        maxlen=args.buffer_size,
        enabled=not args.no_record,
        autosave_every=args.autosave_every,
    )
    server = WSServer(
        host=args.ws_host,
        port=args.ws_port,
        recorder=recorder,
    )

    log.info("Source   : %s", args.source)
    log.info("Recording: %s  (buffer=%d frames)",
             "ON" if not args.no_record else "OFF", args.buffer_size)
    log.info("WebSocket: ws://%s:%d", args.ws_host, args.ws_port)

    # actual pipeline definition
    async def ingest() -> None:
        async for frame in source.stream():
            recorder.record(frame)
            await server.broadcast(frame.to_dashboard_json())

    try:
        await asyncio.gather(server.start(), ingest())
    except asyncio.CancelledError:
        pass
    finally:
        await source.close()
        log.info("Shutdown complete. Buffered frames: %d", recorder.count)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        log.info("Stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
