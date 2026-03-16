# Aurora Ground Station

This project represents the ground station for the Aurora Rocketry Team. It is designed to visualize real-time telemetry data from the rocket during flight and simulations.

The application is built with **Svelte** (Frontend) and uses a **Python** bridge to handle data ingestion from various sources (Serial, CSV replay, or Random generation) and broadcast it via WebSockets.

## System Architecture

```
                   ┌─────────────────────────────────────────┐
                   │            Flight Hardware              │
                   │                                         │
                   │  Flight Computer (ESP32)                │
                   │    BNO055 · LIS3DHTR · MS5611 × 2 · GPS │
                   │         │  ESP-NOW  │                   │
                   │  LoRa Transmitter (Heltec)              │
                   └─────────────────────────────────────────┘
                                    │ LoRa 868 MHz
                                    │ SF7, BW 125 kHz, CR 4/7
                                    ▼
                   ┌─────────────────────────────────────────┐
                   │         Ground Hardware                 │
                   │  LoRa Receiver (Heltec WiFi LoRa 32)    │
                   │  → USB Serial (115200 baud)             │
                   └──────────────────┬──────────────────────┘
                                      │
                   ┌──────────────────▼──────────────────────┐
                   │           backend/  (Python)            │
                   │                                         │
                   │  Sources ──► Recorder (in-memory deque) │
                   │   • serial  (LoRa receiver / direct USB)│
                   │   • file    (CSV replay)                │
                   │         │                               │
                   │  WebSocket server :8081                 │
                   └──────────────────┬──────────────────────┘
                                      │ ws://localhost:8081
                   ┌──────────────────▼──────────────────────┐
                   │         Frontend  (Svelte / Vite)        │
                   │  Dashboard · Command Center             │
                   │  also supports direct Web Serial API    │
                   └─────────────────────────────────────────┘
```

---

## Project Structure

```
aurora-ground-station/
├── src/
│   ├── lib/                    # Svelte components
│   │   ├── Dashboard.svelte
│   │   ├── CommandCenter.svelte
│   │   ├── Header.svelte
│   │   └── utils.js
│   ├── App.svelte              # Connection logic (WebSocket + Web Serial)
│   ├── main.js
│   ├── bridge.py               # Legacy single-file bridge (superseded by backend/)
│   └── simulation_data*.csv    # Sample flight data
│
├── backend/                    # Python telemetry backend
│   ├── main.py                 # Entry point
│   ├── requirements.txt
│   ├── models/
│   │   └── telemetry.py        # Unified TelemetryFrame dataclass
│   ├── sources/
│   │   ├── base.py             # Abstract DataSource
│   │   ├── file_source.py      # CSV replay with real-time pacing
│   │   └── serial_source.py    # Serial port (3 wire formats)
│   ├── pipeline/
│   │   └── recorder.py         # In-memory ring buffer + CSV/JSON save
│   └── server/
│       └── ws_server.py        # WebSocket server + command handler
│
├── index.html
├── package.json
├── vite.config.js
└── svelte.config.js
```

---

## Prerequisites

- **Node.js** v16+
- **Python** 3.10+

---

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/AuroraRocketryTeam/aurora-ground-station.git
    cd aurora-ground-station
    ```

2.  **Install Frontend Dependencies:**
    ```bash
    npm install
    ```

# Backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

## Usage

### 1. Running the Ground Station

You need two terminals: one for the frontend, one for the backend.

Start the Vite development server:

```bash
npm run dev
```

Open your browser and navigate to the URL shown (usually `http://localhost:5173`).

### 2. Backend

```bash
cd backend
source ../.venv/bin/activate
```

#### CSV replay (default – no hardware needed)

```bash
python3 main.py --source file --file ../src/simulation_data.csv
```

Replay at 3× speed, single pass:

```bash
python3 main.py --source file --file ../src/simulation_data.csv --speed 3 --no-loop
```

#### LoRa receiver via USB (live flight)

Auto-detect wire format (works with the current receiver firmware):

```bash
python3 main.py --source serial --port /dev/ttyUSB0
```

Explicit text format (human-readable output from `telemetry_lora_receiver.ino`):

```bash
python3 main.py --source serial --port /dev/ttyUSB0 --serial-format lora_text
```

Explicit binary format (requires [firmware patch](#lora-binary-mode)):

```bash
python3 main.py --source serial --port /dev/ttyUSB0 --serial-format lora_binary
```

#### Direct USB connection to flight computer

```bash
python3 main.py --source serial --port /dev/ttyUSB0 --baud 115200 --serial-format json_line
```

On Windows replace `/dev/ttyUSB0` with `COM3` (or the appropriate port).

#### All options

```
usage: main.py [-h] [--source {file,serial}]
               [--file FILE] [--no-loop] [--speed SPEED]
               [--port PORT] [--baud BAUD]
               [--serial-format {auto,json_line,lora_text,lora_binary}]
               [--ws-host WS_HOST] [--ws-port WS_PORT]
               [--no-record] [--buffer-size BUFFER_SIZE]

  --source              Data source: file | serial  (default: file)

  File source:
    --file              Path to CSV  (default: ../src/simulation_data.csv)
    --loop              Loop recording playback
    --speed             Playback speed multiplier  (default: 1.0)

  Serial source:
    --port              Serial port  (default: /dev/ttyUSB0)
    --baud              Baud rate  (default: 115200)
    --serial-format     Wire format: auto | json_line | lora_text | lora_binary

  WebSocket server:
    --ws-host           Bind host  (default: localhost)
    --ws-port           Port  (default: 8081)

  Recording:
    --no-record         Disable in-memory recording
    --buffer-size       Max frames to keep in memory  (default: 100000)
    --autosave-every    Number of frames to be kept in memory before autosave (0: disabled, default: 0)
```

### 3. Connect the dashboard

In the UI header:
- **WebSocket** mode → click **Connect** (backend must be running)
- **Serial** mode → click **Connect**, select the device port in the browser dialog (no backend needed)

---

## Recording & Saving Flight Data

When the backend is running with a live source (serial), every incoming frame is stored in a circular buffer in memory (default 100 000 frames, ~55 min at 30 Hz).

Send commands to the backend by typing JSON in a WebSocket client, or by wiring a "Save" button into the dashboard:

| Command | Effect |
|---------|--------|
| `{"command": "save"}` | Dump buffer to a timestamped CSV in the current directory |
| `{"command": "save", "path": "flight_001.csv"}` | Save to an explicit path |
| `{"command": "save", "format": "json"}` | Save as JSON instead of CSV |
| `{"command": "status"}` | Return `{frames, duration_s, enabled}` |
| `{"command": "clear"}` | Wipe the in-memory buffer |
| `{"command": "stop_recording"}` | Pause recording (buffer is preserved) |
| `{"command": "start_recording"}` | Resume recording |

The CSV schema is compatible with the existing `simulation_data.csv` files.

---

## Serial Wire Formats

| Format | When to use |
|--------|-------------|
| `auto` | Default – detects format from first bytes received |
| `json_line` | Flight computer connected directly via USB; one JSON object per newline |
| `lora_text` | LoRa receiver (Heltec) with **current** firmware – human-readable `Serial.printf` output |
| `lora_binary` | LoRa receiver with patched firmware – framed binary `TelemetryPacket` struct |

### LoRa Binary Mode

The binary mode is more efficient and removes the text-parsing overhead. To enable it, add this helper to `telemetry_lora_receiver.ino` and call it from `processTelemetryPacket()` in place of the `Serial.printf` block:

```cpp
void sendBinaryFrame(const TelemetryPacket& pkt) {
    const uint8_t MAGIC[2] = {0xAA, 0x55};
    uint8_t len = sizeof(TelemetryPacket);          // 57 bytes
    uint16_t crc = calculateCRC16((const uint8_t*)&pkt, len);
    Serial.write(MAGIC, 2);
    Serial.write(&len, 1);
    Serial.write((const uint8_t*)&pkt, len);
    Serial.write((uint8_t*)&crc, 2);
}
```

Frame layout: `0xAA 0x55 | length(1B) | TelemetryPacket(57B) | CRC16-LE(2B)` = 62 bytes.

---

## Connection Settings

In the Frontend UI:
1. Select **Connection Type**:
   - **WebSocket** – connects to the backend at `ws://localhost:8081`
   - **Serial** – connects directly to a serial device using the Web Serial API (Chrome/Edge only, no backend needed)
2. Click **Connect**.