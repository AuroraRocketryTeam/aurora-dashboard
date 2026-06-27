<script>
  import { onDestroy } from 'svelte';
  import Header from './lib/Header.svelte';
  import Dashboard from './lib/Dashboard.svelte';
  import CommandCenter from './lib/CommandCenter.svelte';

  // Navigation state
  let activePage = "dashboard"; 

  // Connection state
  let connectionType = "websocket"; // 'websocket' or 'serial'
  let status = "DISCONNECTED";
  let isConnected = false;
  
  // WebSocket State
  let socket;
  
  // Serial State
  let serialPort;
  let serialReader;
  let keepReadingSerial = false;
  let incomingBuffer = "";

  // Track if we have received the first data packet (for plotting initialization)
  let isInitialized = false; 

  // Dashboard data
  let currentStage = "Inactive";
  let imu = {};
  let baro1 = {};
  let baro2 = {};
  let accel = {};

  // Derived Data
  let velocity_z = 0;
  let position_z = 0;
  
  // Magnitude variables for display
  let accel_mag = 0;
  let velocity_mag = 0;

  // History Arrays
  const PLOTS_HISTORY_DURATION = 30; // Seconds
  const UPDATE_RATE = 20; // Hz
  const MAX_SAMPLES = PLOTS_HISTORY_DURATION * UPDATE_RATE; // = 600

  // History arrays (for plotting), initially filled with 0 (will be overwritten on first packet)
  let accelHistory = new Array(MAX_SAMPLES).fill(0);
  let pressureHistory = new Array(MAX_SAMPLES).fill(0);
  let velHistory = new Array(MAX_SAMPLES).fill(0);
  let posHistory = new Array(MAX_SAMPLES).fill(0);

  const STAGES = [
    "Inactive", "Calibrating", "Ready For Launch", "Launch", 
    "Accelerated Flight", "Ballistic Flight", "Apogee", 
    "Stabilization", "Landing", "Recovery"
  ];

  // Command Center State
  let commandHistory = [];
  let _lastAckCommandId = 0;
  let rssi = null;

  const _COMMAND_NAMES = { 0: null, 1: "PING", 2: "ABORT", 3: "EMERG_CHUTE_OPEN" };

  function addCommandEntry(msg, type = "sent") {
      let time = new Date().toLocaleTimeString();
      commandHistory = [{ time, msg, type }, ...commandHistory].slice(0, 100);
  }

  onDestroy(() => {
    disconnect();
  });

  // Connection Management
  async function toggleConnection() {
      if (isConnected) {
          disconnect();
      } else {
          if (connectionType === 'websocket') {
              connectWebSocket();
          } else {
              await connectSerial();
          }
      }
  }

  function disconnect() {
      // WS Disconnect
      if (socket) {
          socket.close();
          socket = null;
      }
      
      // Serial Disconnect
      keepReadingSerial = false;
      if (serialReader) {
          serialReader.cancel();
          serialReader = null;
      }
      if (serialPort) {
          serialPort.close();
          serialPort = null;
      }

      status = "DISCONNECTED";
      isConnected = false;
      isInitialized = false;
  }

  // WebSocket Logic
  function connectWebSocket() {
    status = "CONNECTING...";
    socket = new WebSocket('ws://localhost:8081');
    
    socket.onopen = () => { status = "WS CONNECTED"; isConnected = true; };
    
    socket.onclose = () => { 
        if (isConnected) {
            status = "DISCONNECTED"; 
            isConnected = false;
            isInitialized = false;
        }
    };
    
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "serial_log") {
            addCommandEntry(data.text, "serial");
        } else if ("ok" in data || "error" in data) {
            if (data.ok)   addCommandEntry(data.command_id ? `${data.command_id} sent` : "OK", "sent");
            else           addCommandEntry(`${data.error}`, "error");
        } else {
            handleTelemetry(data);
        }
      } catch (e) { }
    };
  }

  // Serial Logic
  async function connectSerial() {
      if (!("serial" in navigator)) {
          alert("Web Serial API not supported in this browser. Use Chrome/Edge.");
          return;
      }

      try {
          // Request user to select a port
          serialPort = await navigator.serial.requestPort();
          await serialPort.open({ baudRate: 115200 });
          
          status = "SERIAL CONNECTED";
          isConnected = true;
          keepReadingSerial = true;
          
          readSerialLoop();
      } catch (err) {
          console.error(err);
          status = "SERIAL ERROR";
          isConnected = false;
      }
  }

  async function readSerialLoop() {
      const textDecoder = new TextDecoderStream();
      const readableStreamClosed = serialPort.readable.pipeTo(textDecoder.writable);
      const reader = textDecoder.readable.getReader();
      serialReader = reader;

      try {
          while (keepReadingSerial) {
              const { value, done } = await reader.read();
              if (done) {
                  // Allow the serial port to be closed later.
                  reader.releaseLock();
                  break;
              }
              if (value) {
                  processSerialChunk(value);
              }
          }
      } catch (error) {
          console.error("Serial Read Error", error);
          disconnect();
      }
  }

  // Parses stream data that contains mixed Logs and JSON arrays
  function processSerialChunk(chunk) {
      incomingBuffer += chunk;

      // Simple bracket counting parser to handle streamed JSON arrays/objects
      let depth = 0;
      let startIndex = -1;
      let inString = false;
      let escape = false;

      // We loop through buffer to find complete JSON objects/arrays
      for (let i = 0; i < incomingBuffer.length; i++) {
          const char = incomingBuffer[i];

          // Handle String literals so brackets inside strings don't count
          if (char === '"' && !escape) { inString = !inString; }
          if (char === '\\' && inString) { escape = !escape; } else { escape = false; }

          if (!inString) {
              if (char === '{' || char === '[') {
                  if (depth === 0) startIndex = i; // Start of a potential JSON
                  depth++;
              } else if (char === '}' || char === ']') {
                  depth--;
                  if (depth === 0 && startIndex !== -1) {
                      // Found a complete block
                      const jsonStr = incomingBuffer.substring(startIndex, i + 1);
                      try {
                          const parsed = JSON.parse(jsonStr);
                          handleSerialJSON(parsed);
                      } catch (e) {
                          // Ignore parse errors (might be partial log text looking like JSON)
                      }
                      
                      // Remove processed part from buffer
                      incomingBuffer = incomingBuffer.substring(i + 1);
                      i = -1; // Reset loop for the remaining buffer
                      startIndex = -1;
                  }
              }
          }
      }

      // Cleanup: Limit buffer size if garbage data accumulates (Logs without JSON)
      if (incomingBuffer.length > 10000) {
          const lastStart = incomingBuffer.lastIndexOf('['); // Try to save latest array
          if (lastStart > -1) incomingBuffer = incomingBuffer.substring(lastStart);
          else incomingBuffer = ""; // Clear if no structure found
      }
  }

  // Data Adapters

  // Adapts the new Serial JSON format to the App's expected format
  function handleSerialJSON(data) {
      // The serial stream often sends an Array of objects
      const items = Array.isArray(data) ? data : [data];
      
      let unifiedUpdate = {};

      items.forEach(item => {
          if (item.type === 'SENSOR_DATA' && item.content) {
              const src = item.content.source;
              const pay = item.content.sensorData;
              
              if (src === 'BNO055') unifiedUpdate.imu = pay;
              else if (src === 'LIS3DHTR') unifiedUpdate.accelerometer = pay;
              else if (src === 'MS561101BA03_') unifiedUpdate.barometer1 = pay; // Use as Baro 1
              else if (src === 'GPS') {
                  unifiedUpdate.other = { ...(unifiedUpdate.other || {}), ...pay };
              }
          }
      });

      // Pass the mapped object to the main handler
      if (Object.keys(unifiedUpdate).length > 0) {
          handleTelemetry(unifiedUpdate);
      }
  }

  // Helper: Returns val if number, otherwise fallback.
  function sanitize(val, fallback = 0) {
      if (typeof val === 'number' && !isNaN(val)) return val;
      return fallback;
  }

  function handleTelemetry(data) {
      // Extract Standard Sensors (Merge with existing state to prevent flickering if partial updates come)
      if (data.imu) imu = { ...imu, ...data.imu };
      if (data.barometer1) baro1 = { ...baro1, ...data.barometer1 };
      if (data.barometer2) baro2 = { ...baro2, ...data.barometer2 };
      if (data.accelerometer) accel = { ...accel, ...data.accelerometer };

      // Extract Simulation Truth Data (Passed from CSV via "other")
      let vx = 0, vy = 0;

      if (data.other) {
          if (data.other.stage) currentStage = data.other.stage;

          const ackId = data.other.last_ack_command_id ?? 0;
          if (ackId !== 0 && ackId !== _lastAckCommandId) {
              _lastAckCommandId = ackId;
              let name = _COMMAND_NAMES[ackId] ?? `0x${ackId.toString(16).padStart(2,"0")}`;
              addCommandEntry(`ACK received: ${name}`, "ack");
          } else if (ackId === 0) {
              _lastAckCommandId = 0;
          }
          
          if (data.other.rssi != null) rssi = data.other.rssi;
          velocity_z = sanitize(data.other.velocity_z, velocity_z);
          position_z = sanitize(data.other.altitude, position_z);

          // Attempt to get X and Y for magnitude calculation
          vx = sanitize(data.other.velocity_x, 0);
          vy = sanitize(data.other.velocity_y, 0);
      }

      // Update Visualization Histories

      const ax = sanitize(accel.acceleration_x, 0);
      const ay = sanitize(accel.acceleration_y, 0);
      const az = sanitize(accel.acceleration_z, 0);

      accel_mag = Math.sqrt((ax * ax) + (ay * ay) + (az * az));
      // Use vector components if available, otherwise fall back to the scalar velocity from the packet
      const componentMag = Math.sqrt((vx * vx) + (vy * vy) + (velocity_z * velocity_z));
      velocity_mag = (vx || vy || velocity_z) ? componentMag : sanitize(data?.other?.velocity, 0);
      const newPressure = sanitize(baro1.pressure, 101325);

      // Initialization Logic
      if (!isInitialized) {
          accelHistory.fill(accel_mag);
          velHistory.fill(velocity_mag);
          posHistory.fill(position_z);
          pressureHistory.fill(newPressure);
          isInitialized = true;
      }

      // Standard Update
      accelHistory.push(accel_mag);
      if (accelHistory.length > MAX_SAMPLES) accelHistory.shift();
      accelHistory = accelHistory;

      velHistory.push(velocity_mag);
      if (velHistory.length > MAX_SAMPLES) velHistory.shift();
      velHistory = velHistory;

      posHistory.push(position_z);
      if (posHistory.length > MAX_SAMPLES) posHistory.shift();
      posHistory = posHistory;

      pressureHistory.push(newPressure);
      if (pressureHistory.length > MAX_SAMPLES) pressureHistory.shift();
      pressureHistory = pressureHistory;
  }

  // Common Functions

  function sendCommand(str) {
      const time = new Date().toLocaleTimeString();
      let sent = false;

      // Send via WebSocket
      if (connectionType === 'websocket' && socket && socket.readyState === WebSocket.OPEN) {
          socket.send(str);
          sent = true;
      }
      // Send via Serial
      else if (connectionType === 'serial' && serialPort && serialPort.writable) {
         // Need a writer logic here for Serial
         const encoder = new TextEncoder();
         const writer = serialPort.writable.getWriter();
         writer.write(encoder.encode(str + "\n"));
         writer.releaseLock();
         sent = true;
      } else {
          alert("Not connected!");
          return;
      }

      if (sent) {
        addCommandEntry(str, "sent");
      }
  }
</script>

<main>
  <Header
    bind:activePage
    bind:connectionType
    {isConnected}
    {toggleConnection}
    {rssi}
  />

  <div class="container-fluid">
    
    {#if activePage === 'dashboard'}
        <Dashboard 
            {accel_mag}
            {velocity_mag}
            {position_z}
            {baro1}
            {baro2}
            {accel}
            {imu}
            {currentStage}
            {accelHistory}
            {velHistory}
            {posHistory}
            {pressureHistory}
            {STAGES}
        />
    {:else if activePage === 'commands'}
        <CommandCenter 
            {commandHistory}
            {sendCommand}
        />
    {/if}
  </div>
</main>

<style>
  :global(body) { background: #0f0f13; color: #eee; margin: 0; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; overflow: hidden; }

  main { display: flex; flex-direction: column; height: 100vh; }
  .container-fluid { width: 98%; margin: 0 auto; flex: 1; min-height: 0; overflow: hidden; }
</style>
