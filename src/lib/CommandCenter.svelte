<script>
    import { onMount } from 'svelte';

    export let commandHistory = [];
    export let sendCommand; // Function (str) => void

    const UPLINK_COMMANDS = [
        { name: "PING", id: "PING", color: "#2a9d8f", description: "Check link" },
        { name: "ABORT", id: "ABORT", color: "#e63946", description: "Emergency abort" },
        { name: "EMERG CHUTE OPEN", id: "EMERG_CHUTE_OPEN", color: "#f4a261", description: "Force drogue deployment" },
    ];

    function sendUplinkCommand(id) {
        sendCommand(JSON.stringify({ command: "transmit", command_id: id }));
    }

    let commandInput = "";
    let commandTemplates = [];
    let newTemplateName = "";
    let newTemplateCmd = "";
    let fileInput; 

    onMount(() => {
        // Load saved templates from localStorage
        const saved = localStorage.getItem('aurora_templates');
        if (saved) {
            try { commandTemplates = JSON.parse(saved); } catch(e) {}
        }
    });

    function loadTemplate(str) { commandInput = str; }

    function saveTemplate() {
        if (!newTemplateName || !newTemplateCmd) return;
        commandTemplates = [...commandTemplates, { name: newTemplateName, payload: newTemplateCmd }];
        newTemplateName = ""; newTemplateCmd = "";
        persistTemplates();
    }

    function deleteTemplate(index) {
        commandTemplates = commandTemplates.filter((_, i) => i !== index);
        persistTemplates();
    }

    function persistTemplates() {
        localStorage.setItem('aurora_templates', JSON.stringify(commandTemplates));
    }

    function exportTemplates() {
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(commandTemplates));
        const downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", "aurora_commands.json");
        document.body.appendChild(downloadAnchorNode);
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
    }

    function triggerImport() { fileInput.click(); }

    function handleFileImport(event) {
        const file = event.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const parsed = JSON.parse(e.target.result);
                if (Array.isArray(parsed)) {
                    commandTemplates = parsed;
                    persistTemplates();
                    alert("Templates imported successfully!");
                } else { alert("Invalid JSON structure"); }
            } catch (err) { alert("Error parsing JSON file"); }
        };
        reader.readAsText(file);
    }

    function handleSend() {
        if (commandInput) {
            sendCommand(commandInput);
            commandInput = "";
        }
    }
</script>

<div class="command-layout">
            
    <div class="cmd-col">
        <div class="card">
            <h3>MANUAL TRANSMISSION</h3>
            <div class="input-group">
                <input 
                    type="text" 
                    bind:value={commandInput} 
                    placeholder="Enter command string..." 
                    on:keydown={(e) => e.key === 'Enter' && handleSend()}
                />
                <button class="btn-send" on:click={handleSend}>SEND</button>
            </div>
        </div>

        <div class="card">
            <h3>UPLINK COMMANDS</h3>
            <div class="uplink-list">
                {#each UPLINK_COMMANDS as cmd}
                    <button class="btn-uplink" style="--accent: {cmd.color}" on:click={() => sendUplinkCommand(cmd.id)}>
                        <span class="uplink-name">{cmd.name}</span>
                        <span class="uplink-desc">{cmd.description}</span>
                    </button>
                {/each}
            </div>
        </div>

        <div class="card log-card">
            <h3>TRANSMISSION LOG</h3>
            <div class="cmd-log">
                {#if commandHistory.length === 0}
                    <div class="log-empty">No commands sent yet.</div>
                {/if}
                {#each commandHistory as entry}
                    <div class="log-entry log-{entry.type ?? 'sent'}">
                        <span class="log-time">[{entry.time}]</span>
                        <span class="log-msg"> {entry.msg}</span>
                    </div>
                {/each}
            </div>
        </div>
    </div>

    <div class="template-col">
        <div class="card">
            <div class="template-header">
                <h3>SAVED TEMPLATES</h3>
                <div class="file-actions">
                    <input type="file" bind:this={fileInput} on:change={handleFileImport} style="display:none" accept=".json"/>
                    <button class="btn-sm" on:click={triggerImport} title="Import JSON">Import</button>
                    <button class="btn-sm" on:click={exportTemplates} title="Export JSON">Export</button>
                </div>
            </div>

            <div class="template-list">
                {#each commandTemplates as tpl, i}
                    <div class="template-item">
                        <div class="tpl-info">
                            <span class="tpl-name">{tpl.name}</span>
                            <code class="tpl-cmd">{tpl.payload}</code>
                        </div>
                        <div class="tpl-actions">
                            <button class="icon-btn btn-send-icon" on:click={() => sendCommand(tpl.payload)} title="Send Now">
                                <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                            </button>
                            
                            <button class="icon-btn btn-edit-icon" on:click={() => loadTemplate(tpl.payload)} title="Edit in Input Box">
                                <svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
                            </button>

                            <button class="icon-btn btn-del-icon" on:click={() => deleteTemplate(i)} title="Delete">
                                <svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
                            </button>
                        </div>
                    </div>
                {/each}
                {#if commandTemplates.length === 0}
                    <div class="log-empty">No templates saved.</div>
                {/if}
            </div>

            <div class="new-template">
                <h4>CREATE NEW TEMPLATE</h4>
                <input type="text" bind:value={newTemplateName} placeholder="Template Name" />
                <input type="text" bind:value={newTemplateCmd} placeholder="Command String" />
                <button class="btn-save" on:click={saveTemplate}>SAVE TEMPLATE</button>
            </div>
        </div>
    </div>

</div>

<style>
  .command-layout { 
      display: grid; 
      grid-template-columns: 2fr 1fr; 
      gap: 20px; 
      padding: 20px; 
      height: 100%; 
      box-sizing: border-box; /* Ensure padding doesn't overflow height */
  }

  .cmd-col, .template-col { 
      display: flex; 
      flex-direction: column; 
      gap: 20px; 
      height: 100%; 
      overflow: hidden; /* Prevent double scrollbars */
  }
  
  .input-group { display: flex; gap: 10px; }
  input[type="text"] { flex-grow: 1; background: #15151a; border: 1px solid #444; color: #fff; padding: 10px; border-radius: 4px; font-family: monospace; }
  input[type="text"]:focus { outline: none; border-color: #4cc9f0; }
  
  .btn-send { background: #2a9d8f; color: white; border: none; padding: 0 20px; border-radius: 4px; cursor: pointer; font-weight: bold; }
  .btn-send:hover { background: #228074; }
  
  /* Log Card - Fills remaining space */
  .log-card { 
      flex-grow: 1; 
      display: flex; 
      flex-direction: column; 
      min-height: 0; /* Important for flex child scrolling */
  }
  .cmd-log { 
      flex-grow: 1; 
      background: #000; 
      padding: 10px;
      border-radius: 4px;
      font-family: monospace;
      overflow-y: auto; 
      color: #0f0;
      border: 1px solid #333;
  }
  .log-entry { margin-bottom: 4px; font-size: 0.9rem; text-align: left; }
  .log-time { color: #555; margin-right: 10px; }
  .log-sent   .log-msg { color: #0f0; }
  .log-ack    .log-msg { color: #4cc9f0; }
  .log-error  .log-msg { color: #e63946; }
  .log-serial .log-msg { color: #888; font-size: 0.8rem; }
  .log-empty { color: #444; font-style: italic; padding: 10px; text-align: center; }

  /* Template Card - Fills Full Height */
  .template-col .card {
      height: 100%;
      display: flex;
      flex-direction: column;
  }
  
  .card { background: #1e1e24; border: 1px solid #333; border-radius: 6px; padding: 15px; }
  h3 { margin: 0 0 10px 0; font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #333; padding-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .template-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 5px; margin-bottom: 10px; }
  .template-header h3 { border: none; margin: 0; padding: 0; }
  .btn-sm { background: #333; border: none; color: #ccc; font-size: 0.75rem; padding: 4px 8px; border-radius: 3px; cursor: pointer; margin-left: 5px; }
  .btn-sm:hover { background: #555; color: #fff; }

  .template-list { 
      flex-grow: 1; 
      overflow-y: auto; 
      margin-bottom: 20px; 
      min-height: 0; /* Important for scrolling */
  }
  .template-item { background: #15151a; border: 1px solid #333; border-radius: 4px; padding: 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
  .tpl-info { display: flex; flex-direction: column; }
  .tpl-name { font-weight: bold; color: #ddd; font-size: 0.9rem; }
  .tpl-cmd { color: #666; font-size: 0.8rem; font-family: monospace; }
  
  .tpl-actions { display: flex; gap: 5px; }

  /* --- Button Icon Styles --- */
  .icon-btn {
    border: none;
    border-radius: 4px;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    background: #25252b;
    color: #888;
  }
  .icon-btn svg {
    width: 18px;
    height: 18px;
    fill: currentColor;
  }
  
  /* Send Icon Hover */
  .btn-send-icon:hover { background: #2a9d8f; color: white; }
  
  /* Edit Icon Hover */
  .btn-edit-icon:hover { background: #ff9f1c; color: #121212; }
  
  /* Delete Icon Hover */
  .btn-del-icon:hover { background: #e63946; color: white; }

  .uplink-list { display: flex; gap: 10px; flex-wrap: wrap; }
  .btn-uplink { display: flex; flex-direction: column; align-items: flex-start; padding: 10px 16px; border: 1px solid var(--accent); background: transparent; color: var(--accent); border-radius: 4px; cursor: pointer; transition: all 0.2s; min-width: 100px; }
  .btn-uplink:hover { background: var(--accent); color: #fff; }
  .uplink-name { font-weight: bold; font-size: 0.9rem; font-family: monospace; }
  .uplink-desc { font-size: 0.7rem; opacity: 0.7; margin-top: 2px; }

  .new-template { border-top: 1px solid #333; padding-top: 15px; display: flex; flex-direction: column; gap: 8px; }
  .new-template h4 { margin: 0; color: #666; font-size: 0.75rem; }
  .btn-save { background: #333; color: #ccc; border: 1px solid #444; padding: 8px; width: 100%; border-radius: 4px; cursor: pointer; font-weight: bold; transition: all 0.2s; }
  .btn-save:hover { background: #4cc9f0; color: #000; border-color: #4cc9f0; }

</style>
