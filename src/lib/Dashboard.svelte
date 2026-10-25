<script>
    import { getPolyline } from './utils.js';
    import TrackMap from './TrackMap.svelte';

    export let accel_mag;
    export let velocity_mag;
    export let position_z;
    export let gps = { latitude: 0, longitude: 0, altitude: 0, hasFix: false };
    export let gpsTrack = [];
    export let baro1;
    export let baro2;
    export let accel;
    export let imu;
    export let currentStage;
    export let accelHistory;
    export let velHistory;
    export let posHistory;
    export let pressureHistory;
    export let STAGES;
</script>

<div class="layout">
        
    <div class="sensors-col">
        
        <div class="plots-row">
        <div class="card plot-card">
            <h3>ACCELERATION MAG (m/s²)</h3>
            <div class="plot-container">
            <svg viewBox="0 0 100 50" preserveAspectRatio="none">
                <polyline points={getPolyline(accelHistory, 50, 0, 100)} fill="none" stroke="#4cc9f0" stroke-width="1" vector-effect="non-scaling-stroke" />
            </svg>
            <div class="live-val">{accel_mag?.toFixed(1) || 0}</div>
            </div>
        </div>

        <div class="card plot-card">
            <h3>VELOCITY MAG (m/s)</h3>
            <div class="plot-container">
            <svg viewBox="0 0 100 50" preserveAspectRatio="none">
                <polyline points={getPolyline(velHistory, 50)} fill="none" stroke="#f72585" stroke-width="1" vector-effect="non-scaling-stroke" />
            </svg>
            <div class="live-val" style="color: #f72585;">{velocity_mag?.toFixed(1) || 0}</div>
            </div>
        </div>

        <div class="card plot-card">
            <h3>POSITION Z (m)</h3>
            <div class="plot-container">
            <svg viewBox="0 0 100 50" preserveAspectRatio="none">
                <polyline points={getPolyline(posHistory, 50)} fill="none" stroke="#7209b7" stroke-width="1" vector-effect="non-scaling-stroke" />
            </svg>
            <div class="live-val" style="color: #7209b7;">{position_z?.toFixed(0) || 0}</div>
            </div>
        </div>

        <div class="card plot-card">
            <h3>PRESSURE (Pa)</h3>
            <div class="plot-container">
            <svg viewBox="0 0 100 50" preserveAspectRatio="none">
                <polyline points={getPolyline(pressureHistory, 50)} fill="none" stroke="#e63946" stroke-width="1" vector-effect="non-scaling-stroke" />
            </svg>
            <div class="live-val text-red">{baro1.pressure?.toFixed(0) || 0}</div>
            </div>
        </div>
        </div>

        <div class="mid-row">
        <div class="card">
            <h3>BAROMETER 1</h3>
            <div class="data-grid">
            <div class="row"><span>Pressure</span> <b>{baro1.pressure?.toFixed(1)}</b></div>
            <div class="row"><span>Temp</span> <b>{baro1.temperature?.toFixed(1)}°C</b></div>
            <div class="row"><span>Time</span> <small>{baro1.timestamp?.toFixed(2)}</small></div>
            </div>
        </div>
        <div class="card">
            <h3>BAROMETER 2</h3>
            <div class="data-grid">
            <div class="row"><span>Pressure</span> <b>{baro2.pressure?.toFixed(1)}</b></div>
            <div class="row"><span>Temp</span> <b>{baro2.temperature?.toFixed(1)}°C</b></div>
            <div class="row"><span>Time</span> <small>{baro2.timestamp?.toFixed(2)}</small></div>
            </div>
        </div>
        <div class="card">
            <h3>GPS</h3>
            <div class="data-grid">
            {#if gps.hasFix}
                <div class="row"><span>Lat</span> <b>{gps.latitude.toFixed(6)}</b></div>
                <div class="row"><span>Lon</span> <b>{gps.longitude.toFixed(6)}</b></div>
                <div class="row"><span>Altitude</span> <b>{gps.altitude.toFixed(1)} m</b></div>
                <div class="row"><span>Map</span>
                    <a href="https://www.openstreetmap.org/?mlat={gps.latitude}&mlon={gps.longitude}#map=17/{gps.latitude}/{gps.longitude}"
                       target="_blank" rel="noreferrer">open</a>
                </div>
            {:else}
                <div class="row"><span>Fix</span> <b class="text-red">NO FIX</b></div>
                <div class="row"><span>Lat</span> <b>--</b></div>
                <div class="row"><span>Lon</span> <b>--</b></div>
                <div class="row"><span>Altitude</span> <b>--</b></div>
            {/if}
            </div>
        </div>
        <div class="card">
            <h3>ACCELEROMETER</h3>
            <div class="data-grid">
            <div class="row"><span>Acc X</span> <b>{accel.acceleration_x?.toFixed(2)}</b></div>
            <div class="row"><span>Acc Y</span> <b>{accel.acceleration_y?.toFixed(2)}</b></div>
            <div class="row"><span>Acc Z</span> <b>{accel.acceleration_z?.toFixed(2)}</b></div>
            <div class="row"><span>Time</span> <small>{accel.timestamp?.toFixed(2)}</small></div>
            </div>
        </div>
        </div>

        <TrackMap track={gpsTrack} hasFix={gps.hasFix} />

        <div class="card imu-card">
        <h3>INERTIAL MEASUREMENT UNIT (IMU)</h3>
        <div class="imu-grid">
            <div class="col">
            <h4>CALIBRATION</h4>
            <div class="row"><span>Sys</span> <b>{imu.calibration_sys}</b></div>
            <div class="row"><span>Gyro</span> <b>{imu.calibration_gyro}</b></div>
            <div class="row"><span>Accel</span> <b>{imu.calibration_accel}</b></div>
            <div class="row"><span>Mag</span> <b>{imu.calibration_mag}</b></div>
            </div>
            <div class="col">
            <h4>ORIENTATION</h4>
            <div class="row"><span>X</span> <b>{imu.orientation_x?.toFixed(2)}</b></div>
            <div class="row"><span>Y</span> <b>{imu.orientation_y?.toFixed(2)}</b></div>
            <div class="row"><span>Z</span> <b>{imu.orientation_z?.toFixed(2)}</b></div>
            </div>
            <div class="col">
            <h4>ANGULAR VEL</h4>
            <div class="row"><span>X</span> <b>{imu.angular_velocity_x?.toFixed(2)}</b></div>
            <div class="row"><span>Y</span> <b>{imu.angular_velocity_y?.toFixed(2)}</b></div>
            <div class="row"><span>Z</span> <b>{imu.angular_velocity_z?.toFixed(2)}</b></div>
            </div>
            <div class="col">
            <h4>LINEAR ACC</h4>
            <div class="row"><span>X</span> <b>{imu.linear_acceleration_x?.toFixed(2)}</b></div>
            <div class="row"><span>Y</span> <b>{imu.linear_acceleration_y?.toFixed(2)}</b></div>
            <div class="row"><span>Z</span> <b>{imu.linear_acceleration_z?.toFixed(2)}</b></div>
            </div>
            <div class="col">
            <h4>MAGNETOMETER<span class="hint" title="not carried by the LoRa packet: only on the on-board interface">*</span></h4>
            <div class="row"><span>X</span> <b>{imu.magnetometer_x?.toFixed(0)}</b></div>
            <div class="row"><span>Y</span> <b>{imu.magnetometer_y?.toFixed(0)}</b></div>
            <div class="row"><span>Z</span> <b>{imu.magnetometer_z?.toFixed(0)}</b></div>
            </div>
        </div>
        <div class="imu-footer">
            <span class="note">* magnetometer, quaternions, gravity and IMU temperature are not transmitted over LoRa: they are on the on-board Ground Services page</span>
            <span><b>Quats*:</b> W:{imu.quaternion_w?.toFixed(3)} X:{imu.quaternion_x?.toFixed(3)} Y:{imu.quaternion_y?.toFixed(3)} Z:{imu.quaternion_z?.toFixed(3)}</span>
            <span><b>Gravity*:</b> X:{imu.gravity_x?.toFixed(2)} Y:{imu.gravity_y?.toFixed(2)} Z:{imu.gravity_z?.toFixed(2)}</span>
            <span><b>Temp*:</b> {imu.temperature?.toFixed(1)}°C</span>
        </div>
        </div>

    </div>

    <div class="stages-col">
        <h2>MISSION STAGE</h2>
        <div class="stage-list">
        {#each STAGES as stage}
            <div class="stage-item" class:active={currentStage === stage}>
            <div class="indicator"></div>
            {stage}
            </div>
        {/each}
        </div>
    </div>

</div>

<style>
  .layout { display: grid; grid-template-columns: 1fr 280px; height: 100%; }
  .sensors-col { padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 20px; }
  .plots-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; height: 200px; }
  .mid-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
  
  .card { background: #1e1e24; border: 1px solid #333; border-radius: 6px; padding: 15px; }
  h3 { margin: 0 0 10px 0; font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #333; padding-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  
  .data-grid .row { display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 5px; border-bottom: 1px solid #2a2a30; padding-bottom: 2px; }
  .data-grid b { color: #4cc9f0; font-family: monospace; font-size: 1rem; }
  
  .imu-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; font-size: 0.8rem; }
  .imu-grid h4 { color: #555; font-size: 0.7rem; margin-bottom: 5px; }
  .imu-grid .hint { color: #e9c46a; margin-left: 3px; cursor: help; }
  .imu-footer .note { color: #666; font-style: italic; }
  .imu-grid .row { display: flex; justify-content: space-between; margin-bottom: 4px; }
  .imu-grid b { color: #fff; font-family: monospace; }
  .imu-footer { margin-top: 15px; padding-top: 10px; border-top: 1px solid #333; display: flex; gap: 20px; font-size: 0.8rem; color: #888; flex-wrap: wrap; }
  .imu-footer b { color: #aaa; margin-right: 5px; }

  .plot-container { position: relative; height: 140px; width: 100%; background: #15151a; border-radius: 4px; overflow: hidden; }
  svg { width: 100%; height: 100%; }
  .live-val { position: absolute; top: 10px; right: 10px; font-family: monospace; font-size: 1.5rem; color: #4cc9f0; font-weight: bold; }
  .text-red { color: #e63946; }

  .stages-col { background: #131318; border-left: 1px solid #333; padding: 20px; padding-bottom: 20px; display: flex; flex-direction: column; overflow-y: auto; }
  .stage-list { display: flex; flex-direction: column; gap: 5px; flex-grow: 1; }
  .stage-item { padding: 12px 15px; background: #1e1e24; border-radius: 4px; color: #555; font-weight: bold; font-size: 0.9rem; display: flex; align-items: center; gap: 10px; border: 1px solid transparent; transition: all 0.2s; }
  .indicator { width: 10px; height: 10px; border-radius: 50%; background: #333; }
  .stage-item.active { background: #1c2b29; color: #4cc9f0; border-color: #2a9d8f; box-shadow: 0 0 10px rgba(76, 201, 240, 0.1); }
  .stage-item.active .indicator { background: #4cc9f0; box-shadow: 0 0 8px #4cc9f0; }
</style>
