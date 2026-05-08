<script>
    export let activePage;
    export let connectionType;
    export let isConnected;
    export let toggleConnection;
    export let rssi = null;

    // Returns 0-4 bars based on dBm value
    function rssiBars(dbm) {
        if (dbm === null) return 0;
        if (dbm >= -30)  return 4;
        if (dbm >= -50)  return 3;
        if (dbm >= -70) return 2;
        return 1;
    }

    const _BAR_COLORS = ['#444', '#e63946', '#e9c46a', '#2a9d8f', '#2a9d8f'];

    $: bars = rssiBars(rssi);
    $: color = _BAR_COLORS[bars];
    $: rssiLabel = rssi !== null ? `${rssi} dBm` : '---';
</script>

<header>
    <div class="brand"><span>AURORA ROCKETRY</span> GROUND STATION</div>
    
    <nav class="nav-tabs">
        <button class:active={activePage === 'dashboard'} on:click={() => activePage = 'dashboard'}>
            DASHBOARD
        </button>
        <button class:active={activePage === 'commands'} on:click={() => activePage = 'commands'}>
            COMMAND CENTER
        </button>
    </nav>

    <div class="rssi-indicator" title="LoRa RSSI">
        <svg width="22" height="16" viewBox="0 0 22 16">
            {#each [4, 7, 10, 13] as x, i}
                <rect
                    x={x} y={16 - (i + 1) * 4}
                    width="3" height={(i + 1) * 4}
                    fill={i < bars ? color : '#333'}
                    rx="1"
                />
            {/each}
        </svg>
        <span style="color: {color}">{rssiLabel}</span>
    </div>

    <div class="connection-ui">
        <select bind:value={connectionType} disabled={isConnected}>
            <option value="websocket">WebSocket</option>
            <option value="serial">USB / Serial</option>
        </select>
        <button 
            class="btn-connect" 
            class:connected={isConnected} 
            on:click={toggleConnection}
        >
            {isConnected ? 'DISCONNECT' : 'CONNECT'}
        </button>
        <div class="status-indicator" class:connected={isConnected}></div>
    </div>
</header>

<style>
  header { height: 60px; background: #18181f; display: flex; align-items: center; padding: 0 20px; border-bottom: 1px solid #333; justify-content: space-between; }
  .brand { font-weight: 800; font-size: 1.2rem; letter-spacing: 1px; min-width: 250px; }
  .brand span { color: red; }
  
  /* Connection UI Styles */
  .connection-ui { display: flex; align-items: center; gap: 10px; }
  .connection-ui select { background: #333; color: white; border: 1px solid #444; padding: 5px 10px; border-radius: 4px; outline: none; }
  .connection-ui select:disabled { opacity: 0.5; cursor: not-allowed; }
  
  .btn-connect {
      background: #444; color: white; border: none; padding: 6px 15px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.8rem; letter-spacing: 0.5px;
      transition: background 0.2s;
  }
  .btn-connect:hover { background: #555; }
  .btn-connect.connected { background: #e63946; } /* Red for disconnect */
  
  .status-indicator { width: 10px; height: 10px; border-radius: 50%; background: #444; transition: background 0.3s; }
  .status-indicator.connected { background: #2a9d8f; box-shadow: 0 0 8px #2a9d8f; }

  .rssi-indicator { display: flex; align-items: center; gap: 6px; }
  .rssi-indicator span { font-size: 0.75rem; font-weight: 600; letter-spacing: 0.5px; min-width: 52px; }

  /* --- Navigation Tabs--- */
  .nav-tabs { display: flex; gap: 10px; flex-grow: 1; justify-content: center; }
  .nav-tabs button {
      background: transparent; border: none; color: #666; font-weight: bold;
      padding: 8px 20px; cursor: pointer; border-bottom: 2px solid transparent;
      transition: all 0.2s; font-size: 0.9rem; letter-spacing: 1px;
  }
  .nav-tabs button:hover { color: #fff; }
  .nav-tabs button.active { color: #4cc9f0; border-bottom-color: #4cc9f0; }
</style>
