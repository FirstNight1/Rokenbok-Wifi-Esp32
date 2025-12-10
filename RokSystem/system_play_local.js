// --- Multi-controller, multi-vehicle assignment and mapping logic ---

// Data structures
let controllers = []; // { index, id, gamepad, mapping, assignedVehicle, lastActive, status }
let vehicles = [];    // { id, name, ws, status, assignedController }
let assignments = {}; // controller index -> vehicle id

const CONTROLLER_TIMEOUT = 10 * 1000; // 10 seconds inactivity

// --- UI rendering ---
function renderControllerList() {
    const container = document.getElementById('controller_list');
    if (!container) return;
    let html = '<h2>Controllers</h2>';
    if (controllers.length === 0) {
        html += '<div style="color:#888">No controllers connected.</div>';
    } else {
        html += '<table><tr><th>Index</th><th>Name</th><th>Vehicle</th><th>Mapping</th><th>Status</th></tr>';
        controllers.forEach(ctrl => {
            html += `<tr><td>${ctrl.index}</td><td>${ctrl.id}</td>` +
                `<td>${renderVehicleDropdown(ctrl)}</td>` +
                `<td><button onclick=\"startMapping(${ctrl.index})\">Map</button></td>` +
                `<td id=\"ctrl_status_${ctrl.index}\">${ctrl.status}</td></tr>`;
        });
        html += '</table>';
    }
    html += '<h2>Vehicles</h2>';
    if (vehicles.length === 0) {
        html += '<div style="color:#888">No vehicles discovered.</div>';
    } else {
        html += '<table><tr><th>ID</th><th>Name</th><th>Status</th><th>Assigned Controller</th></tr>';
        vehicles.forEach(v => {
            html += `<tr><td>${v.id}</td><td>${v.name}</td><td>${v.status}</td><td>${v.assignedController ?? ''}</td></tr>`;
        });
        html += '</table>';
    }
    container.innerHTML = html;
}

function renderVehicleDropdown(ctrl) {
    let html = `<select onchange=\"assignVehicle(${ctrl.index}, this.value)\">`;
    html += '<option value=\"\">--None--</option>';
    vehicles.forEach(v => {
        html += `<option value=\"${v.id}\"${ctrl.assignedVehicle === v.id ? ' selected' : ''}>${v.name}</option>`;
    });
    html += '</select>';
    return html;
}

// --- Gamepad connect/disconnect ---
window.addEventListener('gamepadconnected', (e) => {
    updateControllers();
});
window.addEventListener('gamepaddisconnected', (e) => {
    updateControllers();
});

function updateControllers() {
    const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
    controllers = [];
    for (let i = 0; i < gamepads.length; ++i) {
        const gp = gamepads[i];
        if (gp) {
            controllers.push({
                index: gp.index,
                id: gp.id,
                gamepad: gp,
                mapping: {},
                assignedVehicle: assignments[gp.index] || null,
                lastActive: Date.now(),
                status: 'active'
            });
        }
    }
    renderControllerList();
}

// --- Vehicle discovery (placeholder: static list for now) ---
function discoverVehicles() {
    // TODO: Replace with real discovery (e.g., fetch from backend or mDNS)
    vehicles = [
        { id: 'veh1', name: 'Vehicle 1', ws: null, status: 'available', assignedController: null },
        { id: 'veh2', name: 'Vehicle 2', ws: null, status: 'available', assignedController: null }
    ];
    renderControllerList();
}

// --- Assignment logic ---
window.assignVehicle = function (ctrlIdx, vehId) {
    assignments[ctrlIdx] = vehId || null;
    // Update assignedController for vehicles
    vehicles.forEach(v => {
        if (v.id === vehId) v.assignedController = ctrlIdx;
        else if (v.assignedController === ctrlIdx) v.assignedController = null;
    });
    // Update assignedVehicle for controllers
    controllers.forEach(c => {
        if (c.index === ctrlIdx) c.assignedVehicle = vehId || null;
    });
    renderControllerList();
};

// --- Mapping logic (placeholder) ---
window.startMapping = function (ctrlIdx) {
    alert('Mapping UI for controller ' + ctrlIdx + ' (not yet implemented)');
};

// --- Timeout and status logic ---
function checkControllerTimeouts() {
    const now = Date.now();
    controllers.forEach(ctrl => {
        if (now - ctrl.lastActive > CONTROLLER_TIMEOUT) {
            ctrl.status = 'timeout';
        } else {
            ctrl.status = 'active';
        }
        const statusEl = document.getElementById('ctrl_status_' + ctrl.index);
        if (statusEl) statusEl.textContent = ctrl.status;
    });
}
setInterval(checkControllerTimeouts, 1000);

// --- Poll gamepads for activity ---
function pollGamepadActivity() {
    const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
    controllers.forEach(ctrl => {
        const gp = gamepads[ctrl.index];
        if (gp) {
            // If any axis or button is active, update lastActive
            let active = false;
            for (let a of gp.axes) if (Math.abs(a) > 0.1) active = true;
            for (let b of gp.buttons) if (b.pressed) active = true;
            if (active) ctrl.lastActive = Date.now();
        }
    });
}
setInterval(pollGamepadActivity, 100);

// --- Initial load ---
document.addEventListener('DOMContentLoaded', () => {
    discoverVehicles();
    updateControllers();
});
