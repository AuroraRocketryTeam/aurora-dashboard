"""
Data sources (CSV, serial and LoRa) are normalized into TelemetryFrame
before being broadcast to the dashboard or being stored.

TODO: definition with IDL of the dashboard - backend interface, along with data types
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field, asdict

@dataclass
class IMUData:
    # Raw acceleration (m/s²)
    acceleration_x: float = 0.0
    acceleration_y: float = 0.0
    acceleration_z: float = 0.0
    # Gyroscope (rad/s)
    angular_velocity_x: float = 0.0
    angular_velocity_y: float = 0.0
    angular_velocity_z: float = 0.0
    # BNO055 fields - we have them in CSV / direct serial
    calibration_sys: int = 0
    calibration_gyro: int = 0
    calibration_accel: int = 0
    calibration_mag: int = 0
    orientation_x: float = 0.0
    orientation_y: float = 0.0
    orientation_z: float = 0.0
    linear_acceleration_x: float = 0.0
    linear_acceleration_y: float = 0.0
    linear_acceleration_z: float = 0.0
    gravity_x: float = 0.0
    gravity_y: float = 0.0
    gravity_z: float = 0.0
    magnetometer_x: float = 0.0
    magnetometer_y: float = 0.0
    magnetometer_z: float = 0.0
    quaternion_w: float = 1.0
    quaternion_x: float = 0.0
    quaternion_y: float = 0.0
    quaternion_z: float = 0.0
    temperature: float = 0.0
    timestamp: float = 0.0


@dataclass
class BarometerData:
    pressure: float = 0.0       # Pa
    temperature: float = 0.0    # °C
    timestamp: float = 0.0


@dataclass
class AccelerometerData:
    acceleration_x: float = 0.0
    acceleration_y: float = 0.0
    acceleration_z: float = 0.0
    timestamp: float = 0.0


@dataclass
class OtherData:
    altitude: float = 0.0      # m
    baro_altitude: float = 0.0 # m
    velocity: float = 0.0      # m/s general velocity
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    velocity_z: float = 0.0
    stage: str = "Inactive"
    latitude: float = 0.0
    longitude: float = 0.0
    rssi: float = 0.0
    snr: float = 0.0
    last_ack_command_id: int = 0


@dataclass
class TelemetryFrame:
    imu: IMUData = field(default_factory=IMUData)
    barometer1: BarometerData = field(default_factory=BarometerData)
    barometer2: BarometerData = field(default_factory=BarometerData)
    accelerometer: AccelerometerData = field(default_factory=AccelerometerData)
    other: OtherData = field(default_factory=OtherData)
    # debugging purposes, do we need this?
    ingested_at: float = field(default_factory=time.time)

    def to_dashboard_json(self) -> dict:
        """ Serialize to JSON for dashboard's handleTelemetry(). """
        return {
            "imu": asdict(self.imu),
            "barometer1": asdict(self.barometer1),
            "barometer2": asdict(self.barometer2),
            "accelerometer": asdict(self.accelerometer),
            "other": asdict(self.other),
        }

    def to_csv_row(self) -> dict:
        """Flatten to a dict suitable for csv.DictWriter.

        Only fields that are actually transmitted in the binary TelemetryPacket
        are included.  Fields available only in direct-serial / CSV-replay mode
        (calibration, orientation, linear_acceleration, gravity, magnetometer,
        quaternions, LIS3DHTR accelerometer, velocity components, SNR) are
        omitted to avoid cluttering the output with permanent zeros.
        """
        imu = self.imu
        b1  = self.barometer1
        b2  = self.barometer2
        oth = self.other
        return {
            "timestamp":          imu.timestamp or self.ingested_at,
            "stage":              oth.stage,
            "acceleration_x":     imu.acceleration_x,
            "acceleration_y":     imu.acceleration_y,
            "acceleration_z":     imu.acceleration_z,
            "angular_velocity_x": imu.angular_velocity_x,
            "angular_velocity_y": imu.angular_velocity_y,
            "angular_velocity_z": imu.angular_velocity_z,
            # Barometers (pressure in Pa, temperature in °C)
            "pressure_baro1":     b1.pressure,
            "temperature_baro1":  b1.temperature,
            "pressure_baro2":     b2.pressure,
            "temperature_baro2":  b2.temperature,
            # Altitude
            "baro_altitude":      oth.baro_altitude,   # relative (m)
            "gps_altitude":       oth.altitude,         # absolute (m)
            # GPS position
            "latitude":           oth.latitude,
            "longitude":          oth.longitude,
            # Velocity
            "velocity":           oth.velocity,         # total velocity (m/s)
            # Radio
            "rssi":               oth.rssi,
        }
