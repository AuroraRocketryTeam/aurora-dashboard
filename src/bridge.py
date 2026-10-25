# This file implements a WebSocket server that broadcasts telemetry data
# to connected clients. It can source data from a CSV file, generate synthetic
# data for simulation, or read real-time data from a serial port.

import asyncio
import websockets
import serial
import json
import random
import math
import time
import argparse
import pandas as pd
from enum import Enum

# Enum to define the current mode of operation for the telemetry bridge
class Source(Enum):
    FILE = 1    # Replay data from a CSV file
    RANDOM = 2  # Generate random synthetic data
    SERIAL = 3  # Read real-time data from a USB/Serial device

# Initialize Argument Parser for dynamic configuration through command line
parser = argparse.ArgumentParser(description="Rocket Telemetry WebSocket Bridge")

# Parse of the Source Argument (default: FILE)
parser.add_argument(
    "--source", 
    type=str, 
    default="FILE", 
    choices=["FILE", "RANDOM", "SERIAL"],
    help="The source of the telemetry data."
)

# Parse of the File Argument (default: src/simulation_data.csv)
parser.add_argument(
    "--file", 
    type=str, 
    default="src/simulation_data.csv", 
    help="Path to the CSV file used in FILE mode."
)

# 3. Parse of the Serial Port Argument (default: COM3)
parser.add_argument(
    "--port", 
    type=str, 
    default="COM3", 
    help="The serial port to listen on (only used in SERIAL mode)."
)

# Parse arguments and apply configurations
args = parser.parse_args()

SERIAL_PORT = args.port
BAUD_RATE = 9600
SIMULATION_FILE = args.file

# Convert string argument to Enum safely
if args.source.upper() in Source.__members__:
    DATA_SOURCE = Source[args.source.upper()]
else:
    DATA_SOURCE = Source.FILE

# Global set to keep track of currently connected WebSocket clients
connected_clients = set()

# Standard rocket flight stages for state tracking.
# Values match the firmware RocketState enum (atlas-esp-idf FlightState.hpp),
# which is what TelemetryTask sends in the flight_phase byte over LoRa.
class Stage(Enum):
    INACTIVE = 0
    CALIBRATING = 1
    GROUND_SERVICES = 2
    READY_FOR_LAUNCH = 3
    LAUNCH = 4
    ACCELERATED_FLIGHT = 5
    BALLISTIC_FLIGHT = 6
    APOGEE = 7
    STABILIZATION = 8
    DECELERATION = 9
    LANDING = 10
    RECOVERED = 11

# ==========================================
# WEBSOCKET SERVER LOGIC
# ==========================================

async def handler(websocket):
    """
    Handles incoming WebSocket connections.
    Registers the client, waits for disconnection, and unregisters it.
    """
    print(f"Client connected: {websocket.remote_address}")
    connected_clients.add(websocket)
    try:
        # Keep the connection open until the client disconnects
        await websocket.wait_closed()
    finally:
        # cleanup when connection drops
        connected_clients.remove(websocket)
        print(f"Client disconnected: {websocket.remote_address}")

async def broadcast(data):
    """
    Serializes data to JSON and sends it to all connected clients concurrently.
    """
    if not connected_clients:
        return
        
    message = json.dumps(data)
    
    # Create a list of send coroutines for all clients
    websockets_to_send = [ws.send(message) for ws in connected_clients]
    
    # Run all send operations concurrently, ignoring individual errors
    await asyncio.gather(*websockets_to_send, return_exceptions=True)

# ==========================================
# DATA PRODUCTION LOGIC
# ==========================================

async def data_producer():
    """
    The main loop that generates or reads telemetry data and triggers the broadcast.
    Behavior changes based on the global DATA_SOURCE configuration.
    """
    print(f"Bridge Started. Simulation Mode: {DATA_SOURCE.name}")
    
    # Serial Connection Setup
    if DATA_SOURCE == Source.SERIAL:
        ser = None
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        except Exception as e:
            print(f"Error opening serial port {SERIAL_PORT}: {e}")
            return

    # File Reader Setup
    if DATA_SOURCE == Source.FILE:
        df = None
        try:
            # Optimization: Read the file into memory once at startup to avoid disk I/O lag during the loop.
            df = pd.read_csv(SIMULATION_FILE)
            print(f"Loaded {len(df)} rows from simulation file.")
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return

    if DATA_SOURCE == Source.RANDOM:
        # These variables track the physics state when in RANDOM mode
        t = 0
        stage = Stage.INACTIVE
        altitude = 0
        velocity = 0

    while True:
        telemetry = {}

        if DATA_SOURCE == Source.RANDOM:
            # Increment time step (approx 10Hz simulation rate)
            t += 0.1
            
            # Reset simulation logic for looping demonstration
            if t > 70:
                t = 0
                altitude = 0
                velocity = 0

            # Determine flight stage based on hardcoded time thresholds
            if t < 5: stage = Stage.INACTIVE
            elif t < 10: stage = Stage.CALIBRATING
            elif t < 15: stage = Stage.READY_FOR_LAUNCH
            elif t < 18: stage = Stage.LAUNCH
            elif t < 25: stage = Stage.ACCELERATED_FLIGHT
            elif t < 35: stage = Stage.BALLISTIC_FLIGHT
            elif t < 40: stage = Stage.APOGEE
            elif t < 50: stage = Stage.STABILIZATION
            elif t < 60: stage = Stage.LANDING
            else: stage = Stage.RECOVERED

            current_stage = stage

            # LAUNCH..APOGEE: ascent phases
            if Stage.LAUNCH.value <= stage.value <= Stage.APOGEE.value:
                # If stage is 4 (Accelerated Flight), we add thrust (in this case 10g=98 m/s²)
                # Otherwise, just gravity (-1g = -9.8 m/s^2).
                velocity += 98 * 0.1 if stage == Stage.ACCELERATED_FLIGHT else -9.8 * 0.1
                altitude += velocity * 0.1
            
            # After APOGEE: Descent (Parachute deployment simplified)
            elif stage.value > Stage.APOGEE.value and altitude > 0:
                velocity = -5
                altitude += velocity * 0.1
            
            # Clamp altitude to ground level
            if altitude < 0: altitude = 0

            # Generate Synthetic Sensor Data
            timestamp = time.time()
            
            # Simulation of IMU data
            imu = {
                "calibration_sys": 3, "calibration_gyro": 3, "calibration_accel": 3, "calibration_mag": 3,
                # Simulate spinning motion based on time
                "orientation_x": round(math.sin(t)*180, 2), 
                "orientation_y": round(math.cos(t)*180, 2), 
                "orientation_z": round(t % 360, 2),
                # Add noise to sensor readings
                "angular_velocity_x": round(random.uniform(-1, 1), 3),
                "angular_velocity_y": round(random.uniform(-1, 1), 3),
                "angular_velocity_z": round(random.uniform(-1, 1), 3),
                "linear_acceleration_x": round(random.uniform(-0.5, 0.5), 2),
                "linear_acceleration_y": round(random.uniform(-0.5, 0.5), 2),
                "linear_acceleration_z": round(velocity/10 + 9.8, 2),
                "acceleration_x": round(random.uniform(-0.5, 0.5), 2),
                "acceleration_y": round(random.uniform(-0.5, 0.5), 2),
                "acceleration_z": round(velocity/10 + 9.8, 2),
                "gravity_x": 0, "gravity_y": 0, "gravity_z": 9.81,
                "magnetometer_x": round(random.uniform(-50, 50), 1),
                "magnetometer_y": round(random.uniform(-50, 50), 1),
                "magnetometer_z": round(random.uniform(-50, 50), 1),
                "quaternion_w": 0.9, "quaternion_x": 0.1, "quaternion_y": 0.0, "quaternion_z": 0.0,
                "temperature": round(35 + random.uniform(-1, 1), 1),
                "timestamp": timestamp
            }

            # Simulation of barometers data with uniform sensor noise
            # Standard Barometric Formula approximation for Pressure vs Altitude
            pressure_base = 101325 * (1 - 2.25577e-5 * altitude)**5.25588
            baro1 = { 
                "pressure": round(pressure_base + random.uniform(-10, 10), 2),
                "temperature": round(25 - altitude/100, 1),
                "timestamp": timestamp 
            }
            baro2 = { 
                "pressure": round(pressure_base + random.uniform(-10, 10), 2), 
                "temperature": round(25 - altitude/100, 1), 
                "timestamp": timestamp 
            }

            # Simulation of accelerometer data
            accel = { 
                "acceleration_x": round(random.uniform(-2, 2), 2), 
                "acceleration_y": round(random.uniform(-2, 2), 2), 
                "acceleration_z": round(velocity * 0.5 + 9.8, 2), 
                "timestamp": timestamp 
            }

            # Build final packet
            telemetry = {
                "stage": current_stage,
                "imu": imu,
                "barometer1": baro1,
                "barometer2": baro2,
                "accelerometer": accel
            }
            
            await broadcast(telemetry)
            # Throttle loop to ~20Hz
            await asyncio.sleep(0.05)

        elif DATA_SOURCE == Source.SERIAL:
            if ser.in_waiting > 0:
                try:
                    # Read line, decode UTF-8, remove whitespace
                    line = ser.readline().decode('utf-8').strip()
                    telemetry = json.loads(line)
                    await broadcast(telemetry)
                except Exception:
                    # Ignore malformed packets or serial errors
                    pass
            else:
                # Prevent CPU spin loop if no data is waiting
                await asyncio.sleep(0.01)

        elif DATA_SOURCE == Source.FILE:
            if df is not None:
                print("Starting CSV Simulation playback...")
                
                # Iterate row by row through the CSV
                for index, row in df.iterrows():
                    # Calculate a simulated timestamp if needed for visual rotation
                    t = row["timestamp"] 
                    
                    # Map CSV columns to the expected JSON structure
                    telemetry = {
                        "imu": {
                            "calibration_sys": row["calibration_sys"],
                            "calibration_gyro": row["calibration_gyro"],
                            "calibration_accel": row["calibration_accel"],
                            "calibration_mag": row["calibration_mag"],
                            "orientation_x": row["orientation_x"],
                            "orientation_y": row["orientation_y"],
                            "orientation_z": row["orientation_z"],
                            "angular_velocity_x": row["angular_velocity_x"],
                            "angular_velocity_y": row["angular_velocity_y"],
                            "angular_velocity_z": row["angular_velocity_z"],
                            "linear_acceleration_x": row["linear_acceleration_x"],
                            "linear_acceleration_y": row["linear_acceleration_y"],
                            "linear_acceleration_z": row["linear_acceleration_z"],
                            "acceleration_x": row["acceleration_x"],
                            "acceleration_y": row["acceleration_y"],
                            "acceleration_z": row["acceleration_z"],
                            "gravity_x": row["gravity_x"], 
                            "gravity_y": row["gravity_y"], 
                            "gravity_z": row["gravity_z"],
                            "magnetometer_x": row["magnetometer_x"],
                            "magnetometer_y": row["magnetometer_y"],
                            "magnetometer_z": row["magnetometer_z"],
                            "quaternion_w": row["quaternion_w"],
                            "quaternion_x": row["quaternion_x"], 
                            "quaternion_y": row["quaternion_y"], 
                            "quaternion_z": row["quaternion_z"],
                            "temperature": row["temperature"],
                            "timestamp": row["timestamp"]
                        },
                        "barometer1": {
                            "pressure": row["pressure"],
                            "temperature": row["temperature"],
                            "timestamp": row["timestamp"]
                        },
                        "barometer2": {
                            "pressure": row["pressure"],
                            "temperature": row["temperature"],
                            "timestamp": row["timestamp"]
                        },
                        "accelerometer": {
                            "acceleration_x": row["acceleration_x"],
                            "acceleration_y": row["acceleration_y"],
                            "acceleration_z": row["acceleration_z"],
                            "timestamp": row["timestamp"]
                        },
                        "other": {
                            "altitude": row["altitude"],
                            "velocity_x": row["velocity_x"],
                            "velocity_y": row["velocity_y"],
                            "velocity_z": row["velocity_z"],
                            "stage" : row["stage"]
                        }
                    }
                    
                    await broadcast(telemetry)
                    
                    if index % 100 == 0:
                        print(f"Sent row {index}/{len(df)}")
                    
                    # Simulate real-time playback speed
                    # Calculate delay between current and next timestamp, if last row, use a default small delay
                    if index < len(df) - 1:
                        dt = df.at[index + 1, "timestamp"] - row["timestamp"]
                        if dt < 0 or dt > 1.0:
                            dt = 0.01
                    else:
                        dt = 0.01
                    await asyncio.sleep(dt) 
                
                print("CSV Playback finished. Restarting...")
                await asyncio.sleep(3)
            else:
                print("No Dataframe found. Retrying...")
                await asyncio.sleep(1)


async def main():
    """
    Initializes the WebSocket server and starts the data producer coroutine.
    """
    # Start the WebSocket server on localhost:8081
    async with websockets.serve(handler, "localhost", 8081):
        # Run the data generation loop indefinitely
        await data_producer()

if __name__ == "__main__":
    try:
        # Create an async main to run the asyncio event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user.")