import struct
import sys
import unittest

sys.path.insert(0, ".")

from models.telemetry import TelemetryFrame, IMUData, BarometerData, AccelerometerData, OtherData
from pipeline.recorder import Recorder
from sources.serial_source import (
    _LoRaTextParser, _parse_json_line, _parse_binary_packet,
    _crc16, _TELEM_FMT, _TELEM_SIZE, _from_json_sensor_array,
)


LORA_TEXT_BLOCK = [
    "========== TELEMETRY PACKET ==========",
    "Timestamp:     12000 ms",
    "Data Valid:    YES",
    "--- IMU ---",
    "Accel:  X=1.00  Y=2.00  Z=9.81 m/s²",
    "Gyro:   X=0.10  Y=0.20  Z=0.30 rad/s",
    "--- Barometer 1 ---",
    "Pressure:    1013.25 hPa",
    "Temperature: 22.50 °C",
    "Altitude:    5.00 m (estimated)",
    "--- Barometer 2 ---",
    "Pressure:    1012.00 hPa",
    "Temperature: 22.00 °C",
    "Altitude:    8.00 m (estimated)",
    "--- GPS ---",
    "Latitude:    45.000000°",
    "Longitude:   9.000000°",
    "Altitude:    150.00 m",
    "Radio: RSSI=-45.0 dBm | SNR=12.0 dB",
    "======================================",
]


def make_lora_frame():
    parser = _LoRaTextParser()
    result = None
    for line in LORA_TEXT_BLOCK:
        result = parser.feed(line)
    return result


def make_binary_payload(
    ts_ms=5000, data_valid=True,
    ax=1.0, ay=2.0, az=9.81,
    gx=0.1, gy=0.2, gz=0.3,
    b1p=1013.25, b1t=22.5,
    b2p=1012.0, b2t=22.0,
    lat=45.0, lon=9.0, alt=150.0,
):
    return struct.pack(_TELEM_FMT, ts_ms, data_valid, ax, ay, az, gx, gy, gz,
                       b1p, b1t, b2p, b2t, lat, lon, alt)


class TestTelemetryFrame(unittest.TestCase):
    def test_to_dashboard_json_keys(self):
        f = TelemetryFrame()
        keys = set(f.to_dashboard_json().keys())
        self.assertEqual(keys, {"imu", "barometer1", "barometer2", "accelerometer", "other"})

    def test_to_csv_row_has_timestamp(self):
        f = TelemetryFrame(imu=IMUData(timestamp=42.0))
        self.assertEqual(f.to_csv_row()["timestamp"], 42.0)


class TestRecorder(unittest.TestCase):
    def test_record_and_count(self):
        r = Recorder(maxlen=10)
        for _ in range(5):
            r.record(TelemetryFrame())
        self.assertEqual(r.count, 5)

    def test_maxlen_evicts(self):
        r = Recorder(maxlen=3)
        for _ in range(5):
            r.record(TelemetryFrame())
        self.assertEqual(r.count, 3)

    def test_clear(self):
        r = Recorder(maxlen=10)
        r.record(TelemetryFrame())
        r.clear()
        self.assertEqual(r.count, 0)

    def test_save_raises_when_empty(self):
        r = Recorder()
        with self.assertRaises(ValueError):
            r.save()

    def test_save_csv(self, tmp_path=None):
        import tempfile, os, csv
        r = Recorder()
        r.record(TelemetryFrame(imu=IMUData(timestamp=1.0, acceleration_z=9.81)))
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            r.save(path=path, fmt="csv")
            with open(path) as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertAlmostEqual(float(rows[0]["timestamp"]), 1.0)
        finally:
            os.unlink(path)

    def test_disabled_recorder_does_not_record(self):
        r = Recorder(enabled=False)
        r.record(TelemetryFrame())
        self.assertEqual(r.count, 0)

    def test_stop_start(self):
        r = Recorder()
        r.record(TelemetryFrame())
        r.stop()
        r.record(TelemetryFrame())
        self.assertEqual(r.count, 1)
        r.start()
        r.record(TelemetryFrame())
        self.assertEqual(r.count, 2)


class TestLoRaTextParser(unittest.TestCase):
    def test_parses_full_block(self):
        frame = make_lora_frame()
        self.assertIsNotNone(frame)

    def test_imu_values(self):
        frame = make_lora_frame()
        self.assertAlmostEqual(frame.imu.acceleration_x, 1.0)
        self.assertAlmostEqual(frame.imu.acceleration_z, 9.81)
        self.assertAlmostEqual(frame.imu.angular_velocity_z, 0.30)

    def test_barometers(self):
        frame = make_lora_frame()
        self.assertAlmostEqual(frame.barometer1.pressure, 1013.25)
        self.assertAlmostEqual(frame.barometer2.pressure, 1012.00)

    def test_gps(self):
        frame = make_lora_frame()
        self.assertAlmostEqual(frame.other.latitude, 45.0)
        self.assertAlmostEqual(frame.other.longitude, 9.0)

    def test_rssi_snr(self):
        frame = make_lora_frame()
        self.assertAlmostEqual(frame.other.rssi, -45.0)
        self.assertAlmostEqual(frame.other.snr, 12.0)

    def test_timestamp(self):
        frame = make_lora_frame()
        self.assertAlmostEqual(frame.imu.timestamp, 12.0)

    def test_invalid_block_returns_none(self):
        parser = _LoRaTextParser()
        self.assertIsNone(parser.feed("some random log line"))

    def test_data_invalid_returns_none(self):
        parser = _LoRaTextParser()
        parser.feed("========== TELEMETRY PACKET ==========")
        parser.feed("Timestamp:     1000 ms")
        parser.feed("Data Valid:    NO")
        result = parser.feed("======================================")
        self.assertIsNone(result)

    def test_altitude_average(self):
        frame = make_lora_frame()
        self.assertAlmostEqual(frame.other.altitude, 6.5)


class TestBinaryParser(unittest.TestCase):
    def test_struct_size(self):
        self.assertEqual(_TELEM_SIZE, 57)

    def test_parses_valid_payload(self):
        payload = make_binary_payload()
        frame = _parse_binary_packet(payload)
        self.assertIsNotNone(frame)
        self.assertAlmostEqual(frame.imu.acceleration_z, 9.81, places=4)
        self.assertAlmostEqual(frame.barometer1.pressure, 1013.25, places=4)
        self.assertAlmostEqual(frame.other.latitude, 45.0, places=4)
        self.assertAlmostEqual(frame.imu.timestamp, 5.0, places=4)

    def test_data_invalid_returns_none(self):
        payload = make_binary_payload(data_valid=False)
        self.assertIsNone(_parse_binary_packet(payload))

    def test_short_payload_returns_none(self):
        self.assertIsNone(_parse_binary_packet(b"\x00" * 10))

    def test_crc16(self):
        data = b"\x01\x02\x03\x04"
        self.assertEqual(_crc16(data), _crc16(data))
        self.assertNotEqual(_crc16(data), _crc16(b"\x01\x02\x03\x05"))


class TestJsonLineParser(unittest.TestCase):
    def test_unified_format(self):
        line = '{"imu":{"acceleration_x":1.0,"acceleration_z":9.81},"barometer1":{"pressure":1013.0},"barometer2":{},"accelerometer":{}}'
        frame = _parse_json_line(line)
        self.assertIsNotNone(frame)
        self.assertAlmostEqual(frame.imu.acceleration_z, 9.81)
        self.assertAlmostEqual(frame.barometer1.pressure, 1013.0)

    def test_invalid_json_returns_none(self):
        self.assertIsNone(_parse_json_line("not json"))

    def test_empty_line_returns_none(self):
        self.assertIsNone(_parse_json_line(""))

    def test_sensor_array_bno055(self):
        line = '[{"type":"SENSOR_DATA","content":{"source":"BNO055","sensorData":{"acceleration_z":9.81}}}]'
        frame = _parse_json_line(line)
        self.assertIsNotNone(frame)
        self.assertAlmostEqual(frame.imu.acceleration_z, 9.81)

    def test_sensor_array_b2_mirrors_b1_with_warning(self):
        line = '[{"type":"SENSOR_DATA","content":{"source":"MS561101BA03_","sensorData":{"pressure":1013.0}}}]'
        frame = _parse_json_line(line)
        self.assertAlmostEqual(frame.barometer2.pressure, frame.barometer1.pressure)

    def test_sensor_array_b2_independent(self):
        line = ('[{"type":"SENSOR_DATA","content":{"source":"MS561101BA03_","sensorData":{"pressure":1013.0}}},'
                ' {"type":"SENSOR_DATA","content":{"source":"MS561101BA03_2","sensorData":{"pressure":999.0}}}]')
        frame = _parse_json_line(line)
        self.assertAlmostEqual(frame.barometer1.pressure, 1013.0)
        self.assertAlmostEqual(frame.barometer2.pressure, 999.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
