"""
Reads a CSV produced by the existing simulation pipeline
and replays it at the original timing, or at a user-specified speed factor.

Expected CSV columns:
  timestamp, stage, calibration_*, orientation_*, angular_velocity_*,
  linear_acceleration_*, acceleration_*, gravity_*, magnetometer_*,
  quaternion_*, pressure, temperature, altitude, velocity_*
"""

import asyncio
import csv
import logging
from typing import AsyncIterator

from models.telemetry import (
    TelemetryFrame, IMUData, BarometerData, AccelerometerData, OtherData,
)
from sources.generic_source import DataSource

log = logging.getLogger(__name__)


def _float(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row[key])
    except (KeyError, ValueError, TypeError):
        return default


def _int(row: dict, key: str, default: int = 0) -> int:
    try:
        return int(float(row[key]))
    except (KeyError, ValueError, TypeError):
        return default


def _csv_row_to_frame(row: dict) -> TelemetryFrame:
    ts = _float(row, "timestamp")
    imu = IMUData(
        acceleration_x=_float(row, "acceleration_x"),
        acceleration_y=_float(row, "acceleration_y"),
        acceleration_z=_float(row, "acceleration_z"),
        angular_velocity_x=_float(row, "angular_velocity_x"),
        angular_velocity_y=_float(row, "angular_velocity_y"),
        angular_velocity_z=_float(row, "angular_velocity_z"),
        calibration_sys=_int(row, "calibration_sys", 3),
        calibration_gyro=_int(row, "calibration_gyro", 3),
        calibration_accel=_int(row, "calibration_accel", 3),
        calibration_mag=_int(row, "calibration_mag", 3),
        orientation_x=_float(row, "orientation_x"),
        orientation_y=_float(row, "orientation_y"),
        orientation_z=_float(row, "orientation_z"),
        linear_acceleration_x=_float(row, "linear_acceleration_x"),
        linear_acceleration_y=_float(row, "linear_acceleration_y"),
        linear_acceleration_z=_float(row, "linear_acceleration_z"),
        gravity_x=_float(row, "gravity_x"),
        gravity_y=_float(row, "gravity_y"),
        gravity_z=_float(row, "gravity_z"),
        magnetometer_x=_float(row, "magnetometer_x"),
        magnetometer_y=_float(row, "magnetometer_y"),
        magnetometer_z=_float(row, "magnetometer_z"),
        quaternion_w=_float(row, "quaternion_w", 1.0),
        quaternion_x=_float(row, "quaternion_x"),
        quaternion_y=_float(row, "quaternion_y"),
        quaternion_z=_float(row, "quaternion_z"),
        temperature=_float(row, "temperature"),
        timestamp=ts,
    )
    b1 = BarometerData(
        pressure=_float(row, "pressure"),
        temperature=_float(row, "temperature"),
        timestamp=ts,
    )
    b2 = BarometerData(
        pressure=_float(row, "pressure"),
        temperature=_float(row, "temperature"),
        timestamp=ts,
    )
    acc = AccelerometerData(
        acceleration_x=_float(row, "acceleration_x"),
        acceleration_y=_float(row, "acceleration_y"),
        acceleration_z=_float(row, "acceleration_z"),
        timestamp=ts,
    )
    other = OtherData(
        altitude=_float(row, "altitude"),
        velocity_x=_float(row, "velocity_x"),
        velocity_y=_float(row, "velocity_y"),
        velocity_z=_float(row, "velocity_z"),
        stage=row.get("stage", "Inactive"),
    )
    return TelemetryFrame(imu=imu, barometer1=b1, barometer2=b2,
                          accelerometer=acc, other=other)


class FileSource(DataSource):
    def __init__(self, path: str, loop: bool = False, speed: float = 1.0):
        """
        Args:
            path:  CSV file path
            loop:  If True, restart from the beginning
            speed: Playback speed multiplier
        """
        self.path = path
        self.loop = loop
        self.speed = max(speed, 0.001)

    def _load(self) -> list[dict]:
        try:
            with open(self.path, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except Exception as exc:
            log.error("file_source: cannot read %s: %s", self.path, exc)
            return []

    async def stream(self) -> AsyncIterator[TelemetryFrame]:
        while True:
            rows = self._load()
            if not rows:
                log.error("No data in %s", self.path)
                await asyncio.sleep(1)
                continue

            log.info("file_source: replaying %d rows from %s (speed=%.1f×)",
                     len(rows), self.path, self.speed)

            # emitting rows
            for i, row in enumerate(rows):
                frame = _csv_row_to_frame(row)
                yield frame

                if i < len(rows) - 1:
                    ts_now = _float(row, "timestamp")
                    ts_next = _float(rows[i + 1], "timestamp")
                    dt = (ts_next - ts_now) / self.speed

                    # adjust playback speed to be congruent with frames
                    # NOTE: the dashboard doesn't care about the
                    # frames' timestamps, so if this breaks, the
                    # representation is flawed...

                    if 0 < dt <= 1.0:
                        await asyncio.sleep(dt)
                    else:
                        await asyncio.sleep(0.01 / self.speed)

            # finished rows
            if not self.loop:
                log.info("file_source: playback complete")
                return

            log.info("file_source: restarting playback")
