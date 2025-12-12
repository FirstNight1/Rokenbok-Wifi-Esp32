// --- Motor Number Assignment Logic ---
window.addEventListener('DOMContentLoaded', function () {
    // Attach change listeners to all motor number dropdowns
    const dropdowns = document.querySelectorAll('select[id$="_motor_num"]');
    dropdowns.forEach(dd => {
        dd.addEventListener('change', function (e) {
            // Prevent duplicate assignments: if another dropdown has this value, clear it
            const val = parseInt(dd.value);
            dropdowns.forEach(other => {
                if (other !== dd && parseInt(other.value) === val) {
                    other.value = '';
                }
            });
        });
    });
    // No global save button needed; now each motor has its own Save button
});

async function saveMotorNumbers() {
    // Gather assignments
    const dropdowns = document.querySelectorAll('select[id$="_motor_num"]');
    const assignments = {};
    let used = new Set();
    let valid = true;
    dropdowns.forEach(dd => {
        const name = dd.id.replace('_motor_num', '');
        const val = parseInt(dd.value);
        if (!val || used.has(val)) {
            valid = false;
            dd.style.background = '#fbb';
        } else {
            dd.style.background = '';
            assignments[name] = val;
            used.add(val);
        }
    });
    if (!valid || Object.keys(assignments).length !== dropdowns.length) {
        alert('Each motor must have a unique motor number assigned.');
        return;
    }
    try {
        const resp = await fetch('/testing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'save_motor_numbers', assignments })
        });
        if (resp.redirected) {
            window.location.href = resp.url;
        } else if (resp.ok) {
            window.location.reload();
        } else {
            alert('Failed to save motor assignments (server error)');
        }
    } catch (e) {
        alert('Failed to save motor assignments');
    }
}
// Toggle reversed state for a motor using POST
async function toggleReversed(name) {
    try {
        const resp = await fetch('/testing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'toggle_reversed', name: name })
        });
        if (resp.redirected) {
            window.location.href = resp.url;
        } else if (resp.ok) {
            window.location.reload();
        } else {
            alert('Failed to toggle reversed (server error)');
        }
    } catch (e) {
        alert('Failed to toggle reversed for ' + name);
    }
}
// WebSocket connection for realtime control. Browser cannot send raw
// UDP packets, so use WebSocket to send frequent control messages.

var ws = null;
var wsConnected = false;

// per-motor runtime state: { intervalId, timeoutId, gen }
var motorsState = {};

function _ensureMotorState(name) {
    if (!motorsState[name]) motorsState[name] = { intervalId: null, timeoutId: null, gen: 0 };
    return motorsState[name];
}
function setWSStatus(connected) {
    wsConnected = connected;
    var el = document.getElementById('ws_status');
    if (el) {
        el.textContent = connected ? 'WebSocket: Connected' : 'WebSocket: Disconnected';
        el.style.color = connected ? 'green' : 'red';
    }
    // Disable stop/stop all if not connected
    var stopBtns = document.querySelectorAll('.stop-btn');
    for (var i = 0; i < stopBtns.length; ++i) {
        stopBtns[i].disabled = !connected;
    }
    var fwdRevBtns = document.querySelectorAll('button');
    for (var i = 0; i < fwdRevBtns.length; ++i) {
        if (fwdRevBtns[i].textContent === 'Forward' || fwdRevBtns[i].textContent === 'Reverse') {
            fwdRevBtns[i].disabled = !connected;
        }
    }
}
function initWS() {
    try {
        ws = new WebSocket('ws://' + location.host + '/ws');
        ws.onopen = function () { console.log('WS open'); setWSStatus(true); };
        ws.onclose = function () { console.log('WS closed'); setWSStatus(false); setTimeout(initWS, 5000); };
        ws.onerror = function (e) { console.log('WS error', e); setWSStatus(false); };
        ws.onmessage = function (m) {
            try {
                var pkt = JSON.parse(m.data);
                if (!pkt || !pkt.action) return;
                if (pkt.action === 'stop') {
                    // server requests local stop for a motor
                    stopLocal(pkt.name);
                } else if (pkt.action === 'stop_all') {
                    stopAllLocal();
                }
            } catch (e) { }
        };
    } catch (e) {
        console.log('WS init failed', e); setWSStatus(false);
    }
}

window.addEventListener('DOMContentLoaded', function () { initWS(); });

// Unified dispatcher: try WebSocket
function dispatchCommand(action, payload, allowHttpFallback) {
    const pkt = Object.assign({ action: action }, payload || {});
    if (ws && ws.readyState === 1) {
        try {
            ws.send(JSON.stringify(pkt));
            return Promise.resolve(true);
        } catch (e) {
            // fallthrough
        }
    }
    // No WebSocket connection: notify caller
    return Promise.resolve(false);
}

// Stop a motor: cancel local timers + dispatch stop command
async function sendStop(name) {
    // locally cancel timers first
    stopLocal(name);
    const ok = await dispatchCommand('stop', { name: name }); // never allow fallback
    if (!ok) alert('WebSocket not connected — cannot send stop command.');
}

// local-only stop: cancel timers and bump generation but do not dispatch network
function stopLocal(name) {
    const st = _ensureMotorState(name);
    st.gen += 1;
    try { if (st.intervalId) { clearInterval(st.intervalId); st.intervalId = null; } } catch (e) { }
    try { if (st.timeoutId) { clearTimeout(st.timeoutId); st.timeoutId = null; } } catch (e) { }
}

// Stop all motors: clear all state and dispatch stop_all
async function stopAll() {
    stopAllLocal();
    const ok = await dispatchCommand('stop_all', {}); // never allow fallback
    if (!ok) alert('WebSocket not connected — cannot send stop all command.');
}

function stopAllLocal() {
    try {
        for (let name in motorsState) {
            const st = motorsState[name];
            st.gen += 1;
            try { if (st.intervalId) clearInterval(st.intervalId); } catch (e) { }
            try { if (st.timeoutId) clearTimeout(st.timeoutId); } catch (e) { }
            st.intervalId = null; st.timeoutId = null;
        }
    } catch (e) { }
}

// Save minimum duty for a motor using POST only (scale 1-65)
async function saveMin(name) {
    let val = parseInt(document.getElementById(name + '_min').value);
    if (isNaN(val) || val < 1) val = 1;
    if (val > 65) val = 65;
    try {
        const resp = await fetch('/testing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'save_min', name: name, min: val })
        });
        if (resp.redirected) {
            window.location.href = resp.url;
        } else if (resp.ok) {
            window.location.reload();
        } else {
            alert('Failed to save min (server error)');
        }
    } catch (e) {
        alert('Failed to save min for ' + name);
    }
}

// Run a motor for given duration using watchdog keepalive
// start sending set commands for a motor; durationSec optional
function startMotor(name, dir, power, durationSec) {
    const st = _ensureMotorState(name);
    // cancel existing
    st.gen += 1;
    try { if (st.intervalId) clearInterval(st.intervalId); } catch (e) { }
    try { if (st.timeoutId) clearTimeout(st.timeoutId); } catch (e) { }
    st.intervalId = null; st.timeoutId = null;

    const myGen = st.gen;
    // send once immediately
    dispatchCommand('set', { name: name, dir: dir, power: power }); // never allow fallback

    // schedule periodic keepalive updates
    st.intervalId = setInterval(function () {
        if (st.gen !== myGen) {
            try { if (st.intervalId) clearInterval(st.intervalId); } catch (e) { }
            st.intervalId = null;
            return;
        }
        dispatchCommand('set', { name: name, dir: dir, power: power }); // never allow fallback
    }, 50);

    // schedule stop after duration if provided
    if (durationSec && durationSec > 0) {
        st.timeoutId = setTimeout(function () {
            if (st.gen !== myGen) {
                st.timeoutId = null;
                return;
            }
            // ensure timers cleared and send stop
            try { if (st.intervalId) clearInterval(st.intervalId); } catch (e) { }
            st.intervalId = null;
            st.timeoutId = null;
            // Prevent further keepalives by bumping gen
            st.gen += 1;
            sendStop(name);
        }, durationSec * 1000);
    }
}

// High-level UI run wrapper (keeps original API)
// List of function motors (populated by backend)
window.functionMotors = window.functionMotors || [];

function runMotor(name, dir) {
    let duration = parseFloat(document.getElementById(name + "_duration").value);
    let isFunction = window.functionMotors && window.functionMotors.indexOf(name) !== -1;
    let power = 1.0;
    if (!isFunction) {
        let powerPct = parseInt(document.getElementById(name + "_power").value);
        power = Math.max(0, Math.min(1, powerPct / 100));
    }
    startMotor(name, dir, power, duration);
}
