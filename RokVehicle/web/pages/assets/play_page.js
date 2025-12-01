// --- Play page UI logic for view selection, camera IPs, PIP flip, controller mapping, and Bluetooth scan (placeholder) ---

let viewMode = 'area';
let pipFlip = false;
let areaIP = '';
let fpvIP = '';

let driveMode = 'tank';
let mapping = {};
let auxMotors = [];
let allMotors = [];
let vehicleType = '';

function setView(mode) {
    viewMode = mode;
    updateViewUI();
    saveViewConfig();
}

function flipPIP() {
    pipFlip = !pipFlip;
    updateViewUI();
    saveViewConfig();
}

function updateViewUI() {
    // Highlight selected view button
    ['area', 'fpv', 'pip'].forEach(m => {
        let btn = document.getElementById('view_' + m + '_btn');
        if (btn) btn.style.background = (viewMode === m) ? '#d1e7dd' : '';
    });
    // Update video area (placeholder)
    const container = document.getElementById('video_container');
    if (!container) return;
    container.innerHTML = '';
    if (viewMode === 'area') {
        container.innerHTML = `<video class="video-full" src="http://${areaIP}/stream" controls autoplay></video>`;
    } else if (viewMode === 'fpv') {
        container.innerHTML = `<video class="video-full" src="http://${fpvIP}/stream" controls autoplay></video>`;
    } else if (viewMode === 'pip') {
        // PIP: large and small video, flip if needed
        let main = pipFlip ? fpvIP : areaIP;
        let pip = pipFlip ? areaIP : fpvIP;
        container.innerHTML = `
            <div class="video-main${pipFlip ? ' flipped' : ''}">
                <video src="http://${main}/stream" width="100%" height="100%" controls autoplay></video>
            </div>
            <div class="video-pip${pipFlip ? ' flipped' : ''}">
                <video src="http://${pip}/stream" width="100%" height="100%" controls autoplay></video>
            </div>`;
    }
}

function saveCameraIPs() {
    areaIP = document.getElementById('area_ip').value;
    fpvIP = document.getElementById('fpv_ip').value;
    localStorage.setItem('area_ip', areaIP);
    localStorage.setItem('fpv_ip', fpvIP);
    saveViewConfig();
    alert('Camera IPs saved!');
    updateViewUI();
}

function saveViewConfig() {
    // Save to backend
    fetch('/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'save_view',
            area_ip: areaIP,
            fpv_ip: fpvIP,
            view_mode: viewMode,
            pip_flip: pipFlip
        })
    });
}

function loadViewConfig() {
    // Load from backend (or localStorage as fallback)
    fetch('/play?config=1').then(r => r.json()).then(cfg => {
        areaIP = cfg.area_ip || localStorage.getItem('area_ip') || '';
        fpvIP = cfg.fpv_ip || localStorage.getItem('fpv_ip') || '';
        viewMode = cfg.view_mode || 'area';
        pipFlip = !!cfg.pip_flip;
        document.getElementById('area_ip').value = areaIP;
        document.getElementById('fpv_ip').value = fpvIP;
        updateViewUI();
    });
}


// --- Live mapping state ---
let mappingActive = null; // { field: 'tank_left_axis', type: 'axis'|'button'|'dpad', auxIdx: number|null }

function renderMappingUI() {
    const container = document.getElementById('mapping_section');
    if (!container) return;
    let html = '';
    html += '<h3>Axis Motors</h3>';
    if (typeof axisMotors !== 'undefined' && axisMotors.length) {
        html += '<table><tr><th>Name</th><th>Axis</th><th>Reverse</th><th>Deadzone</th></tr>';
        axisMotors.forEach((motor, idx) => {
            html += `<tr><td>${motor.name}</td>` +
                `<td><input id="axis_${motor.id}_axis" type="number" value="${mapping[`axis_${motor.id}_axis`] ?? ''}" style="width:40px"></td>` +
                `<td><input id="axis_${motor.id}_rev" type="checkbox" ${mapping[`axis_${motor.id}_rev`] ? 'checked' : ''}></td>` +
                `<td><input id="axis_${motor.id}_dead" type="number" step="0.01" value="${mapping[`axis_${motor.id}_dead`] ?? 0.1}" style="width:50px"></td></tr>`;
        });
        html += '</table>';
    } else {
        html += '<div style="color:#888">No axis motors configured.</div>';
    }
    html += '<h3>Motor Functions</h3>';
    if (typeof motorFunctions !== 'undefined' && motorFunctions.length) {
        html += '<table><tr><th>Name</th><th>Forward Btn</th><th>Reverse Btn</th></tr>';
        motorFunctions.forEach((fn, idx) => {
            html += `<tr><td>${fn.name}</td>` +
                `<td><input id="motorfn_${fn.id}_fwd" type="text" value="${mapping[`motorfn_${fn.id}_fwd`] ?? ''}" style="width:40px"></td>` +
                `<td><input id="motorfn_${fn.id}_rev" type="text" value="${mapping[`motorfn_${fn.id}_rev`] ?? ''}" style="width:40px"></td></tr>`;
        });
        html += '</table>';
    } else {
        html += '<div style="color:#888">No motor functions configured.</div>';
    }
    html += '<h3>Logic Functions</h3>';
    if (typeof logicFunctions !== 'undefined' && logicFunctions.length) {
        html += '<table><tr><th>Name</th><th>Button</th></tr>';
        logicFunctions.forEach((fn, idx) => {
            html += `<tr><td>${fn.name}</td>` +
                `<td><input id="logicfn_${fn.id}_btn" type="text" value="${mapping[`logicfn_${fn.id}_btn`] ?? ''}" style="width:40px"></td></tr>`;
        });
        html += '</table>';
    } else {
        html += '<div style="color:#888">No logic functions configured.</div>';
    }
    html += `<button id="save_mapping_btn">Save Mapping</button>`;
    html += `<div id="mapping_status" style="margin-top:8px;color:#1976d2;"></div>`;
    container.innerHTML = html;
}

function startMapping(field, type, auxIdx = null, dpadDir = null) {
    mappingActive = { field, type, auxIdx, dpadDir };
    document.getElementById('mapping_status').textContent = `Waiting for ${type === 'axis' ? 'axis move' : type === 'button' ? 'button press' : 'dpad press'}...`;
    highlightMappingField(field, true);
}

function highlightMappingField(field, on) {
    let el = null;
    if (field.startsWith('tank_left_axis')) el = document.getElementById('tank_left_axis');
    else if (field.startsWith('tank_right_axis')) el = document.getElementById('tank_right_axis');
    else if (field.startsWith('aux')) {
        let idx = field.match(/aux(\d+)_(fwd|rev)/);
        if (idx) el = document.getElementById(`aux${idx[1]}_${idx[2]}`);
    } else if (field.startsWith('dpad_')) {
        el = document.getElementById(field);
    }
    if (el) el.style.background = on ? '#ffe082' : '';
}

// --- Gamepad polling for mapping ---
let lastGamepadState = null;
function pollGamepadForMapping() {
    if (!mappingActive) return;
    const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
    if (!gamepads[0]) return;
    const gp = gamepads[0];
    // Axis mapping
    if (mappingActive.type === 'axis') {
        for (let i = 0; i < gp.axes.length; ++i) {
            if (Math.abs(gp.axes[i]) > 0.7) {
                mapping[mappingActive.field] = i;
                document.getElementById(mappingActive.field).value = i;
                document.getElementById('mapping_status').textContent = `Mapped to Axis ${i + 1}`;
                highlightMappingField(mappingActive.field, false);
                mappingActive = null;
                return;
            }
        }
    } else if (mappingActive.type === 'button') {
        for (let i = 0; i < gp.buttons.length; ++i) {
            if (gp.buttons[i].pressed) {
                // Map to A/B/X/Y if possible
                let btnName = ['A', 'B', 'X', 'Y'][i] || `Btn${i}`;
                mapping[mappingActive.field] = btnName;
                document.getElementById(mappingActive.field).value = btnName;
                document.getElementById('mapping_status').textContent = `Mapped to ${btnName}`;
                highlightMappingField(mappingActive.field, false);
                mappingActive = null;
                return;
            }
        }
    } else if (mappingActive.type === 'dpad') {
        // D-Pad is usually buttons 12-15
        const dpadMap = { up: 12, down: 13, left: 14, right: 15 };
        let dir = mappingActive.dpadDir;
        let idx = dpadMap[dir];
        if (gp.buttons[idx] && gp.buttons[idx].pressed) {
            mapping[mappingActive.field] = 'both'; // or 'left'/'right' if you want to support split
            document.getElementById(mappingActive.field).value = 'both';
            document.getElementById('mapping_status').textContent = `Mapped to D-Pad ${dir}`;
            highlightMappingField(mappingActive.field, false);
            mappingActive = null;
            return;
        }
    }
}

setInterval(pollGamepadForMapping, 100);

function saveMapping() {
    // Gather mapping from UI for all axis motors, motor functions, and logic functions
    let newMap = {};
    if (typeof axisMotors !== 'undefined' && axisMotors.length) {
        axisMotors.forEach(motor => {
            newMap[`axis_${motor.id}_axis`] = parseInt(document.getElementById(`axis_${motor.id}_axis`).value);
            newMap[`axis_${motor.id}_rev`] = document.getElementById(`axis_${motor.id}_rev`).checked;
            newMap[`axis_${motor.id}_dead`] = parseFloat(document.getElementById(`axis_${motor.id}_dead`).value);
        });
    }
    if (typeof motorFunctions !== 'undefined' && motorFunctions.length) {
        motorFunctions.forEach(fn => {
            newMap[`motorfn_${fn.id}_fwd`] = document.getElementById(`motorfn_${fn.id}_fwd`).value;
            newMap[`motorfn_${fn.id}_rev`] = document.getElementById(`motorfn_${fn.id}_rev`).value;
        });
    }
    if (typeof logicFunctions !== 'undefined' && logicFunctions.length) {
        logicFunctions.forEach(fn => {
            newMap[`logicfn_${fn.id}_btn`] = document.getElementById(`logicfn_${fn.id}_btn`).value;
        });
    }
    fetch('/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'save_mapping',
            mapping: newMap,
            drive_mode: driveMode
        })
    }).then(() => { mapping = newMap; alert('Mapping saved!'); });
}

function loadConfigAndRender() {
    fetch('/play?config=1').then(r => r.json()).then(cfg => {
        areaIP = cfg.area_ip || '';
        fpvIP = cfg.fpv_ip || '';
        viewMode = cfg.view_mode || 'area';
        pipFlip = !!cfg.pip_flip;
        driveMode = cfg.drive_mode || 'tank';
        mapping = cfg.mapping || {};
        auxMotors = cfg.aux_motors || [];
        allMotors = cfg.motors || [];
        vehicleType = cfg.vehicle_type || '';
        document.getElementById('area_ip').value = areaIP;
        document.getElementById('fpv_ip').value = fpvIP;
        updateViewUI();
        renderMappingUI();
    });
}


// --- Controller source toggle ---
let controllerSource = 'ble'; // 'ble' or 'browser'

function renderControllerSourceUI() {
    const section = document.getElementById('controller_source_section');
    if (!section) return;
    section.innerHTML = `
      <label><input type="radio" name="controller_source" value="ble" ${controllerSource === 'ble' ? 'checked' : ''}> Use BLE Gamepad</label>
      <label style="margin-left:16px"><input type="radio" name="controller_source" value="browser" ${controllerSource === 'browser' ? 'checked' : ''}> Use Gamepad connected to this device</label>
    `;
    Array.from(section.querySelectorAll('input[name=controller_source]')).forEach(radio => {
        radio.onchange = function () {
            controllerSource = this.value;
            renderControllerSections();
        };
    });
}

function renderControllerSections() {
    renderControllerSourceUI();
    document.getElementById('ble_controller_section').style.display = (controllerSource === 'ble') ? '' : 'none';
    document.getElementById('browser_controller_section').style.display = (controllerSource === 'browser') ? '' : 'none';
}

// --- Browser Gamepad API ---
let browserGamepadIndex = null;
let browserGamepadState = null;
let browserGamepadInterval = null;

function startBrowserGamepad() {
    if (browserGamepadInterval) clearInterval(browserGamepadInterval);
    browserGamepadInterval = setInterval(pollBrowserGamepad, 50);
}

function stopBrowserGamepad() {
    if (browserGamepadInterval) clearInterval(browserGamepadInterval);
    browserGamepadInterval = null;
}

function pollBrowserGamepad() {
    const gps = navigator.getGamepads ? navigator.getGamepads() : [];
    let gp = null;
    for (let i = 0; i < gps.length; ++i) {
        if (gps[i]) { gp = gps[i]; browserGamepadIndex = i; break; }
    }
    browserGamepadState = gp;
    renderBrowserGamepadUI();
    if (gp) sendBrowserGamepadInput(gp);
}

function renderBrowserGamepadUI() {
    const section = document.getElementById('browser_controller_section');
    if (!section) return;
    if (!browserGamepadState) {
        section.innerHTML = '<div style="color:#888">No gamepad detected. Connect a controller and press any button.</div>';
        return;
    }
    let html = `<div><b>Gamepad:</b> ${browserGamepadState.id}</div>`;
    html += '<div><b>Axes:</b> ' + browserGamepadState.axes.map((v, i) => `A${i}:${v.toFixed(2)}`).join(' ') + '</div>';
    html += '<div><b>Buttons:</b> ' + browserGamepadState.buttons.map((b, i) => `B${i}:${b.pressed ? '●' : '○'}`).join(' ') + '</div>';
    section.innerHTML = html;
}

function sendBrowserGamepadInput(gp) {
    if (!ws || ws.readyState !== 1) return;
    // Axis motors: send axis value, apply reverse and deadzone
    if (typeof axisMotors !== 'undefined' && axisMotors.length) {
        axisMotors.forEach(motor => {
            let axisIdx = mapping[`axis_${motor.id}_axis`] ?? 0;
            let val = gp.axes[axisIdx] || 0;
            if (mapping[`axis_${motor.id}_rev`]) val = -val;
            if (Math.abs(val) < (mapping[`axis_${motor.id}_dead`] ?? 0.1)) val = 0;
            ws.send(JSON.stringify({ action: 'axis_motor', id: motor.id, value: val }));
        });
    }
    // Motor functions: send fwd/rev button state
    if (typeof motorFunctions !== 'undefined' && motorFunctions.length) {
        motorFunctions.forEach(fn => {
            let fwdBtn = mapping[`motorfn_${fn.id}_fwd`] || 'A';
            let revBtn = mapping[`motorfn_${fn.id}_rev`] || 'B';
            let fwdIdx = { A: 0, B: 1, X: 2, Y: 3 }[fwdBtn];
            let revIdx = { A: 0, B: 1, X: 2, Y: 3 }[revBtn];
            let fwd = gp.buttons[fwdIdx]?.pressed;
            let rev = gp.buttons[revIdx]?.pressed;
            ws.send(JSON.stringify({ action: 'motor_function', id: fn.id, fwd, rev }));
        });
    }
    // Logic functions: send button state
    if (typeof logicFunctions !== 'undefined' && logicFunctions.length) {
        logicFunctions.forEach(fn => {
            let btn = mapping[`logicfn_${fn.id}_btn`] || 'A';
            let btnIdx = { A: 0, B: 1, X: 2, Y: 3 }[btn];
            let pressed = gp.buttons[btnIdx]?.pressed;
            ws.send(JSON.stringify({ action: 'logic_function', id: fn.id, pressed }));
        });
    }
}

document.addEventListener('DOMContentLoaded', function () {
    loadConfigAndRender();
    renderControllerSections();
    // Start browser gamepad polling if selected
    if (controllerSource === 'browser') startBrowserGamepad();
    // Toggle logic
    document.getElementById('controller_source_section').addEventListener('change', function (e) {
        if (e.target.name === 'controller_source') {
            controllerSource = e.target.value;
            renderControllerSections();
            if (controllerSource === 'browser') startBrowserGamepad();
            else stopBrowserGamepad();
        }
    });
});

// Placeholder for Bluetooth scan
function scanBT() {
    document.getElementById('bt_status').textContent = 'Scanning... (not implemented)';
    setTimeout(() => {
        document.getElementById('bt_list').innerHTML = '<li>Controller 1 (mock)</li><li>Controller 2 (mock)</li>';
        document.getElementById('bt_status').textContent = 'Select a controller to pair.';
    }, 1200);
}

// Placeholder for D-Pad/Tank toggle
function toggleDriveMode() {
    alert('Drive mode toggled (not yet implemented)');
}
// Basic websocket helper for realtime control (extracted from play_page.py)
var ws = null;
function connectWS() {
    if (ws && ws.readyState === 1) return;
    try {
        ws = new WebSocket('ws://' + location.host + '/ws');
        ws.onopen = function () { console.log('WS open'); document.getElementById('conn_status').textContent = 'Connected'; };
        ws.onclose = function () { console.log('WS closed'); document.getElementById('conn_status').textContent = 'Disconnected'; };
        ws.onerror = function (e) { console.log('WS error', e); document.getElementById('conn_status').textContent = 'Error'; };
        ws.onmessage = function (m) { console.log('WS msg', m.data); };
    } catch (e) { console.log('WS init failed', e); document.getElementById('conn_status').textContent = 'Error'; }
}

function disconnectWS() {
    if (ws) { try { ws.close(); } catch (e) { } ws = null; }
    document.getElementById('conn_status').textContent = 'Disconnected';
}

function sendCmd(obj) {
    if (ws && ws.readyState === 1) { ws.send(JSON.stringify(obj)); }
    else { console.log('WS not connected, cmd skipped', obj); }
}

// Placeholder: UI will call this with mapped values when implemented
function sendTest() {
    var left = document.getElementById('map_left').value;
    var right = document.getElementById('map_right').value;
    // example: drive both forward at 30%
    sendCmd({ action: 'set', name: left, dir: 'fwd', power: 0.3 });
    sendCmd({ action: 'set', name: right, dir: 'fwd', power: 0.3 });
}
