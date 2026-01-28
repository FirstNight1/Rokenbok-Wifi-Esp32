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

// per-motor runtime state: { gen }
var motorsState = {};

// Global active motors state for combined packets
var activeMotors = {
    axisMotors: {},
    functionMotors: {},
    logicFunctions: {}
};

// Single global timer system for consistent packet sending
var globalPacketTimer = null;
var lastSentPacket = null;
var packetsSinceChange = 0;
var motorStopTimers = {}; // Track individual motor stop timers

// Configurable keepalive interval (loaded from admin page settings)
let KEEPALIVE_INTERVAL = 200; // ms, default keepalive interval

// Load keepalive configuration from admin page
async function loadKeepAliveConfig() {
    try {
        const response = await fetch('/admin?config=keepalive');
        if (response.ok) {
            const config = await response.json();
            if (config && config.keepalive_interval_ms) {
                KEEPALIVE_INTERVAL = config.keepalive_interval_ms;
            }
        }
    } catch (e) {
        // Use default interval on error
    }
}

function _ensureMotorState(name) {
    // Simple state tracking - no complex timer management
    if (!motorsState[name]) motorsState[name] = { gen: 0 };
    return motorsState[name];
}

// Single global packet sending system
function startGlobalPacketTimer() {
    if (globalPacketTimer) return; // Already running
    
    globalPacketTimer = setInterval(() => {
        if (hasAnyActiveMotors()) {
            sendCombinedPacket();
        } else {
            // No active motors, stop the timer
            stopGlobalPacketTimer();
        }
    }, KEEPALIVE_INTERVAL);
}

function stopGlobalPacketTimer() {
    if (globalPacketTimer) {
        clearInterval(globalPacketTimer);
        globalPacketTimer = null;
    }
}

function hasAnyActiveMotors() {
    return Object.keys(activeMotors.axisMotors).length > 0 || 
           Object.keys(activeMotors.functionMotors).length > 0 || 
           Object.keys(activeMotors.logicFunctions).length > 0;
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
        ws.onopen = function () { 
            setWSStatus(true); 
        };
        ws.onclose = function () { 
            setWSStatus(false); 
            setTimeout(initWS, 5000); 
        };
        ws.onerror = function (e) { 
            console.error('WebSocket error:', e);
            setWSStatus(false); 
        };
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
            } catch (e) { 
                console.error('Error parsing WebSocket message:', e);
            }
        };
    } catch (e) {
        console.error('Error creating WebSocket:', e);
        setWSStatus(false);
    }
}

window.addEventListener('DOMContentLoaded', function () { 
    loadKeepAliveConfig().then(() => {
        initWS(); 
    }).catch(err => {
        initWS();
    });
});

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

// Stop a motor: cancel local timers + remove from active state
async function sendStop(name) {
    // locally cancel timers first
    stopLocal(name);
    
    // Remove motor from global active state
    delete activeMotors.axisMotors[name];
    delete activeMotors.functionMotors[name];
    
    // Send updated combined packet with remaining active motors (immediate)
    sendCombinedPacketImmediate();
}

// local-only stop: cancel timers and bump generation but do not dispatch network
function stopLocal(name) {
    const st = _ensureMotorState(name);
    st.gen += 1;
    
    // Cancel individual motor stop timer
    if (motorStopTimers[name]) {
        clearTimeout(motorStopTimers[name]);
        delete motorStopTimers[name];
    }
}

// Stop all motors: clear all state and send empty packet
async function stopAll() {
    stopAllLocal();
    
    // Clear all active motors
    activeMotors.axisMotors = {};
    activeMotors.functionMotors = {};
    activeMotors.logicFunctions = {};
    
    // Send empty combined packet (immediate)
    sendCombinedPacketImmediate();
}

function stopAllLocal() {
    try {
        // Stop global timer
        stopGlobalPacketTimer();
        
        // Clear all motor stop timers
        for (let name in motorStopTimers) {
            clearTimeout(motorStopTimers[name]);
            delete motorStopTimers[name];
        }
        
        // Bump generation for all motors to invalidate any pending operations
        for (let name in motorsState) {
            const st = motorsState[name];
            st.gen += 1;
        }
    } catch (e) { 
        console.error('Error in stopAllLocal:', e);
    }
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
function startMotor(name, dir, power, durationSec, useSlowMode = false) {
    const st = _ensureMotorState(name);
    
    // Cancel existing stop timer for this motor
    st.gen += 1;
    if (motorStopTimers[name]) {
        clearTimeout(motorStopTimers[name]);
        delete motorStopTimers[name];
    }

    const myGen = st.gen;
    
    // Add motor to global active state
    let isFunction = window.functionMotors && window.functionMotors.indexOf(name) !== -1;
    
    if (isFunction) {
        if (power > 0) {
            activeMotors.functionMotors[name] = { dir: dir };
        } else {
            delete activeMotors.functionMotors[name];
        }
    } else {
        if (power > 0) {
            activeMotors.axisMotors[name] = { 
                dir: dir, 
                power: power, 
                useSlowMode: useSlowMode 
            };
        } else {
            delete activeMotors.axisMotors[name];
        }
    }
    
    // Send immediately and start global timer
    sendCombinedPacketImmediate();
    startGlobalPacketTimer();

    // Schedule stop after duration if provided
    if (durationSec && durationSec > 0) {
        motorStopTimers[name] = setTimeout(function () {
            if (st.gen !== myGen) return; // Check if this timer is still valid
            
            // Remove motor and send stop
            sendStop(name);
        }, durationSec * 1000);
    }
}

// Send combined control packet for testing (includes all currently active motors)
function sendCombinedPacket(forceKeepAlive = false) {
    const now = Date.now();
    
    let packet = {
        axisMotors: { ...activeMotors.axisMotors },
        functionMotors: { ...activeMotors.functionMotors },
        logicFunctions: { ...activeMotors.logicFunctions }
    };
    
    let packetString = JSON.stringify(packet);
    
    // Check if packet has changed from last sent
    let hasChanged = !lastSentPacket || (packetString !== lastSentPacket);
    
    // For testing page, always send to maintain consistent timing
    // This ensures watchdog doesn't timeout due to packet gaps
    let shouldSend = hasChanged || forceKeepAlive || true; // Always send for testing
    
    if (shouldSend) {
        if (ws && ws.readyState === 1) {
            try {
                ws.send(packetString);
                lastSentPacket = packetString;
                window.lastSentTime = now;
            } catch (e) {
                console.error('WebSocket send error:', e);
            }
        } else {
            console.log('WebSocket not ready. State:', ws ? ws.readyState : 'ws is null');
        }
    }
}

// Force immediate packet send (for motor start/stop events)
function sendCombinedPacketImmediate() {
    sendCombinedPacket(true);
}

// Save motor power settings (min/slow/max) for axis motors
async function saveMotorPowerSettings(name) {
    let min_val = parseInt(document.getElementById(name + '_min').value);
    let slow_val = parseInt(document.getElementById(name + '_slow').value);
    let max_val = parseInt(document.getElementById(name + '_max').value);
    
    if (isNaN(min_val) || min_val < 1) min_val = 1;
    if (min_val > 65) min_val = 65;
    if (isNaN(slow_val) || slow_val < 1) slow_val = 1;
    if (slow_val > 65) slow_val = 65;
    if (isNaN(max_val) || max_val < 1) max_val = 1;
    if (max_val > 65) max_val = 65;
    
    try {
        const resp = await fetch('/testing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                action: 'save_axis_config',
                name: name,
                min_power: min_val,
                slow_power: slow_val,
                max_power: max_val
            })
        });
        if (resp.redirected) {
            window.location.href = resp.url;
        } else if (resp.ok) {
            window.location.reload();
        } else {
            alert('Failed to save power settings (server error)');
        }
    } catch (e) {
        alert('Failed to save power settings for ' + name);
    }
}

// Set max power to 65 for a motor
function setMaxPower(name) {
    document.getElementById(name + '_max').value = 65;
}

// Sync power settings from one motor to another
function syncPowerSettings(fromMotor, toMotor) {
    try {
        // Get values from source motor
        let minVal = document.getElementById(fromMotor + '_min').value;
        let slowVal = document.getElementById(fromMotor + '_slow').value;
        let maxVal = document.getElementById(fromMotor + '_max').value;
        
        // Set values on target motor
        document.getElementById(toMotor + '_min').value = minVal;
        document.getElementById(toMotor + '_slow').value = slowVal;
        document.getElementById(toMotor + '_max').value = maxVal;
        
        // Save the settings
        saveMotorPowerSettings(toMotor);
        
        alert(`Synced power settings from ${fromMotor} to ${toMotor}`);
    } catch (error) {
        console.error('Error syncing power settings:', error);
        alert('Error syncing power settings');
    }
}

// High-level UI run wrapper (keeps original API)
// List of function motors (populated by backend)
window.functionMotors = window.functionMotors || [];

function runMotor(name, dir) {
    let duration = parseFloat(document.getElementById(name + "_duration").value);
    let isFunction = window.functionMotors && window.functionMotors.indexOf(name) !== -1;
    let power;
    let useSlowMode = false;

    if (isFunction) {
        // Function motors: use either 0 (off) or 100 (on)
        power = 100;
    } else {
        // Axis motors: use power mode dropdown to determine which power level
        let powerMode = document.getElementById(name + "_power_mode").value;
        if (powerMode === "min") {
            power = 0.01; // Very small positive power to trigger min_power setting
            useSlowMode = false;
        } else if (powerMode === "slow") {
            power = 100; // 100% power but limited to slow_power setting
            useSlowMode = true;
        } else { // max
            power = 100; // 100% power uses max_power setting
            useSlowMode = false;
        }
    }

    startMotor(name, dir, power, duration, useSlowMode);
}

// Drive Tracking Adjustment Functions
function updateTrackingValue(adjustment) {
    let currentVal = parseFloat(document.getElementById('trackingValue').value) || 0.0;
    let newVal = currentVal + adjustment;
    
    // Round to 1 decimal place
    newVal = Math.round(newVal * 10) / 10;
    
    document.getElementById('trackingValue').value = newVal.toFixed(1);
    document.getElementById('driveTrackingAdjustment').value = newVal.toFixed(1);
    
    // Update arrow display
    let arrow = "→";
    if (newVal > 0.05) arrow = "↗";
    else if (newVal < -0.05) arrow = "↙";
    document.getElementById('trackingArrow').textContent = arrow;
}

function testDriveMotors() {
    // Run both drive motors forward for 10 seconds at max power
    let axisMotors = window.axisMotors || [];
    if (axisMotors.length >= 2) {
        let leftMotor = axisMotors[0];
        let rightMotor = axisMotors[1];
        startMotor(leftMotor, "fwd", 100, 10.0, false); // 100% power for 10 seconds
        startMotor(rightMotor, "fwd", 100, 10.0, false);
    }
}

function stopDriveMotors() {
    // Stop both drive motors immediately
    let axisMotors = window.axisMotors || [];
    if (axisMotors.length >= 2) {
        let leftMotor = axisMotors[0];
        let rightMotor = axisMotors[1];
        startMotor(leftMotor, "fwd", 0, 0, false); // 0% power to stop
        startMotor(rightMotor, "fwd", 0, 0, false);
    }
}

// Test drive functions for tracking adjustment testing
function testDriveMotors() {
    if (window.axisMotors && window.axisMotors.length >= 2) {
        const leftMotor = window.axisMotors[0];
        const rightMotor = window.axisMotors[1];
        
        // Run both motors forward for 10 seconds at 100% power
        startMotor(leftMotor, 'fwd', 100, 10);
        startMotor(rightMotor, 'fwd', 100, 10);
        
        console.log('Test drive started - both motors forward for 10 seconds at 100%');
    } else {
        alert('Cannot test drive - insufficient axis motors configured');
    }
}

function stopDriveMotors() {
    if (window.axisMotors && window.axisMotors.length >= 2) {
        const leftMotor = window.axisMotors[0];
        const rightMotor = window.axisMotors[1];
        
        sendStop(leftMotor);
        sendStop(rightMotor);
        
        console.log('Drive motors stopped');
    }
}

// Set up tracking adjustment button handlers when page loads
window.addEventListener('DOMContentLoaded', function() {
    // Tracking adjustment buttons
    if (document.getElementById('trackVeryLeft')) {
        document.getElementById('trackVeryLeft').onclick = () => updateTrackingValue(-2.0);
        document.getElementById('trackLeft').onclick = () => updateTrackingValue(-0.2);
        document.getElementById('trackZero').onclick = () => updateTrackingValue(-parseFloat(document.getElementById('trackingValue').value));
        document.getElementById('trackRight').onclick = () => updateTrackingValue(0.2);
        document.getElementById('trackVeryRight').onclick = () => updateTrackingValue(2.0);
    }
    
    // Test drive buttons
    if (document.getElementById('testDrive')) {
        document.getElementById('testDrive').onclick = testDriveMotors;
        document.getElementById('stopDrive').onclick = stopDriveMotors;
    }
});

// Save function motor settings (min power and travel safety)
function saveFunctionSettings(name) {
    const minInput = document.getElementById(`${name}_min`);
    const safetyCheckbox = document.getElementById(`${name}_travel_safety`);
    const forwardInput = document.getElementById(`${name}_forward_limit`);
    const reverseInput = document.getElementById(`${name}_reverse_limit`);
    
    if (!minInput || !safetyCheckbox || !forwardInput || !reverseInput) {
        console.error('Could not find function motor config elements for:', name);
        return;
    }
    
    // Create a form with action-based data
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/testing';
    form.style.display = 'none';
    
    // Add action field
    const actionField = document.createElement('input');
    actionField.name = 'action';
    actionField.value = 'save_function_config';
    form.appendChild(actionField);
    
    // Add motor name
    const nameField = document.createElement('input');
    nameField.name = 'name';
    nameField.value = name;
    form.appendChild(nameField);
    
    // Add min power
    const minField = document.createElement('input');
    minField.name = 'min_power';
    minField.value = minInput.value || '40';
    form.appendChild(minField);
    
    // Add travel safety
    const safetyField = document.createElement('input');
    safetyField.name = 'travel_safety';
    safetyField.value = safetyCheckbox.checked ? 'true' : 'false';
    form.appendChild(safetyField);
    
    // Add forward limit
    const forwardField = document.createElement('input');
    forwardField.name = 'forward_limit';
    forwardField.value = forwardInput.value || '0';
    form.appendChild(forwardField);
    
    // Add reverse limit
    const reverseField = document.createElement('input');
    reverseField.name = 'reverse_limit';
    reverseField.value = reverseInput.value || '0';
    form.appendChild(reverseField);
    
    // Submit the form
    document.body.appendChild(form);
    form.submit();
}

// Toggle reversed state for a motor
function toggleReversed(name) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/testing';
    form.style.display = 'none';
    
    // Add action
    const actionField = document.createElement('input');
    actionField.name = 'action';
    actionField.value = 'toggle_reversed';
    form.appendChild(actionField);
    
    // Add motor name
    const nameField = document.createElement('input');
    nameField.name = 'name';
    nameField.value = name;
    form.appendChild(nameField);
    
    // Submit the form
    document.body.appendChild(form);
    form.submit();
}

// Save axis motor power settings (min/slow/max)
function saveMotorPowerSettings(name) {
    const minInput = document.getElementById(`${name}_min`);
    const slowInput = document.getElementById(`${name}_slow`);
    const maxInput = document.getElementById(`${name}_max`);
    
    if (!minInput || !slowInput || !maxInput) {
        console.error('Could not find axis motor config elements for:', name);
        return;
    }
    
    // Create a form with action-based data
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/testing';
    form.style.display = 'none';
    
    // Add action field
    const actionField = document.createElement('input');
    actionField.name = 'action';
    actionField.value = 'save_axis_config';
    form.appendChild(actionField);
    
    // Add motor name
    const nameField = document.createElement('input');
    nameField.name = 'name';
    nameField.value = name;
    form.appendChild(nameField);
    
    // Add power values
    const minField = document.createElement('input');
    minField.name = 'min_power';
    minField.value = minInput.value || '40';
    form.appendChild(minField);
    
    const slowField = document.createElement('input');
    slowField.name = 'slow_power';
    slowField.value = slowInput.value || '50';
    form.appendChild(slowField);
    
    const maxField = document.createElement('input');
    maxField.name = 'max_power';
    maxField.value = maxInput.value || '65';
    form.appendChild(maxField);
    
    // Submit the form
    document.body.appendChild(form);
    form.submit();
}
