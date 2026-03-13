"""
Serial port data source:

Supported wire formats:
  JSON_LINE   – One JSON object per newline.  Two sub-formats are handled:
                  a) The "unified" format already used by the WebSocket bridge:
                       { "imu": {...}, "barometer1": {...}, ... }
                  b) The ESP32 sensor-array format read by the frontend in serial mode:
                       [{"type":"SENSOR_DATA","content":{"source":"BNO055","sensorData":{...}}}, ...]

  LORA_TEXT   – Human-readable output printed by the LoRa receiver sketch
                (telemetry_lora_receiver.ino).  Parsed with a small state machine.

  LORA_BINARY – Framed binary TelemetryPacket (requires receiver firmware to be
                patched to output framed binary – see FRAMING NOTE below).
                Frame layout:  0xAA 0x55 | 1-byte length | payload | CRC16-LE
                The payload is the raw TelemetryPacket struct (~57 bytes).

  AUTO        – Try to detect the format from the first bytes received.

------ FRAMING NOTE -------------------------------------------------------
To enable LORA_BINARY mode, add the following helper to the receiver
and call it from processTelemetryPacket() in telemetry_lora_receiver.ino:

  void sendBinaryFrame(const TelemetryPacket& pkt) {
    const uint8_t MAGIC[2] = {0xAA, 0x55};
    uint8_t len = sizeof(TelemetryPacket);
    uint16_t crc = calculateCRC16((const uint8_t*)&pkt, len);
    Serial.write(MAGIC, 2);
    Serial.write(&len, 1);
    Serial.write((const uint8_t*)&pkt, len);
    Serial.write((uint8_t*)&crc, 2);
  }
---------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import logging
import re
import struct
import time
from enum import Enum, auto
from typing import AsyncIterator, Optional

import serial_asyncio  # type: ignore

from models.telemetry import (
    AccelerometerData, BarometerData, IMUData, OtherData, TelemetryFrame,
)
from sources.generic_source import DataSource

log = logging.getLogger(__name__)

# ── Binary TelemetryPacket layout (pragma pack(1), little-endian) ──────────
# uint32_t timestamp   (4)
# bool     dataValid   (1)
# float    imu.accel_x (4) … accel_y … accel_z … gyro_x … gyro_y … gyro_z
# float    baro1.pressure (4), baro1.temperature (4)
# float    baro2.pressure (4), baro2.temperature (4)
# float    gps.latitude (4), gps.longitude (4), gps.altitude (4)
# Total = 4+1+6*4+2*2+3*4 = 57 bytes
_TELEM_FMT = "<I?fffffffffffff"   # 1×u32 + 1×bool + 13×f32 = 57 bytes
_TELEM_SIZE = struct.calcsize(_TELEM_FMT)

_FRAME_MAGIC = bytes([0xAA, 0x55])
_FRAME_HEADER_SIZE = 3   # 2 magic + 1 byte length


class SerialFormat(Enum):
    JSON_LINE = auto()
    LORA_TEXT = auto()
    LORA_BINARY = auto()
    AUTO = auto()


def _from_unified_json(data: dict) -> Optional[TelemetryFrame]:
    """ Parse the unified JSON format {imu, barometer1, barometer2, accelerometer, other}. """
    if not any(k in data for k in ("imu", "barometer1", "barometer2", "accelerometer")):
        return None
    ts = time.time()

    def sub(key): return data.get(key) or {}

    raw_imu = sub("imu")
    raw_b1 = sub("barometer1")
    raw_b2 = sub("barometer2")
    raw_acc = sub("accelerometer")
    raw_oth = sub("other")

    imu = IMUData(
        acceleration_x=raw_imu.get("acceleration_x", 0.0),
        acceleration_y=raw_imu.get("acceleration_y", 0.0),
        acceleration_z=raw_imu.get("acceleration_z", 0.0),
        angular_velocity_x=raw_imu.get("angular_velocity_x", 0.0),
        angular_velocity_y=raw_imu.get("angular_velocity_y", 0.0),
        angular_velocity_z=raw_imu.get("angular_velocity_z", 0.0),
        calibration_sys=raw_imu.get("calibration_sys", 0),
        calibration_gyro=raw_imu.get("calibration_gyro", 0),
        calibration_accel=raw_imu.get("calibration_accel", 0),
        calibration_mag=raw_imu.get("calibration_mag", 0),
        orientation_x=raw_imu.get("orientation_x", 0.0),
        orientation_y=raw_imu.get("orientation_y", 0.0),
        orientation_z=raw_imu.get("orientation_z", 0.0),
        linear_acceleration_x=raw_imu.get("linear_acceleration_x", 0.0),
        linear_acceleration_y=raw_imu.get("linear_acceleration_y", 0.0),
        linear_acceleration_z=raw_imu.get("linear_acceleration_z", 0.0),
        gravity_x=raw_imu.get("gravity_x", 0.0),
        gravity_y=raw_imu.get("gravity_y", 0.0),
        gravity_z=raw_imu.get("gravity_z", 0.0),
        magnetometer_x=raw_imu.get("magnetometer_x", 0.0),
        magnetometer_y=raw_imu.get("magnetometer_y", 0.0),
        magnetometer_z=raw_imu.get("magnetometer_z", 0.0),
        quaternion_w=raw_imu.get("quaternion_w", 1.0),
        quaternion_x=raw_imu.get("quaternion_x", 0.0),
        quaternion_y=raw_imu.get("quaternion_y", 0.0),
        quaternion_z=raw_imu.get("quaternion_z", 0.0),
        temperature=raw_imu.get("temperature", 0.0),
        timestamp=raw_imu.get("timestamp", ts),
    )
    b1 = BarometerData(
        pressure=raw_b1.get("pressure", 0.0),
        temperature=raw_b1.get("temperature", 0.0),
        timestamp=raw_b1.get("timestamp", ts),
    )
    b2 = BarometerData(
        pressure=raw_b2.get("pressure", 0.0),
        temperature=raw_b2.get("temperature", 0.0),
        timestamp=raw_b2.get("timestamp", ts),
    )
    acc = AccelerometerData(
        acceleration_x=raw_acc.get("acceleration_x", 0.0),
        acceleration_y=raw_acc.get("acceleration_y", 0.0),
        acceleration_z=raw_acc.get("acceleration_z", 0.0),
        timestamp=raw_acc.get("timestamp", ts),
    )
    other = OtherData(
        altitude=raw_oth.get("altitude", 0.0),
        velocity_x=raw_oth.get("velocity_x", 0.0),
        velocity_y=raw_oth.get("velocity_y", 0.0),
        velocity_z=raw_oth.get("velocity_z", 0.0),
        stage=raw_oth.get("stage", "Inactive"),
        latitude=raw_oth.get("latitude", 0.0),
        longitude=raw_oth.get("longitude", 0.0),
    )
    return TelemetryFrame(imu=imu, barometer1=b1, barometer2=b2,
                          accelerometer=acc, other=other)


def _from_json_sensor_array(items: list) -> Optional[TelemetryFrame]:
    """ Parse [{type:'SENSOR_DATA', content:{source:..., sensorData:{...}}}, ...] """
    imu = IMUData()
    b1 = BarometerData()
    b2 = BarometerData()
    acc = AccelerometerData()
    other = OtherData()
    found = False

    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "SENSOR_DATA":
            log.warning("SerialSource: found %s, expected SENSOR_DATA",
                     item.get("type"))
            continue
        content = item.get("content", {})
        src = content.get("source", "")
        payload = content.get("sensorData", {})
        if not payload:
            log.warning("SerialSource: Empty payload found: %s.", content)
            continue
        found = True

        # Unwrap the object looking for the keys in our dataclasses
        # We might have to provide a translation layer,
        # but PLEASE no!!! Let's try to keep this format consistent.
        if src == "BNO055":
            imu = IMUData(**{k: payload[k] for k in IMUData.__dataclass_fields__ if k in payload})
        elif src == "LIS3DHTR":
            acc = AccelerometerData(**{k: payload[k] for k in AccelerometerData.__dataclass_fields__ if k in payload})
        elif src == "MS561101BA03_":
            b1 = BarometerData(**{k: payload[k] for k in BarometerData.__dataclass_fields__ if k in payload})
        elif src == "MS561101BA03_2":
            # TODO: what is the source for this second barometer?
            b2 = BarometerData(**{k: payload[k] for k in BarometerData.__dataclass_fields__ if k in payload})
        elif src == "GPS":
            for k, v in payload.items():
                if hasattr(other, k):
                    setattr(other, k, v)
        else:
            log.warning("SerialSource: Unknown sensor source: %s", src)

    if not found:
        return None
    if b2 == BarometerData():
        log.warning("serial_source: MS561101BA03_2 not found, mirroring barometer1")
        b2 = b1
    return TelemetryFrame(imu=imu, barometer1=b1, barometer2=b2,
                          accelerometer=acc, other=other)


def _parse_json_line(line: str) -> Optional[TelemetryFrame]:
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    if isinstance(data, list):
        return _from_json_sensor_array(data)
    if isinstance(data, dict):
        return _from_unified_json(data)

    log.warning("SerialSource: invalid JSON line: %s", line)
    return None


class _LoRaTextParser:
    """
    State-machine parser for the human-readable output of telemetry_lora_receiver.ino.

    ========== TELEMETRY PACKET ==========
    Timestamp:     12345 ms
    Data Valid:    YES
    --- IMU ---
    Accel:  X=0.123  Y=-0.456  Z=9.812 m/s²
    Gyro:   X=0.001  Y=-0.002  Z=0.003 rad/s
    --- Barometer 1 ---
    Pressure:    1013.25 hPa
    Temperature: 22.50 °C
    Altitude:    0.00 m (estimated)
    --- Barometer 2 ---
    ...
    --- GPS ---
    Latitude:    45.123456°
    Longitude:   9.654321°
    Altitude:    150.00 m
    Radio: RSSI=-45.0 dBm | SNR=12.0 dB
    ======================================
    """

    _RE_XYZ = re.compile(r"X=([\-\d.]+)\s+Y=([\-\d.]+)\s+Z=([\-\d.]+)")
    _RE_FLOAT = re.compile(r"([\-\d.]+)")
    _RE_RADIO = re.compile(r"RSSI=([\-\d.]+)\s*dBm\s*\|\s*SNR=([\-\d.]+)\s*dB")

    def __init__(self):
        self._in_block = False
        self._state: dict = {}
        self._section: str = ""

    def feed(self, line: str) -> Optional[TelemetryFrame]:
        """Feed one line; returns a TelemetryFrame when a full block is parsed."""
        line = line.strip()

        if "TELEMETRY PACKET" in line and "===" in line:
            self._in_block = True
            self._state = {}
            self._section = ""
            return None

        if not self._in_block:
            return None

        if line.startswith("===") and "TELEMETRY" not in line:
            # End of block
            self._in_block = False
            return self._build_frame()

        if line.startswith("---"):
            self._section = line.lower()
            return None

        s = self._state

        if line.startswith("Timestamp:"):
            m = self._RE_FLOAT.search(line)
            if m:
                s["timestamp_ms"] = float(m.group(1))

        elif line.startswith("Data Valid:"):
            s["data_valid"] = "YES" in line.upper()

        elif line.startswith("Radio:"):
            m = self._RE_RADIO.search(line)
            if m:
                s["rssi"] = float(m.group(1))
                s["snr"] = float(m.group(2))

        elif "imu" in self._section:
            m = self._RE_XYZ.search(line)
            if m:
                x, y, z = float(m.group(1)), float(m.group(2)), float(m.group(3))
                if "Accel" in line:
                    s["accel"] = (x, y, z)
                elif "Gyro" in line:
                    s["gyro"] = (x, y, z)

        elif "barometer 1" in self._section:
            m = self._RE_FLOAT.search(line)
            if m:
                if "Pressure" in line:
                    s["baro1_pressure"] = float(m.group(1))
                elif "Temperature" in line:
                    s["baro1_temp"] = float(m.group(1))
                elif "Altitude" in line and "estimated" in line:
                    s["baro1_altitude"] = float(m.group(1))
            else:
                log.warning("SerialSource: barometer 1 data didn't match regex! %s", self._section)

        elif "barometer 2" in self._section:
            m = self._RE_FLOAT.search(line)
            if m:
                if "Pressure" in line:
                    s["baro2_pressure"] = float(m.group(1))
                elif "Temperature" in line:
                    s["baro2_temp"] = float(m.group(1))
                elif "Altitude" in line and "estimated" in line:
                    s["baro2_altitude"] = float(m.group(1))
            else:
                log.warning("SerialSource: barometer 2 data didn't match regex! %s", self._section)

        elif "gps" in self._section:
            m = self._RE_FLOAT.search(line)
            if m:
                if "Latitude" in line:
                    s["gps_lat"] = float(m.group(1))
                elif "Longitude" in line:
                    s["gps_lon"] = float(m.group(1))
                elif "Altitude" in line:
                    s["gps_alt"] = float(m.group(1))
            else:
                log.warning("SerialSource: GPS data didn't match regex! %s", self._section)

        return None

    def _build_frame(self) -> Optional[TelemetryFrame]:
        s = self._state
        if not s.get("data_valid", False):
            log.debug("SerialSource: invalid data?")
            return None

        ts = s.get("timestamp_ms", 0.0) / 1000.0
        ax, ay, az = s.get("accel", (0.0, 0.0, 0.0))
        gx, gy, gz = s.get("gyro", (0.0, 0.0, 0.0))

        b1_alt = s.get("baro1_altitude", 0.0)
        b2_alt = s.get("baro2_altitude", 0.0)
        avg_alt = (b1_alt + b2_alt) / 2.0

        imu = IMUData(
            acceleration_x=ax, acceleration_y=ay, acceleration_z=az,
            angular_velocity_x=gx, angular_velocity_y=gy, angular_velocity_z=gz,
            timestamp=ts,
        )
        b1 = BarometerData(
            pressure=s.get("baro1_pressure", 0.0),
            temperature=s.get("baro1_temp", 0.0),
            timestamp=ts,
        )
        b2 = BarometerData(
            pressure=s.get("baro2_pressure", 0.0),
            temperature=s.get("baro2_temp", 0.0),
            timestamp=ts,
        )
        acc = AccelerometerData(
            acceleration_x=ax, acceleration_y=ay, acceleration_z=az,
            timestamp=ts,
        )
        other = OtherData(
            altitude=avg_alt,
            latitude=s.get("gps_lat", 0.0),
            longitude=s.get("gps_lon", 0.0),
            rssi=s.get("rssi", 0.0),
            snr=s.get("snr", 0.0),
        )
        return TelemetryFrame(imu=imu, barometer1=b1, barometer2=b2,
                              accelerometer=acc, other=other)


# *** Binary parser ***
# NOTE: doesn't currently work but might be useful in the future.
# Sending data as human-readable looks like HTTP 1.1 --> HTTP2, beware.

def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def _parse_binary_packet(payload: bytes) -> Optional[TelemetryFrame]:
    if len(payload) < _TELEM_SIZE:
        return None
    try:
        fields = struct.unpack(_TELEM_FMT, payload[:_TELEM_SIZE])
    except struct.error:
        return None

    (ts_ms, data_valid,
     ax, ay, az, gx, gy, gz,
     b1p, b1t, b2p, b2t,
     lat, lon, gps_alt) = fields

    if not data_valid:
        return None

    ts = ts_ms / 1000.0
    import math
    baro1_altitude = 44330.0 * (1.0 - math.pow(b1p / 1013.25, 0.1903))
    baro2_altitude = 44330.0 * (1.0 - math.pow(b2p / 1013.25, 0.1903))
    avg_alt = (baro1_altitude + baro2_altitude) / 2.0

    imu = IMUData(
        acceleration_x=ax, acceleration_y=ay, acceleration_z=az,
        angular_velocity_x=gx, angular_velocity_y=gy, angular_velocity_z=gz,
        timestamp=ts,
    )
    b1 = BarometerData(pressure=b1p, temperature=b1t, timestamp=ts)
    b2 = BarometerData(pressure=b2p, temperature=b2t, timestamp=ts)
    acc = AccelerometerData(acceleration_x=ax, acceleration_y=ay, acceleration_z=az, timestamp=ts)
    other = OtherData(
        altitude=avg_alt,
        latitude=lat,
        longitude=lon,
    )
    return TelemetryFrame(imu=imu, barometer1=b1, barometer2=b2,
                          accelerometer=acc, other=other)


class SerialSource(DataSource):
    """
    Read telemetry from a USB serial port.

    Args:
        port:    Serial port path (e.g. /dev/ttyUSB0, COM3)
        baud:    Baud rate (115200 for LoRa receiver)
        fmt:     Wire format (SerialFormat enum). Default: AUTO
    """

    def __init__(self, port: str, baud: int = 115200,
                 fmt: SerialFormat = SerialFormat.AUTO):
        self.port = port
        self.baud = baud
        self.fmt = fmt
        self._reader = None
        self._writer = None

    async def stream(self) -> AsyncIterator[TelemetryFrame]:
        log.info("SerialSource: opening %s @ %d baud (format=%s)",
                 self.port, self.baud, self.fmt.name)
        try:
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self.port, baudrate=self.baud
            )
        except Exception as e:
            log.error("SerialSource: cannot open %s: %s", self.port, e)
            return

        detected_fmt = self.fmt
        text_parser = _LoRaTextParser()
        binary_buf = bytearray()

        async for line_bytes in self._reader:
            line = line_bytes.decode("utf-8", errors="replace")

            # auto dectector
            if detected_fmt == SerialFormat.AUTO:
                stripped = line.strip()
                if stripped.startswith("{") or stripped.startswith("["):
                    detected_fmt = SerialFormat.JSON_LINE
                    log.info("SerialSource: detected JSON_LINE format")
                elif "TELEMETRY PACKET" in stripped:
                    detected_fmt = SerialFormat.LORA_TEXT
                    log.info("SerialSource: detected LORA_TEXT format")
                elif stripped and stripped[0:1] in ("\xaa", "\xAA"):
                    detected_fmt = SerialFormat.LORA_BINARY
                    log.info("SerialSource: detected LORA_BINARY format")
                else:
                    log.warning("SerialSource: detected unknown format: %s", line)
                    continue

            if detected_fmt == SerialFormat.JSON_LINE:
                frame = _parse_json_line(line)
                if frame:
                    yield frame

            elif detected_fmt == SerialFormat.LORA_TEXT:
                frame = text_parser.feed(line)
                if frame:
                    yield frame

            elif detected_fmt == SerialFormat.LORA_BINARY:
                # resize buffer to line
                binary_buf.extend(line_bytes)
                while True:
                    idx = binary_buf.find(_FRAME_MAGIC)
                    if idx == -1:
                        binary_buf.clear()
                        break
                    if idx > 0:
                        del binary_buf[:idx]
                    # need magic(2) + length(1) + at least 1 byte + crc(2)
                    if len(binary_buf) < _FRAME_HEADER_SIZE + 1 + 2:
                        log.warning("SerialSource: unexpected frame header: %s", line)
                        break
                    length = binary_buf[2]
                    total = _FRAME_HEADER_SIZE + length + 2
                    if len(binary_buf) < total:
                        break
                    payload = bytes(binary_buf[_FRAME_HEADER_SIZE: _FRAME_HEADER_SIZE + length])
                    crc_bytes = bytes(binary_buf[_FRAME_HEADER_SIZE + length: total])
                    expected_crc = struct.unpack("<H", crc_bytes)[0]
                    if _crc16(payload) != expected_crc:
                        log.warning("SerialSource: CRC mismatch, dropping frame")
                        del binary_buf[:3]
                        continue
                    frame = _parse_binary_packet(payload)
                    if frame:
                        yield frame
                    del binary_buf[:total]

    async def close(self) -> None:
        if self._writer:
            self._writer.close()
