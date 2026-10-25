<script>
    // Ground track over OpenStreetMap tiles, without a map library: the tiles are
    // plain images and the path is an SVG polyline drawn on top of them. With no
    // network the tiles stay blank and the track, the markers and the scale bar
    // are still there, which is what a launch field usually offers.
    export let track = [];
    export let hasFix = false;

    const TILE = 256;
    const MIN_ZOOM = 3;
    const MAX_ZOOM = 19;
    const PADDING = 40;      // px of margin kept around the track when fitting

    let width = 0;
    let height = 0;
    let zoomOffset = 0;      // what the +/- buttons add to the fitted zoom

    const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

    // Web Mercator, in the pixel space of the whole world at a given zoom.
    const worldX = (lon, z) => ((lon + 180) / 360) * TILE * 2 ** z;
    const worldY = (lat, z) => {
        const rad = (lat * Math.PI) / 180;
        return ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * TILE * 2 ** z;
    };

    $: bounds = track.length
        ? track.reduce((b, p) => ({
              minLat: Math.min(b.minLat, p.lat), maxLat: Math.max(b.maxLat, p.lat),
              minLon: Math.min(b.minLon, p.lon), maxLon: Math.max(b.maxLon, p.lon),
          }), { minLat: 90, maxLat: -90, minLon: 180, maxLon: -180 })
        : null;

    // The largest zoom that still shows the whole track, then whatever the buttons asked for.
    $: fitted = (() => {
        if (!bounds || !width || !height) return 17;
        for (let z = MAX_ZOOM; z > MIN_ZOOM; z--) {
            const w = worldX(bounds.maxLon, z) - worldX(bounds.minLon, z);
            const h = worldY(bounds.minLat, z) - worldY(bounds.maxLat, z);
            if (w <= width - PADDING && h <= height - PADDING) return z;
        }
        return MIN_ZOOM;
    })();
    $: zoom = clamp(fitted + zoomOffset, MIN_ZOOM, MAX_ZOOM);

    $: centre = bounds
        ? { lat: (bounds.minLat + bounds.maxLat) / 2, lon: (bounds.minLon + bounds.maxLon) / 2 }
        : null;

    // Top left corner of the view, same pixel space as worldX / worldY.
    $: origin = centre && width && height
        ? { x: worldX(centre.lon, zoom) - width / 2, y: worldY(centre.lat, zoom) - height / 2 }
        : null;

    $: tiles = (() => {
        if (!origin) return [];
        const span = 2 ** zoom;
        const out = [];
        for (let tx = Math.floor(origin.x / TILE); tx <= Math.floor((origin.x + width) / TILE); tx++) {
            for (let ty = Math.floor(origin.y / TILE); ty <= Math.floor((origin.y + height) / TILE); ty++) {
                if (ty < 0 || ty >= span) continue;
                const wrapped = ((tx % span) + span) % span;
                out.push({
                    key: `${zoom}/${tx}/${ty}`,
                    url: `https://tile.openstreetmap.org/${zoom}/${wrapped}/${ty}.png`,
                    left: tx * TILE - origin.x,
                    top: ty * TILE - origin.y,
                });
            }
        }
        return out;
    })();

    const place = (p) => ({ x: worldX(p.lon, zoom) - origin.x, y: worldY(p.lat, zoom) - origin.y });

    $: polyline = origin
        ? track.map((p) => { const q = place(p); return `${q.x.toFixed(1)},${q.y.toFixed(1)}`; }).join(" ")
        : "";
    $: first = origin && track.length ? place(track[0]) : null;
    $: current = origin && track.length ? place(track[track.length - 1]) : null;

    // Metres per degree at this latitude, enough for a few hundred metres of track.
    const METRES_PER_DEGREE = 111320;
    $: walked = track.reduce((total, p, i) => {
        if (i === 0) return 0;
        const prev = track[i - 1];
        const dy = (p.lat - prev.lat) * METRES_PER_DEGREE;
        const dx = (p.lon - prev.lon) * METRES_PER_DEGREE * Math.cos((p.lat * Math.PI) / 180);
        return total + Math.sqrt(dx * dx + dy * dy);
    }, 0);

    // A bar of about 100 px, labelled with a round distance.
    $: metresPerPixel = centre
        ? (156543.03392 * Math.cos((centre.lat * Math.PI) / 180)) / 2 ** zoom
        : 0;
    $: scale = (() => {
        if (!metresPerPixel) return null;
        const steps = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
        const target = metresPerPixel * 100;
        const metres = steps.find((s) => s >= target) ?? steps[steps.length - 1];
        return { metres, pixels: metres / metresPerPixel };
    })();

    $: last = track.length ? track[track.length - 1] : null;
</script>

<div class="card map-card">
    <h3>GROUND TRACK</h3>

    <div class="viewport" bind:clientWidth={width} bind:clientHeight={height}>
        {#if track.length}
            {#each tiles as tile (tile.key)}
                <img class="tile" src={tile.url} alt="" style="left:{tile.left}px; top:{tile.top}px"
                     on:error={(e) => (e.currentTarget.style.visibility = "hidden")} />
            {/each}

            <svg class="overlay" {width} {height}>
                {#if track.length > 1}
                    <polyline points={polyline} fill="none" stroke="#4cc9f0" stroke-width="2"
                              stroke-linejoin="round" stroke-linecap="round" />
                {/if}
                {#if first}
                    <circle cx={first.x} cy={first.y} r="4" fill="none" stroke="#2a9d8f" stroke-width="2" />
                {/if}
                {#if current}
                    <circle cx={current.x} cy={current.y} r="6" fill="#f72585" stroke="#fff" stroke-width="1.5" />
                {/if}
            </svg>

            <div class="controls">
                <button on:click={() => (zoomOffset += 1)} disabled={zoom >= MAX_ZOOM} title="zoom in">+</button>
                <button on:click={() => (zoomOffset -= 1)} disabled={zoom <= MIN_ZOOM} title="zoom out">−</button>
                {#if zoomOffset !== 0}
                    <button class="fit" on:click={() => (zoomOffset = 0)} title="fit the whole track">fit</button>
                {/if}
            </div>

            {#if scale}
                <div class="scale">
                    <div class="bar" style="width:{scale.pixels}px"></div>
                    <span>{scale.metres} m</span>
                </div>
            {/if}

            <div class="attribution">© OpenStreetMap</div>
        {:else}
            <div class="empty">{hasFix ? "waiting for the first fix" : "no position received yet"}</div>
        {/if}
    </div>

    <div class="footer">
        {#if last}
            <span><b>Now</b> {last.lat.toFixed(6)}, {last.lon.toFixed(6)}</span>
            <span><b>Points</b> {track.length}</span>
            <span><b>Walked</b> {walked < 1000 ? `${walked.toFixed(0)} m` : `${(walked / 1000).toFixed(2)} km`}</span>
            <a href="https://www.openstreetmap.org/?mlat={last.lat}&mlon={last.lon}#map=18/{last.lat}/{last.lon}"
               target="_blank" rel="noreferrer">open in OpenStreetMap</a>
        {:else}
            <span>the position comes from the receiver on the antenna board</span>
        {/if}
    </div>
</div>

<style>
    .map-card { display: flex; flex-direction: column; }
    .viewport {
        position: relative; flex: 1; min-height: 260px; overflow: hidden;
        background: #15151a; border-radius: 4px;
    }
    .tile {
        position: absolute; width: 256px; height: 256px; user-select: none; pointer-events: none;
        /* OSM tiles are made for a light page: dim them to sit on the dark panel. */
        filter: brightness(0.62) saturate(0.7) contrast(1.05);
    }
    .overlay { position: absolute; left: 0; top: 0; pointer-events: none; }

    .controls { position: absolute; top: 8px; right: 8px; display: flex; flex-direction: column; gap: 4px; }
    .controls button {
        width: 26px; height: 26px; border-radius: 4px; border: 1px solid #333;
        background: rgba(20, 20, 26, 0.85); color: #ddd; font-size: 1rem; line-height: 1; cursor: pointer;
    }
    .controls button:disabled { color: #555; cursor: default; }
    .controls .fit { font-size: 0.65rem; }

    .scale { position: absolute; left: 10px; bottom: 8px; display: flex; align-items: center; gap: 6px;
             font-size: 0.7rem; color: #ccc; text-shadow: 0 1px 2px #000; }
    .scale .bar { height: 4px; border: 1px solid #ccc; border-top: none; }

    .attribution { position: absolute; right: 6px; bottom: 4px; font-size: 0.6rem; color: #888; }
    .empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
             color: #555; font-size: 0.85rem; }

    .footer { display: flex; gap: 20px; flex-wrap: wrap; margin-top: 10px; padding-top: 8px;
              border-top: 1px solid #333; font-size: 0.8rem; color: #888; }
    .footer b { color: #aaa; margin-right: 5px; }
    .footer a { color: #4cc9f0; text-decoration: none; }
    .footer a:hover { text-decoration: underline; }
</style>
